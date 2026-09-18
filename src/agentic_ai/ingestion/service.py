import hashlib
import json
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_ai.embeddings import Embedder

from .chunking import chunk_text
from .loaders import LoadedDocument


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class IngestionService:
    def __init__(self, session: AsyncSession, embedder: Embedder):
        self.session = session
        self.embedder = embedder

    async def ingest(
        self,
        document: LoadedDocument,
        *,
        tenant_id: str,
        allowed_subjects: list[str],
        metadata: dict[str, str] | None = None,
    ) -> UUID:
        chunks = chunk_text(document.content)
        document_metadata = metadata or {}

        result = await self.session.execute(
            text(
                """
                INSERT INTO documents
                    (id, tenant_id, external_id, title, source, content_hash,
                     allowed_subjects, metadata)
                VALUES
                    (:id, :tenant_id, :external_id, :title, :source, :content_hash,
                     :allowed_subjects, CAST(:metadata AS jsonb))
                ON CONFLICT (tenant_id, external_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    source = EXCLUDED.source,
                    content_hash = EXCLUDED.content_hash,
                    allowed_subjects = EXCLUDED.allowed_subjects,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "external_id": document.external_id,
                "title": document.title,
                "source": document.source,
                "content_hash": _content_hash(document.content),
                "allowed_subjects": allowed_subjects,
                "metadata": json.dumps(document_metadata),
            },
        )
        document_id = result.scalar_one()

        for chunk in chunks:
            embedding = await self.embedder.embed(chunk.content)
            await self.session.execute(
                text(
                    """
                    INSERT INTO document_chunks
                        (id, document_id, chunk_index, content, content_hash, embedding, metadata)
                    VALUES
                        (:id, :document_id, :chunk_index, :content, :content_hash,
                         CAST(:embedding AS vector), CAST(:metadata AS jsonb))
                    ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                        content = EXCLUDED.content,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                    """
                ),
                {
                    "id": uuid4(),
                    "document_id": document_id,
                    "chunk_index": chunk.index,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "embedding": str(embedding),
                    "metadata": json.dumps({"title": document.title}),
                },
            )
        await self.session.commit()
        return document_id
