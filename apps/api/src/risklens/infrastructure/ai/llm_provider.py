"""LLM provider adapters behind the ``LLMProvider`` port.

``OpenAICompatibleProvider`` talks to any OpenAI-compatible endpoint
(LM Studio, Ollama /v1, OpenAI, Groq, vLLM). ``AnthropicProvider`` is the
non-compatible alternative. The factory picks by ``LLM_PROVIDER`` env var —
providers are interchangeable without touching application code.
"""

from __future__ import annotations

from openai import AsyncOpenAI
from opentelemetry import trace

from risklens.application.ports import LLMProvider
from risklens.core.config import settings

_tracer = trace.get_tracer("risklens.ai")


class _BaseProvider:
    model: str

    async def _span(
        self, name: str, *, system: str | None = None, user: str | None = None
    ) -> trace.Span:
        span = _tracer.start_span(name)
        span.set_attribute("gen_ai.system", "llm")
        span.set_attribute("gen_ai.request.model", self.model)
        if system:
            span.set_attribute("gen_ai.prompt.system", system[:2000])
        if user:
            span.set_attribute("gen_ai.prompt.user", user[:4000])
        return span


class OpenAICompatibleProvider(_BaseProvider):
    """Works with LM Studio, Ollama, OpenAI, Groq, vLLM, etc."""

    def __init__(self, *, base_url: str, api_key: str, model: str, embedding_model: str):
        self.base_url = base_url
        self.model = model
        self.embedding_model = embedding_model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

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
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens or settings.llm_max_tokens,
                temperature=temperature if temperature is not None else settings.llm_temperature,
            )
            content = resp.choices[0].message.content or ""
            span.set_attribute("gen_ai.usage.completion_tokens", resp.usage.completion_tokens if resp.usage else 0)
            span.set_attribute("gen_ai.usage.prompt_tokens", resp.usage.prompt_tokens if resp.usage else 0)
            return content
        finally:
            span.end()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        span = _tracer.start_span("llm.embed")
        span.set_attribute("gen_ai.request.model", self.embedding_model)
        try:
            resp = await self._client.embeddings.create(model=self.embedding_model, input=texts)
            # Preserve input order (LM Studio may return in arbitrary order)
            by_index = {d.index: d.embedding for d in resp.data}
            return [by_index[i] for i in range(len(texts))]
        finally:
            span.end()


class AnthropicProvider(_BaseProvider):
    """Anthropic Messages API (non-OpenAI-compatible)."""

    def __init__(self, *, api_key: str, model: str, embedding_model: str):
        from anthropic import AsyncAnthropic

        self.model = model
        self.embedding_model = embedding_model
        self._client = AsyncAnthropic(api_key=api_key)

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
            resp = await self._client.messages.create(
                model=self.model,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=max_tokens or settings.llm_max_tokens,
                temperature=temperature if temperature is not None else settings.llm_temperature,
            )
            return "".join(block.text for block in resp.content if block.type == "text")
        finally:
            span.end()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Anthropic has no embeddings endpoint; use a compatible provider.")


def build_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            embedding_model=settings.llm_embedding_model,
        )
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        embedding_model=settings.llm_embedding_model,
    )
