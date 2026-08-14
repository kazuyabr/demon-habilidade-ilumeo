"""arq worker: async job processing for ingestion, agents and evals.

``max_jobs=1`` intentionally serializes LLM calls: LM Studio serves one
generated model at a time and model swaps are slow/racy. Trade-off:
predictable latency per job vs parallel throughput (documented in docs).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from uuid import UUID

from arq.connections import RedisSettings
from arq.worker import create_worker
from pypdf import PdfReader

from risklens.application.services.agent_service import execute_agent
from risklens.application.services.eval_service import run_eval
from risklens.application.services.extraction_service import extract_from_text
from risklens.application.services.indexing_service import index_document
from risklens.core.config import settings
from risklens.infrastructure.ai.llm_provider import build_chat_provider, build_embedding_provider
from risklens.infrastructure.cache.redis import redis_client
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.storage.fs_storage import FsDocumentStorage
from risklens.infrastructure.vector.pgvector_store import PgVectorStore

logger = logging.getLogger("risklens.worker")

storage = FsDocumentStorage()
vector_store = PgVectorStore()


async def _read_document_text(document_id: UUID) -> tuple[str, str]:
    """Return (content_type, text)."""
    doc = await repo.get_document_by_id(document_id)
    if doc is None:
        raise ValueError(f"document {document_id} not found")
    data = await storage.read(doc.storage_path)
    if doc.content_type == "pdf":
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        text = data.decode("utf-8", errors="replace")
    return doc.content_type, text


async def process_document(ctx: dict, document_id: str) -> dict:
    """Ingestion pipeline: extract → redact → index. Idempotent by document id."""
    run_id = UUID(document_id)
    doc = await repo.get_document_by_id(run_id)
    if doc is None:
        return {"status": "not_found"}
    if doc.status == "completed":
        return {"status": "already_processed"}

    await repo.update_document_status(run_id, status="processing")
    llm = ctx["llm"]
    embedder = ctx["embedder"]

    try:
        _, text = await _read_document_text(run_id)
        ext = await repo.get_extraction_by_document(run_id)
        extraction_id = ext.id if ext else (await repo.create_extraction(run_id, schema_name="credit_report")).id

        data, confidence, raw = await extract_from_text(llm, text=text, schema_name="credit_report")
        await repo.update_extraction_result(
            extraction_id,
            status="completed",
            data=data,
            raw_llm_output=raw,
            model_used=llm.model,
            confidence=confidence,
        )

        n_chunks = await index_document(embedder, vector_store, document_id=run_id, text=text)
        await repo.update_document_status(run_id, status="completed")
        return {"status": "completed", "chunks": n_chunks, "confidence": confidence}
    except Exception as exc:  # noqa: BLE001 - worker must mark failure, not die
        logger.exception("document %s failed", run_id)
        await repo.update_document_status(run_id, status="failed", error_message=str(exc)[:1000])
        ext = await repo.get_extraction_by_document(run_id)
        if ext:
            await repo.update_extraction_result(ext.id, status="failed", error_message=str(exc)[:1000])
        return {"status": "failed", "error": str(exc)[:500]}


async def run_agent_job(ctx: dict, run_id: str) -> dict:
    llm = ctx["llm"]
    embedder = ctx["embedder"]
    run = await repo.get_agent_run(UUID(run_id))
    if run is None:
        return {"status": "not_found"}
    try:
        result = await execute_agent(llm, embedder, vector_store, run_id=run.id, question=run.question)
        return {"status": "completed", "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent run %s failed", run_id)
        await repo.finish_agent_run(run.id, status="failed", error_message=str(exc)[:1000])
        return {"status": "failed", "error": str(exc)[:500]}


async def run_eval_job(ctx: dict, run_id: str) -> dict:
    llm = ctx["llm"]
    run = await repo.get_eval_run(UUID(run_id))
    if run is None:
        return {"status": "not_found"}
    try:
        metrics = await run_eval(llm, eval_run_id=run.id, name=run.name)
        return {"status": "completed", "metrics": metrics}
    except Exception as exc:  # noqa: BLE001
        logger.exception("eval run %s failed", run_id)
        await repo.finish_eval_run(run.id, status="failed", error_message=str(exc)[:1000])
        return {"status": "failed", "error": str(exc)[:500]}


async def startup(ctx: dict) -> None:
    ctx["llm"] = build_chat_provider()
    ctx["embedder"] = build_embedding_provider()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


async def shutdown(ctx: dict) -> None:
    await redis_client.aclose()


class WorkerSettings:
    functions = [process_document, run_agent_job, run_eval_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 1  # serialize LLM calls (see module docstring)
    job_timeout = 600
    keep_result = 3600
    retry_jobs = True
    max_tries = 3


def main() -> None:
    create_worker(WorkerSettings).run()


if __name__ == "__main__":
    main()
