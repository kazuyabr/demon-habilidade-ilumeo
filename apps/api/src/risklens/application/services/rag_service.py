"""RAG service: retrieval-augmented question answering with citations.

Query → embed → hybrid search (vector + FTS) → grounded prompt with numbered
sources → answer that cites [n]. The model is instructed to answer "não
encontrado nos documentos" rather than hallucinate when context is empty.
"""

from __future__ import annotations

from uuid import UUID

from risklens.application.ports import LLMProvider, VectorStore
from risklens.core.config import settings
from risklens.domain.entities import RetrievedChunk

MAX_CONTEXT_CHARS = 8000


def _format_context(chunks: list[RetrievedChunk]) -> tuple[str, list[dict]]:
    parts: list[str] = []
    citations: list[dict] = []
    used = 0
    for i, c in enumerate(chunks, start=1):
        snippet = c.content[:2000]
        if used + len(snippet) > MAX_CONTEXT_CHARS:
            break
        parts.append(f"[{i}] {c.document_title}:\n{snippet}")
        citations.append(
            {
                "index": i,
                "document_id": str(c.document_id),
                "document_title": c.document_title,
                "snippet": snippet[:400],
                "score": round(c.score, 3),
            }
        )
        used += len(snippet)
    return "\n\n".join(parts), citations


async def ask(
    llm: LLMProvider,
    vector_store: VectorStore,
    *,
    question: str,
    document_id: UUID | None = None,
) -> dict:
    embedding = (await llm.embed_texts([question]))[0]
    chunks = await vector_store.search(
        embedding,
        query_text=question,
        hybrid=settings.ff_rag_hybrid_search,
        limit=6,
        document_id=str(document_id) if document_id else None,
    )

    context, citations = _format_context(chunks)

    if not chunks:
        answer = "Não encontrei informação suficiente nos documentos indexados para responder."
    else:
        system = (
            "Você é um assistente de inteligência de risco. Responda SOMENTE com base no contexto "
            "fornecido, citando a fonte entre colchetes [n]. Se a informação não estiver no contexto, "
            "responda que não foi encontrada. Seja conciso e objetivo."
        )
        user = f"Contexto:\n---\n{context}\n---\n\nPergunta: {question}"
        answer = await llm.complete(system=system, user=user)

    return {
        "question": question,
        "answer": answer,
        "citations": citations,
        "grounded": bool(chunks),
    }
