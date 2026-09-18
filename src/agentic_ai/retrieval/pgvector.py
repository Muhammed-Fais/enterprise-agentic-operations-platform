from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .contracts import AccessContext, SearchResult


class PgVectorRetriever:
    """Permission-aware hybrid retrieval using pgvector and PostgreSQL FTS.

    Embedding generation is deliberately outside this class so the storage layer
    does not depend on a particular model provider.
    """

    def __init__(self, session: AsyncSession, embedder):
        self.session = session
        self.embedder = embedder

    async def search(
        self, query: str, access: AccessContext, *, limit: int = 8
    ) -> list[SearchResult]:
        vector = await self.embedder.embed(query)
        statement = text(
            """
            WITH vector_results AS (
                SELECT c.id AS chunk_id, c.document_id, c.content, d.source, c.metadata,
                       1 - (c.embedding <=> CAST(:vector AS vector)) AS vector_score
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.tenant_id = :tenant_id
                  AND d.allowed_subjects @> ARRAY[:subject_id]::text[]
                  AND c.embedding IS NOT NULL
                ORDER BY c.embedding <=> CAST(:vector AS vector)
                LIMIT :candidate_limit
            ),
            text_results AS (
                SELECT c.id AS chunk_id,
                       ts_rank_cd(c.search_vector, websearch_to_tsquery('english', :query)) AS text_score
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.tenant_id = :tenant_id
                  AND d.allowed_subjects @> ARRAY[:subject_id]::text[]
                  AND c.search_vector @@ websearch_to_tsquery('english', :query)
                ORDER BY text_score DESC
                LIMIT :candidate_limit
            )
            SELECT v.chunk_id, v.document_id, v.content, v.source, v.metadata,
                   (0.7 * v.vector_score + 0.3 * COALESCE(t.text_score, 0)) AS score
            FROM vector_results v
            LEFT JOIN text_results t ON t.chunk_id = v.chunk_id
            ORDER BY score DESC
            LIMIT :limit
            """
        )
        rows = await self.session.execute(
            statement,
            {
                "vector": str(vector),
                "tenant_id": access.tenant_id,
                "subject_id": access.subject_id,
                "query": query,
                "candidate_limit": max(limit * 4, 20),
                "limit": limit,
            },
        )
        return [
            SearchResult(
                chunk_id=str(row.chunk_id),
                document_id=str(row.document_id),
                text=row.content,
                score=float(row.score),
                source=row.source,
                metadata=row.metadata or {},
            )
            for row in rows
        ]
