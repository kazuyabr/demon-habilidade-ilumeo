"""Ingestion service: accept upload → dedupe → persist → enqueue processing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from risklens.application.ports import DocumentStorage, JobQueue
from risklens.core.config import settings
from risklens.infrastructure.db import repository as repo


class ValidationError_(ValueError):
    pass


async def ingest_upload(
    storage: DocumentStorage,
    queue: JobQueue,
    file: UploadFile,
    *,
    user_id: UUID | None,
    source: str | None = None,
) -> tuple[object, bool]:
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if ext not in settings.allowed_extension_list:
        raise ValidationError_(
            f"extensão '{ext}' não permitida (permitidas: {settings.allowed_extension_list})"
        )

    data = await file.read()
    if not data:
        raise ValidationError_("arquivo vazio")
    if len(data) > settings.max_upload_bytes:
        raise ValidationError_(
            f"arquivo excede {settings.max_upload_mb}MB ({len(data) / 1024 / 1024:.1f}MB)"
        )

    sha256 = hashlib.sha256(data).hexdigest()
    existing = await repo.get_document_by_sha256(sha256)
    if existing is not None:
        return existing, True  # idempotent upload: same content → no duplicate work

    storage_path = await storage.save(file.filename or f"upload.{ext}", data)
    content_type = "pdf" if ext == "pdf" else ("md" if ext == "md" else "txt")
    title = Path(file.filename or "document").stem.replace("_", " ").replace("-", " ").strip() or file.filename

    doc = await repo.create_document(
        filename=file.filename or "document",
        title=title,
        storage_path=storage_path,
        content_type=content_type,
        sha256=sha256,
        size_bytes=len(data),
        created_by=user_id,
        source=source,
    )

    await queue.enqueue("process_document", _job_id=str(doc.id), document_id=str(doc.id))
    return doc, False
