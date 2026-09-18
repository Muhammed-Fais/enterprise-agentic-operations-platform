from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_ai.auth import AuthContext, get_auth_context
from agentic_ai.db.session import get_session
from agentic_ai.embeddings import Embedder
from agentic_ai.guardrails import mask_pii
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
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
) -> DocumentIngestResponse:
    masked = mask_pii(request.content)
    allowed_subjects = request.allowed_subjects or [auth.subject_id]
    document_id = await IngestionService(session, embedder).ingest(
        LoadedDocument(
            external_id=request.external_id,
            title=request.title,
            source=request.source,
            content=masked.text,
        ),
        tenant_id=auth.tenant_id,
        allowed_subjects=allowed_subjects,
        metadata={**request.metadata, "pii_masked": str(bool(masked.counts)).lower()},
    )
    return DocumentIngestResponse(
        document_id=str(document_id),
        chunks_created=len(chunk_text(masked.text)),
    )


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
) -> SearchResponse:
    results = await PgVectorRetriever(session, embedder).search(
        mask_pii(request.query).text,
        AccessContext(
            tenant_id=auth.tenant_id,
            subject_id=auth.subject_id,
            roles=auth.roles,
        ),
        limit=request.limit,
    )
    return SearchResponse(
        results=[SearchResultResponse(**result.__dict__) for result in results]
    )
