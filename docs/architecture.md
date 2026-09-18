# Enterprise Agentic Operations Platform

## 1. Platform architecture

```mermaid
flowchart TB
    U[User / Enterprise Client]
    UI[Web UI or API Client]
    API[FastAPI Gateway]
    AUTH[Authentication + Tenant/RBAC]
    IN[Input Guardrails]
    ORCH[LangGraph Orchestrator]
    ROUTER[Intent + Skill Router]
    PLAN[Workflow Planner]
    RET[Retrieval Service]
    HYBRID[Hybrid Search\nVector + BM25 + Filters]
    DB[(PostgreSQL + pgvector)]
    CACHE[(Redis Cache / Queue)]
    MCP[MCP Tool Gateway]
    TOOLS[Read Tools\nStatus / Search / Metrics]
    WRITE[Write Tools\nTickets / Notifications]
    APPROVAL[Human Approval Gate]
    OUT[Output Guardrails]
    RESP[Answer + Citations + Audit ID]
    TRACE[Tracing / Cost / Audit]

    U --> UI --> API --> AUTH --> IN --> ORCH
    ORCH --> ROUTER --> PLAN
    PLAN --> RET --> HYBRID --> DB
    PLAN --> CACHE
    PLAN --> MCP
    MCP --> TOOLS
    MCP --> APPROVAL --> WRITE
    DB --> OUT
    ORCH --> OUT --> RESP --> UI
    API -. telemetry .-> TRACE
    ORCH -. telemetry .-> TRACE
    MCP -. telemetry .-> TRACE
```

## 2. Incident-response request lifecycle

```mermaid
sequenceDiagram
    actor User
    participant API as API Gateway
    participant Guard as Guardrails
    participant Graph as Agent Graph
    participant RAG as Retrieval
    participant MCP as MCP Gateway
    participant Approval as Approval Service
    participant Audit as Audit/Tracing

    User->>API: Ask incident question
    API->>Guard: Validate input and detect injection/PII
    Guard-->>API: Sanitized request + risk metadata
    API->>Graph: Start workflow
    Graph->>RAG: Retrieve authorized evidence
    RAG-->>Graph: Ranked chunks + citations
    Graph->>MCP: Query read-only status tool
    MCP-->>Graph: Tool result + provenance
    Graph->>Audit: Record plan, retrieval, and tool calls
    Graph-->>User: Investigation summary + citations
    User->>API: Approve ticket creation
    API->>Approval: Validate approval and scope
    Approval->>MCP: Invoke write tool
    MCP-->>Approval: Ticket ID
    Approval->>Audit: Record approval and action
    Approval-->>User: Ticket created
```

## 3. Trust boundaries

```mermaid
flowchart LR
    subgraph Untrusted[Untrusted content]
        Q[User prompt]
        DOC[Retrieved documents]
        EXT[External tool responses]
    end

    subgraph Controls[Security controls]
        SAN[Sanitization]
        PII[PII masking]
        ACL[ACL and tenant filtering]
        INJ[Prompt-injection detection]
        SCHEMA[Strict tool schemas]
        APPROVE[Human approval]
    end

    subgraph Trusted[Controlled execution]
        MODEL[Model reasoning]
        READ[Read-only tools]
        WRITE[Approved write actions]
        LOG[Immutable audit events]
    end

    Q --> SAN --> MODEL
    DOC --> ACL --> INJ --> MODEL
    EXT --> SCHEMA --> MODEL
    MODEL --> PII --> READ
    MODEL --> SCHEMA --> APPROVE --> WRITE
    SAN -.-> LOG
    ACL -.-> LOG
    APPROVE -.-> LOG
```

## 4. Knowledge and evaluation loop

```mermaid
flowchart LR
    SOURCE[Policies / Incidents / Tickets]
    INGEST[Ingestion Worker]
    PARSE[Parse + Normalize]
    CHUNK[Chunk + Metadata]
    EMBED[Embedding Service]
    STORE[(PostgreSQL + pgvector)]
    DATASET[Versioned Evaluation Dataset]
    RUN[Evaluation Runner]
    METRICS[Retrieval / Groundedness / Security Metrics]
    OBS[Observability Dashboard]

    SOURCE --> INGEST --> PARSE --> CHUNK --> EMBED --> STORE
    STORE --> RUN
    DATASET --> RUN --> METRICS --> OBS
    OBS -. regression feedback .-> INGEST
```

## 5. Interview narrative

The platform is intentionally demonstrated through one complete workflow:

1. A user asks about an incident.
2. The system authenticates the user and applies tenant/RBAC filters.
3. The agent retrieves and cites relevant evidence.
4. A read-only MCP tool checks current system status.
5. Guardrails validate the answer and detect unsupported claims.
6. The user approves a ticket action.
7. The write tool runs with a constrained schema.
8. Every retrieval, tool call, approval, cost, and result is auditable.

The architecture can later support customer support, market research, HR, and finance workflows by adding skills and MCP servers without changing the platform security and evaluation layers.
