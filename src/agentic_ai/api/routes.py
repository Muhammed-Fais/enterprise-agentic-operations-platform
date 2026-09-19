from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agentic_ai.agents import build_agent_graph
from agentic_ai.audit import record_event
from agentic_ai.auth import AuthContext, get_auth_context
from agentic_ai.config import get_settings
from agentic_ai.controls import (
    BudgetExceeded,
    RateLimitExceeded,
    RedisControls,
    RedisControlsUnavailable,
)
from agentic_ai.db.session import get_session
from agentic_ai.embeddings import Embedder
from agentic_ai.guardrails import detect_prompt_injection, mask_pii
from agentic_ai.ingestion import (
    IngestionQueue,
    IngestionService,
    LoadedDocument,
    chunk_text,
    create_ingestion_job,
    get_ingestion_job,
)
from agentic_ai.mcp import MCPStatusClient, PersistentToolAuthorization
from agentic_ai.retrieval.contracts import AccessContext
from agentic_ai.retrieval.pgvector import PgVectorRetriever

from .dependencies import (
    get_answer_model,
    get_embedder,
    get_ingestion_queue,
    get_mcp_status_client,
    get_observability,
    get_redis_controls,
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
    IngestionJobResponse,
    IngestionJobStatusResponse,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
)

router = APIRouter(prefix="/v1")


async def enforce_rate_limit(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    controls: RedisControls = Depends(get_redis_controls),
) -> None:
    try:
        await controls.enforce_rate_limit(auth.tenant_id, auth.subject_id, request.url.path)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": str(exc), "retry_after_seconds": exc.retry_after},
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except RedisControlsUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


async def enforce_agent_budget(
    auth: AuthContext = Depends(get_auth_context),
    controls: RedisControls = Depends(get_redis_controls),
) -> None:
    try:
        await controls.reserve_agent_budget(auth.tenant_id)
    except BudgetExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": str(exc), "retry_after_seconds": exc.retry_after},
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except RedisControlsUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/documents", response_model=DocumentIngestResponse, status_code=201)
async def ingest_document(
    request: DocumentIngestRequest,
    http_request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
    _: None = Depends(enforce_rate_limit),
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


@router.post("/ingestion/jobs", response_model=IngestionJobResponse, status_code=202)
async def submit_ingestion_job(
    request: DocumentIngestRequest,
    http_request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    queue: IngestionQueue = Depends(get_ingestion_queue),
    _: None = Depends(enforce_rate_limit),
) -> IngestionJobResponse:
    masked = mask_pii(request.content)
    document = LoadedDocument(
        external_id=request.external_id,
        title=request.title,
        source=request.source,
        content=masked.text,
    )
    metadata = {**request.metadata, "pii_masked": str(bool(masked.counts)).lower()}
    job_id = await create_ingestion_job(
        session,
        tenant_id=auth.tenant_id,
        document=document,
        allowed_subjects=request.allowed_subjects or [auth.subject_id],
        metadata=metadata,
        max_attempts=get_settings().ingestion_max_attempts,
    )
    try:
        await queue.enqueue(job_id, auth.tenant_id)
    except Exception as exc:
        await session.execute(
            text("UPDATE ingestion_jobs SET status = 'failed', error_message = :error, finished_at = now() WHERE id = :id"),
            {"id": job_id, "error": "queue unavailable"},
        )
        await session.commit()
        raise HTTPException(status_code=503, detail="ingestion queue unavailable") from exc
    await record_event(
        session,
        auth,
        http_request.state.request_id,
        "ingestion.queued",
        {"job_id": str(job_id), "source": request.source},
    )
    return IngestionJobResponse(job_id=str(job_id), status="queued")


@router.get("/ingestion/jobs/{job_id}", response_model=IngestionJobStatusResponse)
async def get_ingestion_job_status(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(enforce_rate_limit),
) -> IngestionJobStatusResponse:
    job = await get_ingestion_job(session, job_id, auth.tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ingestion job not found")
    row = (
        await session.execute(
            text("SELECT documents_processed FROM ingestion_jobs WHERE id = :id"),
            {"id": job_id},
        )
    ).mappings().one()
    return IngestionJobStatusResponse(
        job_id=str(job.job_id),
        status=job.status,
        documents_processed=row["documents_processed"],
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        error_message=job.error_message,
    )


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    http_request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder),
    observability=Depends(get_observability),
    _: None = Depends(enforce_rate_limit),
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
    _: None = Depends(enforce_rate_limit),
    __: None = Depends(enforce_agent_budget),
) -> AgentResponse:
    graph = build_agent_graph(
        PgVectorRetriever(session, embedder, observability),
        status_tool=mcp_status_client.get_incident_status,
        answer_model=answer_model.answer,
    )
    masked_query = mask_pii(request.query).text
    injection = detect_prompt_injection(masked_query)
    if injection.detected:
        await record_event(
            session,
            auth,
            http_request.state.request_id,
            "security.prompt_injection_blocked",
            {"matched_rules": list(injection.matched_rules)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request blocked by prompt-injection guardrail",
        )
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
            "degraded": bool(output.get("degraded")),
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
        degraded=bool(result.get("degraded")),
    )


@router.post("/actions/request-approval", response_model=ApprovalResponse)
async def request_action_approval(
    request: ApprovalRequest,
    http_request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    authorization: PersistentToolAuthorization = Depends(get_tool_authorization),
    _: None = Depends(enforce_rate_limit),
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
    _: None = Depends(enforce_rate_limit),
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
