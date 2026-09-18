from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .contracts import AccessContext, SearchResult


class PgVectorRetriever:
    """Permission-aware retrieval boundary for PostgreSQL + pgvector.

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
            SELECT c.id AS chunk_id, c.document_id, c.content, c.source,
                   1 - (c.embedding <=> :vector) AS score, c.metadata
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.tenant_id = :tenant_id
              AND d.allowed_subjects @> ARRAY[:subject_id]::text[]
            ORDER BY c.embedding <=> :vector
            LIMIT :limit
            """
        )
        rows = await self.session.execute(
            statement,
            {
                "vector": str(vector),
                "tenant_id": access.tenant_id,
                "subject_id": access.subject_id,
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
