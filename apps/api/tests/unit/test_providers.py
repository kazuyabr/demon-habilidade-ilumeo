"""Unit tests for the provider factories (env-driven selection)."""

from __future__ import annotations

from risklens.core.config import settings
from risklens.infrastructure.ai.llm_provider import (
    AnthropicProvider,
    FastEmbedProvider,
    OpenAICompatibleEmbeddings,
    OpenAICompatibleProvider,
    build_chat_provider,
    build_embedding_provider,
)


def test_default_chat_is_lmstudio(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "lmstudio")
    monkeypatch.setattr(settings, "llm_model", "google/gemma-3-4b")
    provider = build_chat_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == settings.lm_studio_base_url
    assert provider.model == "google/gemma-3-4b"


def test_opencode_chat(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "opencode")
    monkeypatch.setattr(settings, "llm_model", "mimo-v2.5-free")
    monkeypatch.setattr(settings, "opencode_api_key", "test-key")
    provider = build_chat_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "https://opencode.ai/zen/v1"
    assert provider.model == "mimo-v2.5-free"


def test_anthropic_chat(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_model", "claude-3-5-haiku-latest")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    provider = build_chat_provider()
    assert isinstance(provider, AnthropicProvider)


def test_custom_chat_uses_explicit_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "custom")
    monkeypatch.setattr(settings, "llm_base_url", "http://gateway.local/v1")
    monkeypatch.setattr(settings, "llm_api_key", "gw-key")
    provider = build_chat_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "http://gateway.local/v1"


def test_default_embedding_is_lmstudio(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "lmstudio")
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-nomic-embed-text-v1.5")
    provider = build_embedding_provider()
    assert isinstance(provider, OpenAICompatibleEmbeddings)
    assert provider.dims is None  # LM Studio não recebe dimensions=


def test_openai_embedding_forwards_dims(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-3-small")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    provider = build_embedding_provider()
    assert isinstance(provider, OpenAICompatibleEmbeddings)
    assert provider.dims == 768


def test_fastembed_keyless(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "fastembed")
    monkeypatch.setattr(settings, "embedding_model", "intfloat/multilingual-e5-base")
    provider = build_embedding_provider()
    assert isinstance(provider, FastEmbedProvider)
    assert provider.dims == 768
