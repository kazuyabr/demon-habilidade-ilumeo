"""Ports — interfaces the application depends on (ports & adapters / hexagonal).

Application services depend on these protocols, never on concrete
implementations. Swapping the LLM provider, vector store, object storage or
queue is a configuration change, not a code change.
"""

from __future__ import annotations

from typing import Protocol

from risklens.domain.entities import ChunkInput, RetrievedChunk


class LLMProvider(Protocol):
    """Adapters: OpenAI-compatible (LM Studio/Ollama/OpenAI/Groq), Anthropic."""

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str: ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def model(self) -> str: ...


class VectorStore(Protocol):
    """Adapters: pgvector (PostgreSQL)."""

    async def upsert_chunks(self, chunks: list[ChunkInput], embeddings: list[list[float]]) -> None: ...

    async def search(
        self,
        query_embedding: list[float],
        *,
        query_text: str | None = None,
        hybrid: bool = True,
        limit: int = 8,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]: ...

    async def delete_for_document(self, document_id: str) -> None: ...


class DocumentStorage(Protocol):
    """Adapters: local filesystem, S3, GCS."""

    async def save(self, filename: str, data: bytes) -> str: ...

    async def read(self, storage_path: str) -> bytes: ...

    async def delete(self, storage_path: str) -> None: ...


class JobQueue(Protocol):
    """Adapters: arq (Redis)."""

    async def enqueue(self, function_name: str, *, _job_id: str, **kwargs) -> None: ...


class Cache(Protocol):
    """Adapters: Redis."""

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...
