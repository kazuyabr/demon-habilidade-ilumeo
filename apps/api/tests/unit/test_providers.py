"""Unit tests for the provider factories (env-driven + runtime config)."""

from __future__ import annotations

from risklens.core.config import settings
from risklens.infrastructure.ai import runtime
from risklens.infrastructure.ai.llm_provider import (
    AnthropicProvider,
    FastEmbedProvider,
    OpenAICompatibleEmbeddings,
    OpenAICompatibleProvider,
    build_chat_provider,
    build_embedding_provider,
)


def _set_cfg(monkeypatch, **fields) -> None:
    """Point the runtime cache at a config (env baseline + overrides)."""
    cfg = runtime._env_baseline()
    cfg.update(fields)
    monkeypatch.setattr(runtime, "_cache", cfg)


def test_default_chat_is_lmstudio(monkeypatch) -> None:
    _set_cfg(monkeypatch)
    provider = build_chat_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == settings.lm_studio_base_url
    assert provider.model == "google/gemma-3-4b"


def test_opencode_chat(monkeypatch) -> None:
    monkeypatch.setattr(settings, "opencode_api_key", "test-key")
    _set_cfg(monkeypatch, chat_provider="opencode", chat_model="mimo-v2.5-free")
    provider = build_chat_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "https://opencode.ai/zen/v1"
    assert provider.model == "mimo-v2.5-free"


def test_anthropic_chat(monkeypatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    _set_cfg(monkeypatch, chat_provider="anthropic", chat_model="claude-3-5-haiku-latest")
    provider = build_chat_provider()
    assert isinstance(provider, AnthropicProvider)


def test_custom_chat_uses_explicit_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_base_url", "http://gateway.local/v1")
    monkeypatch.setattr(settings, "llm_api_key", "gw-key")
    _set_cfg(monkeypatch, chat_provider="custom", chat_model="x")
    provider = build_chat_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "http://gateway.local/v1"


def test_default_embedding_is_lmstudio(monkeypatch) -> None:
    _set_cfg(monkeypatch)
    provider = build_embedding_provider()
    assert isinstance(provider, OpenAICompatibleEmbeddings)
    assert provider.dims is None  # LM Studio não recebe dimensions=


def test_openai_embedding_forwards_dims(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    _set_cfg(monkeypatch, embedding_provider="openai", embedding_model="text-embedding-3-small")
    provider = build_embedding_provider()
    assert isinstance(provider, OpenAICompatibleEmbeddings)
    assert provider.dims == 768


def test_fastembed_keyless(monkeypatch) -> None:
    _set_cfg(monkeypatch, embedding_provider="fastembed", embedding_model="nomic-ai/nomic-embed-text-v1.5")
    provider = build_embedding_provider()
    assert isinstance(provider, FastEmbedProvider)
    assert provider.dims == 768
