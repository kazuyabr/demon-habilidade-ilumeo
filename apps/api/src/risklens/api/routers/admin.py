"""Admin routes: feature flags + multi-provider registry for the UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from risklens.api.deps import get_current_user
from risklens.api.schemas import ActiveProviderOut, FeatureFlagsOut, ProvidersOut
from risklens.core.config import settings
from risklens.infrastructure.ai.registry import get_registry
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/flags", response_model=FeatureFlagsOut)
async def get_flags(_: User = Depends(get_current_user)) -> FeatureFlagsOut:
    return FeatureFlagsOut(
        agent_review_enabled=settings.ff_agent_review_enabled,
        rag_hybrid_search=settings.ff_rag_hybrid_search,
        eval_llm_judge=settings.ff_eval_llm_judge,
        llm_model=settings.llm_model,
        llm_provider=settings.llm_provider,
        embedding_model=settings.embedding_model,
        embedding_provider=settings.embedding_provider,
        embedding_dims=settings.embedding_dims,
    )


@router.get("/providers", response_model=ProvidersOut)
async def get_providers(_: User = Depends(get_current_user)) -> ProvidersOut:
    return ProvidersOut(
        providers=get_registry(),
        active_chat=ActiveProviderOut(provider=settings.llm_provider, model=settings.llm_model),
        active_embeddings=ActiveProviderOut(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            dims=settings.embedding_dims,
        ),
    )
