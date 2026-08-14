"""Runtime AI configuration.

``.env`` provides the baseline; the settings panel persists **overrides** in the
``app_settings`` table (single JSONB row). No secrets are ever stored here —
API keys remain in env/Secret Manager. The effective config is cached in memory
and reloaded when settings change; a Redis version counter lets the worker and
API rebuild providers lazily.
"""

from __future__ import annotations

from typing import Any

from risklens.core.config import settings
from risklens.infrastructure.cache.redis import redis_client
from risklens.infrastructure.db import models as m
from risklens.infrastructure.db.session import SessionFactory

SETTINGS_KEY = "ai"
CONFIG_VERSION_KEY = "config:version"

# Runtime-overridable field -> (env fallback attribute, env default)
RUNTIME_FIELDS: dict[str, tuple[str, Any]] = {
    "chat_provider": ("llm_provider", settings.llm_provider),
    "chat_model": ("llm_model", settings.llm_model),
    "embedding_provider": ("embedding_provider", settings.embedding_provider),
    "embedding_model": ("embedding_model", settings.embedding_model),
    "temperature": ("llm_temperature", settings.llm_temperature),
    "max_tokens": ("llm_max_tokens", settings.llm_max_tokens),
    "chunk_size": ("rag_chunk_size", settings.rag_chunk_size),
    "top_k": ("rag_top_k", settings.rag_top_k),
    "rag_hybrid": ("ff_rag_hybrid_search", settings.ff_rag_hybrid_search),
    "ff_agent_review_enabled": ("ff_agent_review_enabled", settings.ff_agent_review_enabled),
    "ff_eval_llm_judge": ("ff_eval_llm_judge", settings.ff_eval_llm_judge),
}

_cache: dict[str, Any] | None = None
_overridden: set[str] = set()


def _env_baseline() -> dict[str, Any]:
    return {k: getattr(settings, attr) for k, (attr, _d) in RUNTIME_FIELDS.items()}


async def _load_overrides() -> dict[str, Any]:
    async with SessionFactory() as session:
        row = await session.get(m.AppSetting, SETTINGS_KEY)
        return dict(row.value) if row else {}


async def load_effective_config() -> dict[str, Any]:
    """Merge env defaults + DB overrides into the module cache."""
    global _cache, _overridden
    baseline = _env_baseline()
    overrides = await _load_overrides()
    merged = {**baseline, **overrides}
    _cache = merged
    _overridden = set(overrides.keys())
    return merged


def get_cached_config() -> dict[str, Any]:
    """Sync access for services/factories; falls back to env-only pre-startup."""
    return _cache if _cache is not None else _env_baseline()


def get_overridden_keys() -> set[str]:
    return set(_overridden)


async def get_config_version() -> int:
    raw = await redis_client.get(CONFIG_VERSION_KEY)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def bump_config_version() -> None:
    await redis_client.set(CONFIG_VERSION_KEY, str(await get_config_version() + 1))


async def apply_updates(updates: dict[str, Any]) -> dict[str, Any]:
    """Validate + persist overrides (None resets to env), reload cache, bump version."""
    allowed = set(RUNTIME_FIELDS.keys())
    invalid = set(updates.keys()) - allowed
    if invalid:
        raise ValueError(f"campos desconhecidos: {sorted(invalid)}")

    overrides = await _load_overrides()
    for key, value in updates.items():
        if value is None:
            overrides.pop(key, None)
        else:
            overrides[key] = value

    async with SessionFactory() as session:
        row = await session.get(m.AppSetting, SETTINGS_KEY)
        if overrides:
            if row is None:
                session.add(m.AppSetting(key=SETTINGS_KEY, value=overrides))
            else:
                row.value = overrides
        elif row is not None:
            await session.delete(row)
        await session.commit()

    merged = await load_effective_config()
    await bump_config_version()
    return merged
