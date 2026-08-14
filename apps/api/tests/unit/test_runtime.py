"""Unit tests for the runtime AI configuration (no DB required)."""

from __future__ import annotations

from risklens.infrastructure.ai import runtime


def test_runtime_fields_cover_expected_keys() -> None:
    expected = {
        "chat_provider",
        "chat_model",
        "embedding_provider",
        "embedding_model",
        "temperature",
        "max_tokens",
        "chunk_size",
        "top_k",
        "rag_hybrid",
        "ff_agent_review_enabled",
        "ff_eval_llm_judge",
    }
    assert expected <= set(runtime.RUNTIME_FIELDS.keys())


def test_cached_config_falls_back_to_env_baseline(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "_cache", None)
    monkeypatch.setattr(runtime, "_overridden", set())
    cfg = runtime.get_cached_config()
    assert cfg["chat_provider"] == "lmstudio"
    assert cfg["chat_model"] == "google/gemma-3-4b"
    assert cfg["embedding_provider"] == "lmstudio"
    assert cfg["temperature"] == 0.1
    assert cfg["chunk_size"] == 1200
    assert cfg["top_k"] == 6
    assert runtime.get_overridden_keys() == set()


def test_apply_updates_rejects_unknown_fields() -> None:
    import pytest

    with pytest.raises(ValueError):
        # apply_updates is async and hits the DB — validate the guard via the
        # allowed-key check logic by calling with an unknown key and catching
        # before the DB write would be attempted (guard runs first).
        import asyncio

        async def go() -> None:
            await runtime.apply_updates({"nao_existe": 1})

        asyncio.run(go())
