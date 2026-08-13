"""Indexing service: chunk → embed → upsert into vector store.

Chunking is markdown-aware (split by sections) with a paragraph fallback.
Overlap preserves context across boundaries. Metadata keeps provenance
(document, section, chunk index) for citations and source filtering.
"""

from __future__ import annotations

import re
from uuid import UUID

from risklens.application.ports import LLMProvider, VectorStore
from risklens.domain.entities import ChunkInput

TARGET_CHARS = 1200
OVERLAP_CHARS = 150


def chunk_text(text: str, *, target_chars: int = TARGET_CHARS, overlap: int = OVERLAP_CHARS) -> list[tuple[str, dict]]:
    """Return [(content, metadata)] with markdown section detection."""
    chunks: list[tuple[str, dict]] = []
    current_section = "intro"

    # Split into sections by markdown headings
    parts = re.split(r"(?m)^(#{1,3}\s+.+)$", text)
    i = 0
    while i < len(parts):
        piece = parts[i]
        if piece.strip().startswith("#") and i + 1 < len(parts):
            heading = piece.strip().lstrip("#").strip()
            current_section = heading
            body = parts[i + 1]
            i += 2
        else:
            body = piece
            i += 1

        for start in range(0, len(body), target_chars - overlap):
            content = body[start : start + target_chars].strip()
            if content:
                chunks.append((content, {"section": current_section}))

    return chunks or [(text[:target_chars], {"section": "intro"})]


async def index_document(
    llm: LLMProvider,
    vector_store: VectorStore,
    *,
    document_id: UUID,
    text: str,
) -> int:
    raw_chunks = chunk_text(text)
    chunks = [
        ChunkInput(document_id=document_id, chunk_index=i, content=content, metadata=meta)
        for i, (content, meta) in enumerate(raw_chunks)
    ]
    if not chunks:
        return 0

    embeddings = await llm.embed_texts([c.content for c in chunks])
    await vector_store.upsert_chunks(chunks, embeddings)
    return len(chunks)
