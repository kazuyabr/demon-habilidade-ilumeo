"""Document routes: upload (queued ingestion), list, detail, delete."""

from __future__ import annotations

import contextlib
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from risklens.api.deps import get_current_user, get_job_queue, get_storage
from risklens.api.schemas import DocumentOut, UploadResponse
from risklens.application.services.ingestion_service import ValidationError_, ingest_upload
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    source: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    storage=Depends(get_storage),
    queue=Depends(get_job_queue),
) -> UploadResponse:
    try:
        doc, duplicate = await ingest_upload(
            storage, queue, file, user_id=user.id, source=source
        )
    except ValidationError_ as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None

    return UploadResponse(document=DocumentOut.model_validate(doc), duplicate=duplicate)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    _: User = Depends(get_current_user),
) -> list[DocumentOut]:
    docs = await repo.list_documents(limit=min(limit, 200), offset=offset)
    return [DocumentOut.model_validate(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    _: User = Depends(get_current_user),
) -> DocumentOut:
    doc = await repo.get_document_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")
    return DocumentOut.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    storage=Depends(get_storage),
) -> None:
    if user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente")
    doc = await repo.get_document_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")
    with contextlib.suppress(Exception):  # best-effort cleanup
        await storage.delete(doc.storage_path)
    await repo.delete_document(document_id)
