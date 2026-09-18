from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_ai.agents import build_agent_graph
from agentic_ai.auth import AuthContext, get_auth_context
from agentic_ai.db.session import get_session
from agentic_ai.embeddings import Embedder
from agentic_ai.guardrails import mask_pii
from agentic_ai.ingestion import IngestionService, LoadedDocument, chunk_text
from agentic_ai.mcp import ApprovalRequired, MCPStatusClient, ToolAuthorization
from agentic_ai.retrieval.contracts import AccessContext
from agentic_ai.retrieval.pgvector import PgVectorRetriever

from .dependencies import (
    get_answer_model,
    get_embedder,
    get_mcp_status_client,
    get_tool_authorization,
)
from .schemas import (
    ActionExecuteRequest,
    ActionExecuteResponse,
    AgentRequest,
    AgentResponse,
    ApprovalRequest,
    ApprovalResponse,
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


@router.post("/agent/run", response_model=AgentResponse)
async def run_agent(
    request: AgentRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
    answer_model=Depends(get_answer_model),
    mcp_status_client=Depends(get_mcp_status_client),
) -> AgentResponse:
    graph = build_agent_graph(
        PgVectorRetriever(session, embedder),
        status_tool=mcp_status_client.get_incident_status,
        answer_model=answer_model.answer,
    )
    result = await graph.ainvoke(
        {
            "query": mask_pii(request.query).text,
            "access": AccessContext(auth.tenant_id, auth.subject_id, auth.roles),
        }
    )
    return AgentResponse(
        answer=result["answer"],
        citations=result.get("citations", []),
        live_status=result.get("live_status"),
    )


@router.post("/actions/request-approval", response_model=ApprovalResponse)
async def request_action_approval(
    request: ApprovalRequest,
    auth: AuthContext = Depends(get_auth_context),
    authorization: ToolAuthorization = Depends(get_tool_authorization),
) -> ApprovalResponse:
    try:
        token = authorization.request_approval(auth, request.tool_name, request.arguments)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ApprovalResponse(approval_token=token)


@router.post("/actions/execute", response_model=ActionExecuteResponse)
async def execute_action(
    request: ActionExecuteRequest,
    auth: AuthContext = Depends(get_auth_context),
    authorization: ToolAuthorization = Depends(get_tool_authorization),
    mcp_client: MCPStatusClient = Depends(get_mcp_status_client),
) -> ActionExecuteResponse:
    try:
        authorization.authorize(
            auth,
            request.tool_name,
            request.arguments,
            approval_token=request.approval_token,
            idempotency_key=request.idempotency_key,
        )
    except ApprovalRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "human approval required", "approval_token": exc.approval_token},
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if request.tool_name != "create_incident_ticket":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported action")
    required = {"title", "description"}
    if set(request.arguments) != required:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid ticket arguments",
        )
    result = await mcp_client.create_incident_ticket(
        str(request.arguments["title"]),
        str(request.arguments["description"]),
        request.idempotency_key,
    )
    return ActionExecuteResponse(result=result)
