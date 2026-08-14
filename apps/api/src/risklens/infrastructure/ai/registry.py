"""Provider registry (models.dev-style) — the single source of truth for
which providers/models the platform can talk to.

Mirrors the pattern the AI SDK registry (models.dev) uses: a curated list of
providers with their OpenAI-compatible endpoints, env keys, chat models and
embedding models. The admin API exposes it (``/api/v1/admin/providers``) so the
UI can list options; the factories in ``llm_provider.py`` validate against it.
"""

from __future__ import annotations

from typing import TypedDict


class ModelInfo(TypedDict):
    id: str
    label: str
    free: bool
    dims: int | None  # embeddings only


class ProviderInfo(TypedDict):
    id: str
    label: str
    api: str | None
    env_key: str | None
    chat: bool
    embeddings: bool
    chat_models: list[ModelInfo]
    embedding_models: list[ModelInfo]


def _m(id: str, label: str, *, free: bool = False, dims: int | None = None) -> ModelInfo:
    return {"id": id, "label": label, "free": free, "dims": dims}


PROVIDERS: list[ProviderInfo] = [
    {
        "id": "opencode",
        "label": "OpenCode Zen",
        "api": "https://opencode.ai/zen/v1",
        "env_key": "OPENCODE_API_KEY",
        "chat": True,
        "embeddings": False,
        "chat_models": [
            _m("mimo-v2.5-free", "MiMo V2.5 (free)", free=True),
            _m("deepseek-v4-flash-free", "DeepSeek V4 Flash (free)", free=True),
            _m("glm-4.7-free", "GLM 4.7 (free)", free=True),
            _m("kimi-k2.5-free", "Kimi K2.5 (free)", free=True),
            _m("gpt-5-nano", "GPT-5 nano"),
        ],
        "embedding_models": [],
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "api": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "chat": True,
        "embeddings": True,
        "chat_models": [
            _m("gpt-4o-mini", "GPT-4o mini"),
            _m("gpt-4o", "GPT-4o"),
        ],
        "embedding_models": [
            _m("text-embedding-3-small", "text-embedding-3-small", dims=768),
        ],
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "api": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "chat": True,
        "embeddings": False,
        "chat_models": [
            _m("claude-3-5-haiku-latest", "Claude 3.5 Haiku"),
            _m("claude-sonnet-4-20250514", "Claude Sonnet 4"),
        ],
        "embedding_models": [],
    },
    {
        "id": "google",
        "label": "Google (Gemini)",
        "api": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "env_key": "GEMINI_API_KEY",
        "chat": True,
        "embeddings": False,
        "chat_models": [
            _m("gemini-2.0-flash", "Gemini 2.0 Flash"),
        ],
        "embedding_models": [],
    },
    {
        "id": "groq",
        "label": "Groq",
        "api": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "chat": True,
        "embeddings": False,
        "chat_models": [
            _m("llama-3.3-70b-versatile", "Llama 3.3 70B"),
            _m("qwen-2.5-coder-32b", "Qwen 2.5 Coder 32B"),
        ],
        "embedding_models": [],
    },
    {
        "id": "vertex",
        "label": "Google Vertex AI",
        "api": "https://aiplatform.googleapis.com",
        "env_key": "VERTEX_PROJECT / VERTEX_REGION",
        "chat": True,
        "embeddings": True,
        "chat_models": [
            _m("gemini-2.0-flash-001", "Gemini 2.0 Flash"),
        ],
        "embedding_models": [
            _m("text-embedding-005", "text-embedding-005", dims=768),
        ],
    },
    {
        "id": "fastembed",
        "label": "FastEmbed (self-hosted, free)",
        "api": None,
        "env_key": None,
        "chat": False,
        "embeddings": True,
        "chat_models": [],
        "embedding_models": [
            _m("nomic-ai/nomic-embed-text-v1.5", "nomic-embed-text v1.5 (ONNX)", dims=768),
        ],
    },
    {
        "id": "lmstudio",
        "label": "LM Studio (local)",
        "api": "http://127.0.0.1:1234/v1",
        "env_key": "LM_STUDIO_BASE_URL",
        "chat": True,
        "embeddings": True,
        "chat_models": [
            _m("google/gemma-3-4b", "Gemma 3 4B (local)"),
        ],
        "embedding_models": [
            _m("text-embedding-nomic-embed-text-v1.5", "nomic-embed-text v1.5", dims=768),
        ],
    },
    {
        "id": "ollama",
        "label": "Ollama (local)",
        "api": "http://127.0.0.1:11434/v1",
        "env_key": "OLLAMA_BASE_URL",
        "chat": True,
        "embeddings": True,
        "chat_models": [
            _m("gemma3:4b", "Gemma 3 4B (local)"),
        ],
        "embedding_models": [
            _m("nomic-embed-text", "nomic-embed-text", dims=768),
        ],
    },
]


def get_registry() -> list[ProviderInfo]:
    return [dict(p) for p in PROVIDERS]


def resolve_provider(provider_id: str) -> ProviderInfo:
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return p
    raise ValueError(f"provider desconhecido: {provider_id}")


def require_chat_model(provider_id: str, model_id: str) -> None:
    p = resolve_provider(provider_id)
    if not p["chat"]:
        raise ValueError(f"provider '{provider_id}' não oferece chat (use fastembed só p/ embeddings)")
    ids = {m["id"] for m in p["chat_models"]}
    if model_id not in ids:
        raise ValueError(f"modelo de chat '{model_id}' não listado para '{provider_id}'")


def require_embedding_model(provider_id: str, model_id: str, *, dims: int) -> None:
    p = resolve_provider(provider_id)
    if not p["embeddings"]:
        raise ValueError(
            f"provider '{provider_id}' não oferece embeddings — use openai/lmstudio/fastembed/vertex"
        )
    for m in p["embedding_models"]:
        if m["id"] == model_id:
            expected = m["dims"]
            if expected is not None and dims != expected:
                raise ValueError(
                    f"'{model_id}' produz {expected} dims, mas EMBEDDING_DIMS={dims} — "
                    f"mantenha {expected} para bater com vector(768) do pgvector"
                )
            return
    raise ValueError(f"modelo de embedding '{model_id}' não listado para '{provider_id}'")
