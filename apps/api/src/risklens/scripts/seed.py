"""Seed script: create default admin user (+ optionally enqueue sample docs
and import the golden eval definition from samples/golden).

Usage: uv run risklens-seed [--with-samples] [--with-evals]
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

from risklens.application.services.ingestion_service import ingest_upload
from risklens.core.config import settings
from risklens.core.security import hash_password
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.queue.queue import ArqJobQueue
from risklens.infrastructure.storage.fs_storage import FsDocumentStorage


async def _seed_eval_definitions() -> None:
    """Import each samples/golden/*.json as an eval definition (idempotent)."""
    golden_dir = Path(settings.samples_dir) / "golden"
    for path in sorted(golden_dir.glob("*.json")):
        slug = path.stem.replace("_", "-")  # credit_report -> credit-report
        if await repo.get_eval_definition_by_slug(slug) is not None:
            print(f"  definição já existe: {slug}")
            continue
        cases = json.loads(path.read_text(encoding="utf-8"))
        definition_cases = []
        for case in cases:
            doc_file = case.get("document_file")
            src = Path(settings.samples_dir) / "documents" / doc_file
            text = src.read_text(encoding="utf-8") if src.exists() else ""
            definition_cases.append(
                {
                    "document_file": doc_file,
                    "document_text": text,
                    "expected": case["expected"],
                }
            )
        if not definition_cases:
            print(f"  sem casos: {path.name}")
            continue
        title = "Golden: " + slug.replace("-", " ").title()
        await repo.create_eval_definition(
            slug=slug,
            title=title,
            description=f"Golden set importado de samples/golden/{path.name}",
            schema_name="credit_report",
            cases=definition_cases,
        )
        print(f"  definição criada: {slug} ({len(definition_cases)} casos)")


async def _main(with_samples: bool, with_evals: bool) -> None:
    existing = await repo.get_user_by_email(settings.seed_admin_email)
    if existing is None:
        await repo.create_user(
            email=settings.seed_admin_email,
            full_name="Admin",
            hashed_password=hash_password(settings.seed_admin_password),
            role="admin",
        )
        print(f"admin criado: {settings.seed_admin_email} / {settings.seed_admin_password}")
    else:
        print(f"admin já existe: {settings.seed_admin_email}")

    if with_evals:
        await _seed_eval_definitions()

    if with_samples:
        storage = FsDocumentStorage()
        queue = ArqJobQueue()
        docs_dir = Path(settings.samples_dir) / "documents"
        for path in sorted(docs_dir.glob("*")):
            if path.suffix.lower() not in (".md", ".txt", ".pdf"):
                continue
            from fastapi import UploadFile
            from starlette.datastructures import Headers

            class _File(UploadFile):
                def __init__(self, path: Path):
                    super().__init__(
                        file=io.BytesIO(path.read_bytes()),
                        filename=path.name,
                        headers=Headers({}),
                    )

            doc, dup = await ingest_upload(storage, queue, _File(path), user_id=None, source="seed")
            print(f"  {'duplicado' if dup else 'enfileirado'} {path.name} -> {doc.id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-samples", action="store_true", help="enqueue sample documents for processing")
    parser.add_argument("--with-evals", action="store_true", help="import golden eval definitions from samples/golden")
    args = parser.parse_args()

    import asyncio

    asyncio.run(_main(args.with_samples, args.with_evals))


if __name__ == "__main__":
    main()
