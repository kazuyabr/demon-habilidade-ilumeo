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

from risklens.application.services import credential_service
from risklens.application.services.agent_service import execute_agent
from risklens.application.services.eval_service import run_eval
from risklens.application.services.extraction_service import extract_from_text
from risklens.application.services.indexing_service import index_document
from risklens.core.config import settings
from risklens.infrastructure.ai import runtime
from risklens.infrastructure.ai.llm_provider import (
    build_chat_provider,
    build_chat_provider_for,
    build_embedding_provider,
)
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


async def _providers(ctx: dict) -> tuple[object, object]:
    """Rebuild LLM/embedder lazily when the runtime config version changes."""
    version = await runtime.get_config_version()
    if ctx.get("_cfg_version") != version:
        ctx["llm"] = build_chat_provider()
        ctx["embedder"] = build_embedding_provider()
        ctx["_cfg_version"] = version
    return ctx["llm"], ctx["embedder"]


async def _providers_for(ctx: dict, user_id=None) -> tuple[object, object]:
    """BYOK: use the aggregate owner's credentials when present, else env."""
    if user_id is not None:
        return (
            await credential_service.build_user_chat_provider(user_id),
            await credential_service.build_user_embedding_provider(user_id),
        )
    return await _providers(ctx)


async def _llm_for_run(ctx: dict, *, provider: str | None, model: str | None, user_id: str | None):
    """Chat LLM for an eval run: explicit (provider, model) override wins,
    else the requesting user's effective credentials (BYOK), else the active one."""
    if provider and model:
        if user_id is not None:
            base_url, api_key = await credential_service.get_effective_chat_endpoint(UUID(user_id), provider)
            return build_chat_provider_for(provider, model, base_url=base_url, api_key=api_key)
        return build_chat_provider_for(provider, model)
    if user_id is not None:
        return await credential_service.build_user_chat_provider(UUID(user_id))
    return ctx["llm"]


async def process_document(ctx: dict, document_id: str) -> dict:
    """Ingestion pipeline: extract → redact → index. Idempotent by document id."""
    run_id = UUID(document_id)
    doc = await repo.get_document_by_id(run_id)
    if doc is None:
        return {"status": "not_found"}
    if doc.status == "completed":
        return {"status": "already_processed"}

    await repo.update_document_status(run_id, status="processing")
    llm, embedder = await _providers_for(ctx, doc.created_by)

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
    run = await repo.get_agent_run(UUID(run_id))
    if run is None:
        return {"status": "not_found"}
    llm, embedder = await _providers_for(ctx, run.created_by)
    try:
        result = await execute_agent(llm, embedder, vector_store, run_id=run.id, question=run.question)
        return {"status": "completed", "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent run %s failed", run_id)
        await repo.finish_agent_run(run.id, status="failed", error_message=str(exc)[:1000])
        return {"status": "failed", "error": str(exc)[:500]}


async def run_eval_job(
    ctx: dict,
    run_id: str,
    *,
    definition_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    user_id: str | None = None,
) -> dict:
    run = await repo.get_eval_run(UUID(run_id))
    if run is None:
        return {"status": "not_found"}
    try:
        if definition_id is None:
            raise ValueError("run sem definition_id")
        definition = await repo.get_eval_definition_by_id(UUID(definition_id))
        if definition is None:
            raise ValueError(f"definição não encontrada: {definition_id}")
        llm = await _llm_for_run(ctx, provider=provider, model=model, user_id=user_id)
        metrics = await run_eval(
            llm,
            eval_run_id=run.id,
            name=run.name,
            cases=definition.cases,
            schema_name=definition.schema_name,
        )
        return {"status": "completed", "metrics": metrics}
    except Exception as exc:  # noqa: BLE001
        logger.exception("eval run %s failed", run_id)
        await repo.finish_eval_run(run.id, status="failed", error_message=str(exc)[:1000])
        return {"status": "failed", "error": str(exc)[:500]}


async def startup(ctx: dict) -> None:
    await runtime.load_effective_config()
    ctx["llm"] = build_chat_provider()
    ctx["embedder"] = build_embedding_provider()
    ctx["_cfg_version"] = await runtime.get_config_version()
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
