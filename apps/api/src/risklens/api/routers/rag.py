"""RAG routes: grounded question answering over indexed documents."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from risklens.api.deps import get_current_user, get_llm, get_vector_store
from risklens.api.schemas import RagAnswer
from risklens.application.services.rag_service import ask
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/rag", tags=["rag"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_id: UUID | None = None


@router.post("/ask", response_model=RagAnswer)
async def ask_question(
    body: AskRequest,
    _: User = Depends(get_current_user),
    llm=Depends(get_llm),
    vector_store=Depends(get_vector_store),
) -> RagAnswer:
    result = await ask(llm, vector_store, question=body.question, document_id=body.document_id)
    return RagAnswer(**result)
