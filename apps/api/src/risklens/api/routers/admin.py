"""Admin routes: feature flags, multi-provider registry and runtime settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from risklens.api.deps import get_current_user, require_roles
from risklens.api.schemas import (
    ActiveProviderOut,
    FeatureFlagsOut,
    ProvidersOut,
    SettingsOut,
    SettingsTestIn,
    SettingsTestOut,
    SettingsUpdate,
)
from risklens.application.services.settings_service import (
    get_settings,
    test_chat_for_user,
    update_settings,
)
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


@router.get("/settings", response_model=SettingsOut)
async def get_app_settings(_: User = Depends(get_current_user)) -> SettingsOut:
    return SettingsOut(**await get_settings())


@router.put("/settings", response_model=SettingsOut)
async def put_app_settings(
    body: SettingsUpdate,
    _: User = Depends(require_roles("admin", "analyst")),
) -> SettingsOut:
    try:
        return SettingsOut(**await update_settings(body.model_dump(exclude_unset=True)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/settings/test", response_model=SettingsTestOut)
async def post_settings_test(
    body: SettingsTestIn,
    user: User = Depends(require_roles("admin", "analyst")),
) -> SettingsTestOut:
    # BYOK: test using the requesting user's credentials (env fallback)
    return SettingsTestOut(**await test_chat_for_user(user.id, body.provider, body.model))
