"""pgvector adapter for the VectorStore port (PostgreSQL).

Uses the same async engine/session as the rest of the app — one database,
relational + vector. Supports hybrid search: cosine ANN (`<=>`) merged with
PostgreSQL full-text search (tsvector/ts_rank) so keywords not in the
embedding space still match (e.g. company acronyms, Portuguese verb forms).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from textwrap import dedent
from uuid import UUID, uuid4

from sqlalchemy import text

from risklens.domain.entities import ChunkInput, RetrievedChunk
from risklens.infrastructure.db.session import SessionFactory


class PgVectorStore:
    async def upsert_chunks(
        self, chunks: list[ChunkInput], embeddings: list[list[float]]
    ) -> None:
        if not chunks:
            return
        async with SessionFactory() as session:
            stmt = text(
                dedent(
                    """
                    INSERT INTO chunks (id, document_id, chunk_index, content, embedding, metadata, created_at)
                    VALUES (:id, :document_id, :chunk_index, :content, :embedding, :metadata, :created_at)
                    """
                )
            )
            for chunk, emb in zip(chunks, embeddings, strict=True):
                await session.execute(
                    stmt,
                    {
                        "id": uuid4(),
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        # vector literal text: asyncpg encodes str → PG casts to vector
                        "embedding": "[" + ",".join(str(x) for x in emb) + "]",
                        "metadata": json.dumps(chunk.metadata, ensure_ascii=False),
                        "created_at": datetime.now(UTC),
                    },
                )
            await session.commit()

    async def search(
        self,
        query_embedding: list[float],
        *,
        query_text: str | None = None,
        hybrid: bool = True,
        limit: int = 8,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]:
        params: dict = {
            "limit": limit,
            "embedding": "[" + ",".join(str(x) for x in query_embedding) + "]",
            "k_limit": limit * 3,
        }
        where = ""
        if document_id:
            where = "WHERE c.document_id = :document_id"
            params["document_id"] = UUID(document_id)

        vector_sql = text(
            dedent(
                f"""
                SELECT c.document_id, d.title, c.content, 1 - (c.embedding <=> :embedding) AS score,
                       c.metadata
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                {where}
                ORDER BY c.embedding <=> :embedding ASC
                LIMIT :k_limit
                """
            )
        )

        rows_by_doc: dict[str, dict] = {}

        async with SessionFactory() as session:
            vector_rows = (await session.execute(vector_sql, params)).all()
            for r in vector_rows:
                key = f"{r.document_id}:{r.content[:120]}"
                rows_by_doc[key] = self._chunk(r, score=float(r.score or 0.0))

            if hybrid and query_text:
                fts_params = dict(params)
                fts_params["q"] = query_text
                fts_sql = text(
                    dedent(
                        f"""
                        SELECT c.document_id, d.title, c.content,
                               ts_rank(to_tsvector('portuguese', c.content),
                                       plainto_tsquery('portuguese', :q)) AS score,
                               c.metadata
                        FROM chunks c
                        JOIN documents d ON d.id = c.document_id
                        {where + ' AND' if where else 'WHERE'}
                            to_tsvector('portuguese', c.content) @@ plainto_tsquery('portuguese', :q)
                        ORDER BY score DESC
                        LIMIT :k_limit
                        """
                    )
                )
                fts_rows = (await session.execute(fts_sql, fts_params)).all()
                for r in fts_rows:
                    key = f"{r.document_id}:{r.content[:120]}"
                    if key not in rows_by_doc:
                        rows_by_doc[key] = self._chunk(r, score=float(r.score or 0.0))
                    else:
                        rows_by_doc[key].score += float(r.score or 0.0)

        ranked = sorted(rows_by_doc.values(), key=lambda c: c.score, reverse=True)
        return ranked[:limit]

    @staticmethod
    def _chunk(row, *, score: float) -> RetrievedChunk:
        meta = row.metadata or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        return RetrievedChunk(
            document_id=row.document_id,
            document_title=row.title,
            content=row.content,
            score=score,
            metadata=meta,
        )

    async def delete_for_document(self, document_id: str) -> None:
        async with SessionFactory() as session:
            await session.execute(
                text("DELETE FROM chunks WHERE document_id = :document_id"),
                {"document_id": UUID(document_id)},
            )
            await session.commit()
