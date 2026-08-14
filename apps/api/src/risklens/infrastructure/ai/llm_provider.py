"""Provider adapters behind the ``LLMProvider`` and ``EmbeddingProvider`` ports.

Chat and embeddings are **decoupled**: ``LLM_PROVIDER`` picks the generator,
``EMBEDDING_PROVIDER`` picks the embedder — RAG can use a keyless/self-hosted
embedder (fastembed) while chat uses OpenCode Zen (free) or any cloud provider.

Chat adapters
  - OpenAICompatibleProvider  (OpenCode Zen, OpenAI, Groq, Google Gemini,
                               LM Studio, Ollama, vLLM, any OpenAI-compatible API)
  - AnthropicProvider         (Anthropic Messages API)
  - VertexProvider            (Google Vertex AI via google-genai, GCP-native)

Embedding adapters
  - OpenAICompatibleEmbeddings (OpenAI text-embedding-3-small @768, LM Studio nomic)
  - FastEmbedProvider          (self-hosted ONNX, keyless, 768 dims)
  - VertexProvider             (text-embedding-005 @768)

All embedding models produce 768 dims on purpose — pgvector stays vector(768).
"""

from __future__ import annotations

import asyncio
import contextlib

from openai import AsyncOpenAI
from opentelemetry import trace

from risklens.application.ports import EmbeddingProvider, LLMProvider
from risklens.core.config import settings
from risklens.infrastructure.ai import registry, runtime

_tracer = trace.get_tracer("risklens.ai")


class _BaseProvider:
    model: str

    async def _span(self, name: str, *, system: str | None = None, user: str | None = None) -> trace.Span:
        span = _tracer.start_span(name)
        span.set_attribute("gen_ai.request.model", self.model)
        if system:
            span.set_attribute("gen_ai.prompt.system", system[:2000])
        if user:
            span.set_attribute("gen_ai.prompt.user", user[:4000])
        return span


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider(_BaseProvider):
    """OpenAI-compatible chat: OpenCode Zen, OpenAI, Groq, Google Gemini,
    LM Studio, Ollama, vLLM, custom gateways."""

    def __init__(self, *, base_url: str, api_key: str, model: str):
        self.base_url = base_url
        self.model = model
        # Retry 429/5xx with exponential backoff — free tiers (OpenCode Zen) rate-limit bursts
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=6, timeout=60.0)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        span = await self._span("llm.complete", system=system, user=user)
        try:
            cfg = runtime.get_cached_config()
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens or cfg["max_tokens"],
                temperature=temperature if temperature is not None else cfg["temperature"],
            )
            content = resp.choices[0].message.content or ""
            if resp.usage:
                span.set_attribute("gen_ai.usage.completion_tokens", resp.usage.completion_tokens)
                span.set_attribute("gen_ai.usage.prompt_tokens", resp.usage.prompt_tokens)
            return content
        finally:
            span.end()


class AnthropicProvider(_BaseProvider):
    """Anthropic Messages API — the provider itself or OpenCode Zen/Go
    (which expose the same ``/v1/messages`` shape)."""

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None):
        from anthropic import AsyncAnthropic

        self.model = model
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        span = await self._span("llm.complete", system=system, user=user)
        try:
            cfg = runtime.get_cached_config()
            resp = await self._client.messages.create(
                model=self.model,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=max_tokens or cfg["max_tokens"],
                temperature=temperature if temperature is not None else cfg["temperature"],
            )
            return "".join(block.text for block in resp.content if block.type == "text")
        finally:
            span.end()


class VertexProvider(_BaseProvider):
    """Google Vertex AI (enterprise/GCP) — chat (Gemini) + embeddings, via google-genai.

    Auth: VERTEX_API_KEY when set; otherwise Application Default Credentials
    (Workload Identity in Cloud Run). Requires the Vertex AI API enabled.
    """

    def __init__(
        self,
        *,
        project: str,
        region: str,
        api_key: str,
        model: str,
        embedding_model: str,
        dims: int,
    ):
        self.project = project
        self.region = region
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.dims = dims
        self._client = None

    def _get(self):
        if self._client is None:
            from google import genai

            kwargs = {"vertexai": True, "project": self.project, "location": self.region}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._client = genai.Client(**kwargs)
        return self._client

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        from google.genai import types

        client = self._get()
        span = await self._span("llm.complete", system=system, user=user)
        try:
            cfg = runtime.get_cached_config()
            resp = await client.aio.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens or cfg["max_tokens"],
                    temperature=temperature if temperature is not None else cfg["temperature"],
                ),
            )
            return resp.text or ""
        finally:
            span.end()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types

        client = self._get()
        span = _tracer.start_span("llm.embed")
        span.set_attribute("gen_ai.request.model", self.embedding_model)
        try:
            resp = await client.aio.models.embed_content(
                model=self.embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=self.dims),
            )
            return [list(map(float, e.values)) for e in resp.embeddings]
        finally:
            span.end()


class OpenAIResponsesProvider(_BaseProvider):
    """OpenAI Responses API (``/v1/responses``) — GPT/Grok-class models on
    OpenCode Zen/Go expose this shape."""

    def __init__(self, *, base_url: str, api_key: str, model: str):
        self.model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=6, timeout=60.0)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        span = await self._span("llm.complete", system=system, user=user)
        try:
            cfg = runtime.get_cached_config()
            resp = await self._client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_output_tokens=max_tokens or cfg["max_tokens"],
                temperature=temperature if temperature is not None else cfg["temperature"],
            )
            if hasattr(resp, "output_text"):
                return resp.output_text or ""
            text = ""
            for item in resp.output or []:
                if getattr(item, "type", None) == "message":
                    for c in getattr(item, "content", []) or []:
                        text += getattr(c, "text", "") or ""
            return text
        finally:
            span.end()


class GoogleGeminiProvider(_BaseProvider):
    """Gemini via the google-genai SDK pointed at a gateway base URL
    (``/models/{id}:generateContent``) — used by OpenCode Zen Gemini models."""

    def __init__(self, *, base_url: str, api_key: str, model: str):
        self.model = model
        self._base_url = base_url
        self._api_key = api_key
        self._client = None

    def _get(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(base_url=self._base_url),
            )
        return self._client

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        from google.genai import types

        client = self._get()
        span = await self._span("llm.complete", system=system, user=user)
        try:
            cfg = runtime.get_cached_config()
            resp = await client.aio.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens or cfg["max_tokens"],
                    temperature=temperature if temperature is not None else cfg["temperature"],
                ),
            )
            return resp.text or ""
        finally:
            span.end()


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class OpenAICompatibleEmbeddings:
    """OpenAI-compatible embeddings. ``dims`` (optional) forwards the OpenAI
    ``dimensions`` parameter so text-embedding-3-small can emit exactly 768
    dims; local servers (LM Studio/Ollama) ignore it and already return 768."""

    def __init__(self, *, base_url: str, api_key: str, model: str, dims: int | None):
        self.model = model
        self.dims = dims
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=6, timeout=60.0)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        span = _tracer.start_span("llm.embed")
        span.set_attribute("gen_ai.request.model", self.model)
        try:
            kwargs = {"model": self.model, "input": texts}
            if self.dims:
                kwargs["dimensions"] = self.dims
            resp = await self._client.embeddings.create(**kwargs)
            by_index = {d.index: d.embedding for d in resp.data}
            return [by_index[i] for i in range(len(texts))]
        finally:
            span.end()


class FastEmbedProvider:
    """Self-hosted embeddings (ONNX via fastembed) — keyless, free, runs in the
    container. Model is downloaded on first use into the HF cache."""

    def __init__(self, *, model: str, dims: int):
        self.model = model
        self.dims = dims
        self._embedding = None

    def _get(self):
        if self._embedding is None:
            from fastembed import TextEmbedding

            self._embedding = TextEmbedding(model_name=self.model)
        return self._embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        span = _tracer.start_span("llm.embed")
        span.set_attribute("gen_ai.request.model", self.model)
        try:
            embedder = self._get()
            vectors = await asyncio.to_thread(lambda: list(embedder.embed(texts)))
            return [list(map(float, v)) for v in vectors]
        finally:
            span.end()


# ---------------------------------------------------------------------------
# Endpoint mapping
# ---------------------------------------------------------------------------

_CHAT_ENDPOINTS: dict[str, tuple[str | None, str | None]] = {
    "opencode": ("https://opencode.ai/zen/v1", "opencode_api_key"),
    "opencode-go": ("https://opencode.ai/zen/go/v1", "opencode_api_key"),
    "openai": ("https://api.openai.com/v1", "openai_api_key"),
    "groq": ("https://api.groq.com/openai/v1", "groq_api_key"),
    "google": ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini_api_key"),
    "lmstudio": (None, None),  # base_url = LM_STUDIO_BASE_URL, dummy key
    "ollama": ("http://127.0.0.1:11434/v1", None),
}

_EMBED_ENDPOINTS: dict[str, tuple[str | None, str | None, int | None]] = {
    "openai": ("https://api.openai.com/v1", "openai_api_key", 768),
    "lmstudio": (None, None, None),
    "ollama": ("http://127.0.0.1:11434/v1", None, None),
}


def _resolve_chat_endpoint(provider: str) -> tuple[str, str]:
    if provider in _CHAT_ENDPOINTS:
        base, key_field = _CHAT_ENDPOINTS[provider]
        base_url = base or settings.lm_studio_base_url
        api_key = getattr(settings, key_field) if key_field else "lm-studio"
        return base_url, api_key
    return settings.llm_base_url, settings.llm_api_key  # custom


def _resolve_embed_endpoint(provider: str) -> tuple[str, str, int | None]:
    if provider in _EMBED_ENDPOINTS:
        base, key_field, dims = _EMBED_ENDPOINTS[provider]
        base_url = base or settings.lm_studio_base_url
        api_key = getattr(settings, key_field) if key_field else "lm-studio"
        return base_url, api_key, dims
    return settings.embedding_base_url, settings.embedding_api_key, settings.embedding_dims


# ---------------------------------------------------------------------------
# Factories (env-driven)
# ---------------------------------------------------------------------------


def _strip_v1(url: str) -> str:
    """Anthropic SDK appends '/v1/messages'; strip a trailing /v1 from the
    provider base so opencode/opencode-go messages endpoints line up."""
    stripped = url.rstrip("/")
    if stripped.endswith("/v1"):
        stripped = stripped[: -len("/v1")]
    return stripped or url


def _build_chat(provider: str, model: str) -> LLMProvider:
    if provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key or settings.llm_api_key,
            model=model,
        )
    if provider == "vertex":
        return VertexProvider(
            project=settings.vertex_project,
            region=settings.vertex_region,
            api_key=settings.vertex_api_key,
            model=model,
            embedding_model=str(runtime.get_cached_config()["embedding_model"]),
            dims=settings.embedding_dims,
        )
    protocol = registry.resolve_model_protocol(provider, model)
    base_url, api_key = _resolve_chat_endpoint(provider)
    if protocol == "responses":
        return OpenAIResponsesProvider(base_url=base_url, api_key=api_key, model=model)
    if protocol == "messages":
        return AnthropicProvider(api_key=api_key, model=model, base_url=_strip_v1(base_url))
    if protocol == "google":
        return GoogleGeminiProvider(base_url=base_url, api_key=api_key, model=model)
    return OpenAICompatibleProvider(base_url=base_url, api_key=api_key, model=model)


def build_chat_provider() -> LLMProvider:
    cfg = runtime.get_cached_config()
    provider = str(cfg["chat_provider"]).lower()
    model = str(cfg["chat_model"])
    with contextlib.suppress(ValueError):
        registry.require_chat_model(provider, model)
    return _build_chat(provider, model)


def build_chat_provider_for(provider: str, model: str) -> LLMProvider:
    """Build a chat provider for an explicit (provider, model) — used by the
    settings 'test connection' feature without mutating the active config."""
    return _build_chat(provider.lower(), model)


def build_embedding_provider() -> EmbeddingProvider:
    cfg = runtime.get_cached_config()
    provider = str(cfg["embedding_provider"]).lower()
    model = str(cfg["embedding_model"])
    with contextlib.suppress(ValueError):
        registry.require_embedding_model(provider, model, dims=settings.embedding_dims)

    if provider == "fastembed":
        return FastEmbedProvider(model=model, dims=settings.embedding_dims)
    if provider == "vertex":
        return VertexProvider(
            project=settings.vertex_project,
            region=settings.vertex_region,
            api_key=settings.vertex_api_key,
            model=str(cfg["chat_model"]),
            embedding_model=model,
            dims=settings.embedding_dims,
        )
    base_url, api_key, dims = _resolve_embed_endpoint(provider)
    return OpenAICompatibleEmbeddings(
        base_url=base_url, api_key=api_key, model=model, dims=dims
    )
