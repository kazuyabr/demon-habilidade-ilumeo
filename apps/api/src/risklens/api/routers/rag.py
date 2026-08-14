"""RAG routes: grounded question answering over indexed documents."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from risklens.api.deps import get_current_user, get_vector_store
from risklens.api.schemas import RagAnswer
from risklens.application.services import credential_service
from risklens.application.services.rag_service import ask
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/rag", tags=["rag"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_id: UUID | None = None


@router.post("/ask", response_model=RagAnswer)
async def ask_question(
    body: AskRequest,
    user: User = Depends(get_current_user),
    vector_store=Depends(get_vector_store),
) -> RagAnswer:
    # BYOK: build providers with the requesting user's credentials (env fallback)
    llm = await credential_service.build_user_chat_provider(user.id)
    embedder = await credential_service.build_user_embedding_provider(user.id)
    result = await ask(llm, embedder, vector_store, question=body.question, document_id=body.document_id)
    return RagAnswer(**result)
