from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_ai.agents import build_agent_graph
from agentic_ai.audit import record_event
from agentic_ai.auth import AuthContext, get_auth_context
from agentic_ai.db.session import get_session
from agentic_ai.embeddings import Embedder
from agentic_ai.guardrails import mask_pii
from agentic_ai.ingestion import IngestionService, LoadedDocument, chunk_text
from agentic_ai.mcp import MCPStatusClient, PersistentToolAuthorization
from agentic_ai.retrieval.contracts import AccessContext
from agentic_ai.retrieval.pgvector import PgVectorRetriever

from .dependencies import (
    get_answer_model,
    get_embedder,
    get_mcp_status_client,
    get_observability,
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
    http_request: Request,
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
    await record_event(
        session,
        auth,
        http_request.state.request_id,
        "document.ingested",
        {"document_id": str(document_id), "chunks_created": len(chunk_text(masked.text))},
    )
    return DocumentIngestResponse(
        document_id=str(document_id),
        chunks_created=len(chunk_text(masked.text)),
    )


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    http_request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
    observability=Depends(get_observability),
) -> SearchResponse:
    results = await PgVectorRetriever(session, embedder, observability).search(
        mask_pii(request.query).text,
        AccessContext(
            tenant_id=auth.tenant_id,
            subject_id=auth.subject_id,
            roles=auth.roles,
        ),
        limit=request.limit,
    )
    await record_event(
        session,
        auth,
        http_request.state.request_id,
        "retrieval.completed",
        {"result_count": len(results), "limit": request.limit},
    )
    return SearchResponse(
        results=[SearchResultResponse(**result.__dict__) for result in results]
    )


@router.post("/agent/run", response_model=AgentResponse)
async def run_agent(
    request: AgentRequest,
    http_request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
    answer_model=Depends(get_answer_model),
    mcp_status_client=Depends(get_mcp_status_client),
    observability=Depends(get_observability),
) -> AgentResponse:
    graph = build_agent_graph(
        PgVectorRetriever(session, embedder, observability),
        status_tool=mcp_status_client.get_incident_status,
        answer_model=answer_model.answer,
    )
    masked_query = mask_pii(request.query).text
    result = await observability.observe(
        name="agent.run",
        as_type="agent",
        input_data={"query": masked_query},
        metadata={"tenant_id": auth.tenant_id, "subject_id": auth.subject_id},
        operation=lambda: graph.ainvoke(
            {
                "query": masked_query,
                "access": AccessContext(auth.tenant_id, auth.subject_id, auth.roles),
            }
        ),
        output_builder=lambda output: {
            "citation_count": len(output.get("citations", [])),
            "has_live_status": bool(output.get("live_status")),
        },
    )
    await record_event(
        session,
        auth,
        http_request.state.request_id,
        "agent.completed",
        {"citation_count": len(result.get("citations", [])), "live_status": bool(result.get("live_status"))},
    )
    return AgentResponse(
        answer=result["answer"],
        citations=result.get("citations", []),
        live_status=result.get("live_status"),
    )


@router.post("/actions/request-approval", response_model=ApprovalResponse)
async def request_action_approval(
    request: ApprovalRequest,
    http_request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    authorization: PersistentToolAuthorization = Depends(get_tool_authorization),
) -> ApprovalResponse:
    try:
        token = await authorization.request_approval(session, auth, request.tool_name, request.arguments)
        await record_event(
            session,
            auth,
            http_request.state.request_id,
            "action.approval_requested",
            {"tool_name": request.tool_name, "expires_in_seconds": 300},
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ApprovalResponse(approval_token=token)


@router.post("/actions/execute", response_model=ActionExecuteResponse)
async def execute_action(
    request: ActionExecuteRequest,
    http_request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    authorization: PersistentToolAuthorization = Depends(get_tool_authorization),
    mcp_client: MCPStatusClient = Depends(get_mcp_status_client),
) -> ActionExecuteResponse:
    if request.tool_name != "create_incident_ticket":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported action")
    required = {"title", "description"}
    if set(request.arguments) != required:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid ticket arguments",
        )
    try:
        cached = await authorization.get_idempotent_result(
            session, auth, request.tool_name, request.arguments, request.idempotency_key
        )
        if cached is not None:
            return ActionExecuteResponse(result=cached)
        await authorization.authorize(
            session,
            auth,
            request.tool_name,
            request.arguments,
            approval_token=request.approval_token,
            idempotency_key=request.idempotency_key,
        )
    except PermissionError as exc:
        code = status.HTTP_409_CONFLICT if "idempotency" in str(exc) else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    try:
        result = await mcp_client.create_incident_ticket(
            str(request.arguments["title"]),
            str(request.arguments["description"]),
            request.idempotency_key,
        )
    except Exception as exc:
        await authorization.fail(session, auth, request.idempotency_key, str(exc))
        await record_event(
            session,
            auth,
            http_request.state.request_id,
            "action.failed",
            {"tool_name": request.tool_name, "idempotency_key": request.idempotency_key},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="action execution failed") from exc
    await authorization.complete(session, auth, request.idempotency_key, result)
    await record_event(
        session,
        auth,
        http_request.state.request_id,
        "action.completed",
        {"tool_name": request.tool_name, "idempotency_key": request.idempotency_key},
    )
    return ActionExecuteResponse(result=result)
