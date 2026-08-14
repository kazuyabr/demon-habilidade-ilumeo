"""Unit tests for the models.dev-style provider registry."""

from __future__ import annotations

import pytest

from risklens.infrastructure.ai import registry


def test_registry_lists_providers() -> None:
    providers = registry.get_registry()
    ids = {p["id"] for p in providers}
    assert {"opencode", "openai", "anthropic", "google", "groq", "vertex", "fastembed", "lmstudio", "ollama"} <= ids


def test_opencode_offers_free_chat() -> None:
    p = registry.resolve_provider("opencode")
    assert p["chat"] is True
    assert p["embeddings"] is False
    free_models = {m["id"] for m in p["chat_models"] if m["free"]}
    assert "mimo-v2.5-free" in free_models


def test_embeddings_dimension_is_768_everywhere() -> None:
    for provider_id in ("openai", "fastembed", "lmstudio", "vertex", "ollama"):
        p = registry.resolve_provider(provider_id)
        assert p["embeddings"], provider_id
        for m in p["embedding_models"]:
            assert m["dims"] == 768, (provider_id, m["id"])


def test_require_chat_model_unknown_raises() -> None:
    with pytest.raises(ValueError):
        registry.require_chat_model("fastembed", "gpt-4o")  # fastembed não tem chat


def test_require_embedding_model_wrong_dims_raises() -> None:
    with pytest.raises(ValueError):
        registry.require_embedding_model("openai", "text-embedding-3-small", dims=512)


def test_require_embedding_model_provider_without_embeddings_raises() -> None:
    with pytest.raises(ValueError):
        registry.require_embedding_model("anthropic", "x", dims=768)


def test_resolve_unknown_provider_raises() -> None:
    with pytest.raises(ValueError):
        registry.resolve_provider("nao-existe")


def test_resolve_model_protocol() -> None:
    assert registry.resolve_model_protocol("opencode-go", "mimo-v2.5") == "chat"
    assert registry.resolve_model_protocol("opencode-go", "grok-4.5") == "responses"
    assert registry.resolve_model_protocol("opencode-go", "qwen3.7-max") == "messages"
    assert registry.resolve_model_protocol("opencode", "gemini-3.7-flash") == "google"
    assert registry.resolve_model_protocol("opencode", "mimo-v2.5-free") == "chat"
    # unmapped/custom always fall back to OpenAI-compatible
    assert registry.resolve_model_protocol("custom", "qualquer-modelo") == "chat"
    assert registry.resolve_model_protocol("opencode-go", "modelo-desconhecido") == "chat"


def test_registry_has_custom_and_go() -> None:
    ids = {p["id"] for p in registry.get_registry()}
    assert "opencode-go" in ids
    assert "custom" in ids
