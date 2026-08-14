"""Settings panel service: read/update runtime AI config and test connections."""

from __future__ import annotations

import time

from risklens.core.config import settings
from risklens.infrastructure.ai import registry, runtime
from risklens.infrastructure.ai.llm_provider import build_chat_provider_for


async def get_settings() -> dict:
    return {
        "config": runtime.get_cached_config(),
        "overridden": sorted(runtime.get_overridden_keys()),
    }


async def update_settings(updates: dict) -> dict:
    """Validate provider/model combos against the registry before persisting."""
    chat_provider = updates.get("chat_provider")
    chat_model = updates.get("chat_model")
    if chat_provider and chat_model:
        registry.require_chat_model(chat_provider.lower(), chat_model)
    embed_provider = updates.get("embedding_provider")
    embed_model = updates.get("embedding_model")
    if embed_provider and embed_model:
        registry.require_embedding_model(
            embed_provider.lower(), embed_model, dims=settings.embedding_dims
        )

    await runtime.apply_updates(updates)
    return await get_settings()


async def test_chat(provider: str, model: str) -> dict:
    llm = build_chat_provider_for(provider, model)
    start = time.perf_counter()
    try:
        reply = await llm.complete(
            system="Responda apenas com a palavra: OK", user="ping", max_tokens=10, temperature=0
        )
        return {
            "ok": True,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "model": model,
            "reply": reply[:120],
        }
    except Exception as exc:  # noqa: BLE001 - report the provider error
        return {
            "ok": False,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "model": model,
            "error": str(exc)[:300],
        }
