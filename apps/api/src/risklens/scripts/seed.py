"""Seed script: create default admin user (+ optionally enqueue sample docs).

Usage: uv run risklens-seed [--with-samples]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from risklens.application.services.ingestion_service import ingest_upload
from risklens.core.config import settings
from risklens.core.security import hash_password
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.queue.queue import ArqJobQueue
from risklens.infrastructure.storage.fs_storage import FsDocumentStorage


async def _main(with_samples: bool) -> None:
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
                    super().__init__(filename=path.name, headers=Headers({}))
                    self._data = path.read_bytes()

                async def read(self, size: int = -1) -> bytes:
                    return self._data

            doc, dup = await ingest_upload(storage, queue, _File(path), user_id=None, source="seed")
            print(f"  {'duplicado' if dup else 'enfileirado'} {path.name} -> {doc.id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-samples", action="store_true", help="enqueue sample documents for processing")
    args = parser.parse_args()

    import asyncio

    asyncio.run(_main(args.with_samples))


if __name__ == "__main__":
    main()
