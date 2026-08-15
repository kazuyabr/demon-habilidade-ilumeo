"""Provider registry (models.dev-style) — the single source of truth for
which providers/models the platform can talk to.

Each model is tagged with the API **protocol** it speaks, per the OpenCode docs:
- ``chat``      → OpenAI-compatible  ``POST /v1/chat/completions``
- ``responses`` → OpenAI Responses   ``POST /v1/responses``
- ``messages``  → Anthropic Messages ``POST /v1/messages``
- ``google``    → Gemini             ``POST /models/{id}:generateContent``

The admin API exposes it (``/api/v1/admin/providers``); the factories in
``llm_provider.py`` dispatch to the right adapter by (provider, model).
``custom`` is a generic OpenAI-compatible provider for unmapped gateways.
"""

from __future__ import annotations

from typing import TypedDict

Protocol = str  # chat | responses | messages | google


class ModelInfo(TypedDict):
    id: str
    label: str
    free: bool
    dims: int | None  # embeddings only
    protocol: Protocol
    sdk: str  # AI SDK package, per the OpenCode docs endpoint tables
    # Chinese-origin provider. Not a hosting claim (docs: Zen=US, Go=global);
    # signals a possible need to enable "models hosted in China" on the Go
    # subscription if requests fail with a permission error.
    china_gated: bool


class ProviderInfo(TypedDict):
    id: str
    label: str
    api: str | None
    env_key: str | None
    chat: bool
    embeddings: bool
    chat_models: list[ModelInfo]
    embedding_models: list[ModelInfo]


_SDK_BY_PROTOCOL: dict[Protocol, str] = {
    "chat": "@ai-sdk/openai-compatible",
    "responses": "@ai-sdk/openai",
    "messages": "@ai-sdk/anthropic",
    "google": "@ai-sdk/google",
}


def _m(
    id: str,
    label: str,
    *,
    free: bool = False,
    dims: int | None = None,
    protocol: Protocol = "chat",
    china_gated: bool = False,
) -> ModelInfo:
    return {
        "id": id,
        "label": label,
        "free": free,
        "dims": dims,
        "protocol": protocol,
        "sdk": _SDK_BY_PROTOCOL.get(protocol, "@ai-sdk/openai-compatible"),
        "china_gated": china_gated,
    }


def _ms(
    ids: list[str],
    protocol: Protocol = "chat",
    china_gated: bool = False,
) -> list[ModelInfo]:
    return [_m(i, i, protocol=protocol, china_gated=china_gated) for i in ids]


PROVIDERS: list[ProviderInfo] = [
    {
        "id": "opencode",
        "label": "OpenCode Zen",
        "api": "https://opencode.ai/zen/v1",
        "env_key": "OPENCODE_API_KEY",
        "chat": True,
        "embeddings": False,
        "chat_models": [
            # OpenAI-compatible (chat/completions)
            *_ms(["deepseek-v4-flash", "deepseek-v4-pro"], china_gated=True),
            _m("deepseek-v4-flash-free", "deepseek-v4-flash-free", free=True, china_gated=True),
            *_ms(["minimax-m3", "minimax-m2.7", "minimax-m2.5"]),
            *_ms(["glm-5.2", "glm-5.1", "glm-5"]),
            *_ms(["kimi-k3", "kimi-k2.7-code", "kimi-k2.6", "kimi-k2.5"]),
            _m("mimo-v2.5-free", "mimo-v2.5-free", free=True),
            _m("hy3-free", "hy3-free", free=True),
            _m("laguna-s-2.1-free", "laguna-s-2.1-free", free=True),
            _m("big-pickle", "big-pickle", free=True),
            _m("nemotron-3-ultra-free", "nemotron-3-ultra-free", free=True),
            _m("nemotron-3.5-lightning-free", "nemotron-3.5-lightning-free", free=True),
            # OpenAI Responses (responses)
            *_ms(
                [
                    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.5-pro",
                    "gpt-5.4", "gpt-5.4-pro", "gpt-5.4-mini", "gpt-5.4-nano",
                    "gpt-5.3-codex", "gpt-5.3-codex-spark", "gpt-5.2", "gpt-5.2-codex",
                    "gpt-5.1", "gpt-5.1-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini",
                    "gpt-5", "gpt-5-codex", "gpt-5-nano",
                    "grok-4.6", "grok-4.5", "grok-build-0.1", "muse-spark-1.2",
                ],
                protocol="responses",
            ),
            # Anthropic Messages (messages)
            *_ms(
                [
                    "claude-fable-5", "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
                    "claude-opus-4-6", "claude-opus-4-5", "claude-sonnet-5", "claude-sonnet-4-6",
                    "claude-sonnet-4-5", "claude-haiku-4-5",
                ],
                protocol="messages",
            ),
            *_ms(
                ["qwen3.7-max", "qwen3.7-plus", "qwen3.6-plus", "qwen3.5-plus"],
                protocol="messages",
            ),
            # Gemini (google)
            *_ms(
                [
                    "gemini-3.7-flash",
                    "gemini-3.6-flash",
                    "gemini-3.5-flash",
                    "gemini-3.5-flash-lite",
                    "gemini-3.1-pro",
                    "gemini-3-flash",
                ],
                protocol="google",
            ),
        ],
        "embedding_models": [],
    },
    {
        "id": "opencode-go",
        "label": "OpenCode Go (assinatura)",
        "api": "https://opencode.ai/zen/go/v1",
        "env_key": "OPENCODE_API_KEY",
        "chat": True,
        "embeddings": False,
        "chat_models": [
            # OpenAI-compatible (chat/completions) — baratos/volumosos, ideais p/ agentes/evals
            *_ms(["mimo-v2.5", "mimo-v2.5-pro", "hy3"]),
            *_ms(["deepseek-v4-flash", "deepseek-v4-pro"], china_gated=True),
            *_ms(["glm-5.3", "glm-5.2", "glm-5.1", "kimi-k3", "kimi-k2.7-code", "kimi-k2.6"]),
            # OpenAI Responses
            *_ms(["grok-4.5", "gpt-5.6-luna"], protocol="responses"),
            # Anthropic Messages
            *_ms(
                [
                    "minimax-m3",
                    "minimax-m2.7",
                    "minimax-m2.5",
                    "qwen3.8-max",
                    "qwen3.7-max",
                    "qwen3.7-plus",
                    "qwen3.6-plus",
                ],
                protocol="messages",
            ),
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
            _m("gpt-4o-mini", "GPT-4o mini", protocol="responses"),
            _m("gpt-4o", "GPT-4o", protocol="responses"),
        ],
        "embedding_models": [_m("text-embedding-3-small", "text-embedding-3-small", dims=768)],
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "api": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "chat": True,
        "embeddings": False,
        "chat_models": [
            _m("claude-3-5-haiku-latest", "Claude 3.5 Haiku", protocol="messages"),
            _m("claude-sonnet-4-20250514", "Claude Sonnet 4", protocol="messages"),
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
            _m("gemini-2.0-flash", "Gemini 2.0 Flash", protocol="chat"),
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
            _m("llama-3.3-70b-versatile", "Llama 3.3 70B", protocol="chat"),
            _m("qwen-2.5-coder-32b", "Qwen 2.5 Coder 32B", protocol="chat"),
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
            _m("gemini-2.0-flash-001", "Gemini 2.0 Flash", protocol="google"),
        ],
        "embedding_models": [_m("text-embedding-005", "text-embedding-005", dims=768)],
    },
    {
        "id": "fastembed",
        "label": "FastEmbed (self-hosted, free)",
        "api": None,
        "env_key": None,
        "chat": False,
        "embeddings": True,
        "chat_models": [],
        "embedding_models": [_m("nomic-ai/nomic-embed-text-v1.5", "nomic-embed-text v1.5 (ONNX)", dims=768)],
    },
    {
        "id": "lmstudio",
        "label": "LM Studio (local)",
        "api": "http://127.0.0.1:1234/v1",
        "env_key": "LM_STUDIO_BASE_URL",
        "chat": True,
        "embeddings": True,
        "chat_models": [_m("google/gemma-3-4b", "Gemma 3 4B (local)", protocol="chat")],
        "embedding_models": [_m("text-embedding-nomic-embed-text-v1.5", "nomic-embed-text v1.5", dims=768)],
    },
    {
        "id": "ollama",
        "label": "Ollama (local)",
        "api": "http://127.0.0.1:11434/v1",
        "env_key": "OLLAMA_BASE_URL",
        "chat": True,
        "embeddings": True,
        "chat_models": [_m("gemma3:4b", "Gemma 3 4B (local)", protocol="chat")],
        "embedding_models": [_m("nomic-embed-text", "nomic-embed-text", dims=768)],
    },
    {
        "id": "custom",
        "label": "OpenAI-compatible (custom)",
        "api": None,  # usa LLM_BASE_URL / EMBEDDING_BASE_URL
        "env_key": "LLM_BASE_URL / LLM_API_KEY",
        "chat": True,
        "embeddings": True,
        "chat_models": [],  # modelo livre (campo texto na UI)
        "embedding_models": [],
    },
]


def get_registry() -> list[ProviderInfo]:
    return [dict(p) for p in PROVIDERS]


def resolve_provider(provider_id: str) -> ProviderInfo:
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return p
    raise ValueError(f"provider desconhecido: {provider_id}")


def resolve_model_protocol(provider_id: str, model_id: str) -> Protocol:
    try:
        provider = resolve_provider(provider_id)
    except ValueError:
        return "chat"
    for model in provider["chat_models"]:
        if model["id"] == model_id:
            return model.get("protocol", "chat")
    return "chat"


def require_chat_model(provider_id: str, model_id: str) -> None:
    p = resolve_provider(provider_id)
    if not p["chat"]:
        raise ValueError(f"provider '{provider_id}' não oferece chat (use fastembed só p/ embeddings)")
    ids = {m["id"] for m in p["chat_models"]}
    if not ids:
        return  # free-form provider (e.g. `custom`) — any model id is valid
    if model_id not in ids:
        raise ValueError(f"modelo de chat '{model_id}' não listado para '{provider_id}'")


def require_embedding_model(provider_id: str, model_id: str, *, dims: int) -> None:
    p = resolve_provider(provider_id)
    if not p["embeddings"]:
        raise ValueError(
            f"provider '{provider_id}' não oferece embeddings — use openai/lmstudio/fastembed/vertex"
        )
    if not p["embedding_models"]:
        return  # free-form provider (e.g. `custom`)
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
