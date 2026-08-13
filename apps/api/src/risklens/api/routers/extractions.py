"""Extraction routes: read extraction for a document, re-trigger processing."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from risklens.api.deps import get_current_user, get_job_queue
from risklens.api.schemas import ExtractionOut
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/extractions", tags=["extractions"])


@router.get("/document/{document_id}", response_model=ExtractionOut)
async def get_extraction(
    document_id: UUID,
    _: User = Depends(get_current_user),
) -> ExtractionOut:
    ext = await repo.get_extraction_by_document(document_id)
    if ext is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extração não encontrada")
    return ExtractionOut.model_validate(ext)


@router.post("/document/{document_id}/re-run", response_model=ExtractionOut)
async def rerun_extraction(
    document_id: UUID,
    user: User = Depends(get_current_user),
    queue=Depends(get_job_queue),
) -> ExtractionOut:
    if user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente")
    doc = await repo.get_document_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    await repo.update_document_status(document_id, status="processing", error_message=None)
    await queue.enqueue("process_document", _job_id=f"{document_id}:rerun", document_id=str(document_id))

    ext = await repo.get_extraction_by_document(document_id)
    if ext is None:
        ext = await repo.create_extraction(document_id, schema_name="credit_report")
    return ExtractionOut.model_validate(ext)
