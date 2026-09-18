from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_ai.db.session import get_session
from agentic_ai.embeddings import Embedder
from agentic_ai.ingestion import IngestionService, LoadedDocument, chunk_text
from agentic_ai.retrieval.contracts import AccessContext
from agentic_ai.retrieval.pgvector import PgVectorRetriever

from .dependencies import get_embedder
from .schemas import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
)

router = APIRouter(prefix="/v1")


@router.post("/documents", response_model=DocumentIngestResponse, status_code=201)
async def ingest_document(
    request: DocumentIngestRequest,
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
) -> DocumentIngestResponse:
    document_id = await IngestionService(session, embedder).ingest(
        LoadedDocument(
            external_id=request.external_id,
            title=request.title,
            source=request.source,
            content=request.content,
        ),
        tenant_id=request.tenant_id,
        allowed_subjects=request.allowed_subjects,
        metadata=request.metadata,
    )
    return DocumentIngestResponse(
        document_id=str(document_id),
        chunks_created=len(chunk_text(request.content)),
    )


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
) -> SearchResponse:
    results = await PgVectorRetriever(session, embedder).search(
        request.query,
        AccessContext(
            tenant_id=request.tenant_id,
            subject_id=request.subject_id,
            roles=tuple(request.roles),
        ),
        limit=request.limit,
    )
    return SearchResponse(
        results=[SearchResultResponse(**result.__dict__) for result in results]
    )
