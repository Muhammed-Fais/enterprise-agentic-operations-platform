# Production Interview Questions and Answers

## Retrieval and RAG

### Why did you choose pgvector?

PostgreSQL already stores the document metadata, tenant ownership, ACLs, and audit relationships. pgvector lets us enforce authorization and perform vector search in the same query boundary. It reduces operational complexity for the first production version while leaving room to move to a dedicated vector engine if benchmarks justify it.

### Why hybrid retrieval instead of vector search alone?

Semantic embeddings are good at meaning, while keyword search is better for exact incident IDs, error codes, product names, and policy terms. The system retrieves candidates using both pgvector cosine similarity and PostgreSQL full-text search, then combines their scores. The weights are configuration and should be tuned against an evaluation set rather than chosen blindly.

### How do you prevent unauthorized data from reaching the model?

Tenant and subject filters are applied inside the retrieval SQL query before chunks are returned. Filtering after retrieval would be unsafe because unauthorized text could already enter the model context. The same access context must also be applied to MCP tools and any cached result.

### How did you choose the embedding model?

We use `sentence-transformers/all-MiniLM-L6-v2` locally. It is free to run, Apache-2.0 licensed, fast enough for local development, and produces 384-dimensional vectors. The model is loaded once and reused; document and query embeddings must use the same model and preprocessing configuration.

### What happens when the embedding model changes?

Embedding model name, revision, dimensions, and normalization settings are stored as deployment metadata. A model change creates a new embedding version, triggers a re-indexing job, and is evaluated before promotion. We do not mix incompatible vector spaces in one index.

### How do you choose chunk size?

Chunking is evaluated empirically. Larger chunks preserve context but increase noise and token cost; smaller chunks improve precision but can lose context. We start with paragraph-aware chunks and overlap, then compare recall, citation completeness, answer groundedness, and latency on a versioned dataset.

### What if retrieval finds nothing useful?

The agent should abstain or ask a clarifying question. It must not invent an answer. A low retrieval score, missing citations, or conflicting sources can route the request to an insufficient-evidence response.

### How do you evaluate retrieval?

We maintain questions with expected documents or chunks and measure Recall@K, MRR, NDCG, ACL correctness, latency, and citation completeness. Retrieval evaluation is separate from answer-generation evaluation so a generation model cannot hide a retrieval regression.

## Agent and MCP design

### Why use an agent instead of a single RAG chain?

The incident workflow has conditional steps: classify the request, retrieve evidence, decide whether a read-only tool is needed, summarize findings, and possibly request approval for a write action. A bounded graph makes those transitions explicit and observable instead of relying on unconstrained model behavior.

### Why MCP?

MCP gives tools a standard boundary with explicit schemas and provenance. The platform can enforce an allowlist, separate read and write capabilities, validate arguments, apply timeouts, and audit every invocation independently of the model.

### How do you prevent an agent from taking dangerous actions?

Write tools are not available on the read-only path. Tool arguments are validated against strict schemas, permissions are checked again at execution time, destructive actions require human approval, and every action has an idempotency key and audit event.

### Is Redis a log platform?

No. Redis is an in-memory data store. In this platform it is useful for retrieval caching, asynchronous ingestion queues, rate limiting, short-lived approval state, workflow checkpoints, and distributed locks. Application logs should be emitted as structured events and sent to an observability or log backend. PostgreSQL remains the durable store for documents, audit records, and business data.

### Why not store logs in Redis?

Redis is optimized for fast temporary access, not durable log retention, compliance retention, search, or long-term analysis. Redis can hold short-lived counters or queue messages, but audit events and production logs need durable storage, retention policies, access controls, and backups.

### How do you protect a public repository?

Secrets are excluded through `.gitignore`, while `.env.example` documents required configuration without real values. The repository also ignores credentials, certificates, local databases, model caches, generated build artifacts, and raw data. Before making the repository public, tracked files should be scanned for secrets and the deployment must use a secret manager rather than committed configuration.

### How should the API be designed?

The API should expose typed request and response contracts, validate tenant and subject context, keep model loading outside request handlers, and return stable identifiers and provenance. The current API slice exposes document ingestion and permission-aware search; authentication and RBAC will replace the client-supplied identity fields before production deployment.

### Where does tenant identity come from?

It must come from a validated authentication token, not from the request body. The current API validates a signed JWT and derives `tenant_id`, `sub`, and `roles` from its claims. Those values are passed into retrieval and ingestion. A production deployment would use an external identity provider and rotate signing keys instead of the development HMAC secret.

### How does PII masking work?

The guardrail scans content and queries for patterns such as email addresses, phone numbers, SSNs, and API-key-like values before embedding or persistence. It replaces them with typed placeholders and records only masking metadata. The current implementation is intentionally conservative and should be extended with a tested recognizer such as an enterprise DLP service for broader coverage.

### Should PII masking be reversible?

Not by default. Reversible masking creates a sensitive mapping that must be encrypted, access-controlled, tenant-scoped, and short-lived. For retrieval and model context, irreversible masking is safer. Reversal should exist only for an approved workflow that genuinely needs the original value.

### How do you handle tool failure?

Use bounded retries only for transient failures, apply timeouts and circuit breakers, preserve the workflow state, and return a partial-but-honest response when the tool remains unavailable. The agent should never claim that a tool succeeded without a verified result.

### How do you prevent prompt injection from documents?

Retrieved documents are treated as untrusted evidence, not instructions. They are delimited, scanned for injection patterns, and passed through a policy that tells the agent to follow system and workflow instructions over document text. Security tests include malicious documents and tool-result injection attempts.

## Production operations

### What would you monitor?

Track retrieval latency, embedding latency, model latency, tool latency, queue depth, error rate, timeout rate, cache hit rate, token usage, cost per workflow, citation failures, abstention rate, and unauthorized-access denials.

### How do you control cost?

Cache embeddings and safe retrieval results, route simple classification to smaller local models, cap context and tool iterations, enforce per-workflow budgets, and record token usage at every model call. Cost limits should fail safely rather than silently skipping security checks.

### How do you scale ingestion?

Move ingestion to an asynchronous worker queue, make jobs idempotent using content hashes, batch embedding requests locally, upsert chunks transactionally, and expose job status. A failed document should be retried independently without duplicating successful documents.

### How do you deploy schema changes?

Use ordered, versioned migrations, backward-compatible changes first, data backfills as resumable jobs, and indexes built with production-safe strategies. Embedding-dimension changes require a new index or table and a controlled re-index rather than an in-place mismatch.

### How do you handle stale documents and re-ingestion?

Documents are identified by `tenant_id` and `external_id`, while a content hash detects changes. Re-ingestion upserts the document, removes its previous chunks, re-chunks the latest content, recomputes embeddings, and inserts the replacement chunks transactionally. This prevents old content from remaining searchable after a source document changes or becomes shorter.

### How do you handle tenant isolation?

Tenant isolation must exist at every layer: authentication claims, API context, SQL filters, retrieval, MCP tools, cache keys, memory, logs, and background jobs. Cache keys must include tenant identity so one tenant cannot receive another tenant's cached answer. PostgreSQL Row-Level Security can add a second enforcement layer in a larger deployment.

### How do you version prompts, embeddings, and datasets?

Every trace should record the schema version, prompt version, embedding model and revision, chunking version, retriever version, reranker version, guardrail version, and evaluation dataset version. This makes regressions explainable and allows safe rollback when retrieval quality or security metrics decline.

### How do you control MCP tool permissions?

Tools are classified as read-only, write-with-approval, or administrative. Every call validates the user, tenant, role, tool allowlist, input schema, resource ownership, approval state, and idempotency key. The model can request an action, but application code—not the model—decides whether it is authorized.

### Why use MCP instead of calling tools directly from the agent?

MCP gives tools a standard interface that can be discovered and consumed by different agent hosts. The official Python SDK derives tool schemas from type hints and supports standard transports. Our application still keeps authorization outside the protocol layer because protocol metadata and client hints are not security controls.

### How does the approval gate work?

For a write tool, the application hashes the exact arguments, binds an approval token to the tenant, subject, tool name, and arguments, and expires the token after a short period. The write call is allowed only when the approval matches. An idempotency key prevents duplicate side effects.

### What happens if the model tampers with an approved tool call?

The approval is rejected because the arguments hash no longer matches. The model cannot convert approval for one action into permission for another action. The system logs the mismatch as a security event.

### How does approval become an actual action?

The API separates approval creation from execution. A user requests approval for a specific tool and argument payload, then the execution request must present the matching token and idempotency key. The application authorizes the call before invoking the MCP write tool. This makes the approval boundary auditable and prevents the model from silently executing a draft.

### What happens if the same action is submitted twice?

The caller supplies an idempotency key. The authorization layer persists the key, canonical argument hash, status, and result in PostgreSQL. A completed key returns the stored result without invoking the tool again; an in-progress key is rejected; and a key reused with different arguments is a security error. The downstream system should also enforce idempotency because exactly-once behavior cannot be assumed across process or network failures.

### How is approval state made production-safe?

Approval tokens are generated with a cryptographically secure random source, but only their SHA-256 hashes are stored. Each record is bound to tenant, subject, tool, and an exact canonical argument hash, and expires after a short TTL. The execution transaction locks the approval row, consumes it once, and creates a durable idempotency record. This prevents process restarts, multiple API replicas, and database-visible token leakage from turning into reusable authorization.

### What happens if the approved tool fails after authorization?

The durable idempotency record moves from `in_progress` to `failed` with a structured error marker. The same key cannot silently retry a potentially ambiguous side effect; the workflow must use an explicit recovery or reconciliation path. For a production integration, the downstream MCP tool should implement an idempotency contract and expose a status/reconciliation operation.

### How does the agent communicate with an MCP server?

The application uses the official MCP client over a typed transport. The local development path launches the MCP server as a subprocess over stdio; a deployed version can use Streamable HTTP. The client validates the tool result and converts it into the graph's typed state. Transport failures are separate from business-tool failures and should be traced independently.

### Why use stdio locally and Streamable HTTP in production?

Stdio is isolated and simple for a local tool process. Streamable HTTP is the deployable transport for a separately scaled MCP service, with normal authentication, timeouts, load balancing, and service observability. The graph depends on a tool adapter, so changing the transport does not change workflow logic.

### Why use a bounded LangGraph workflow?

The graph makes the workflow explicit: retrieve evidence, decide whether a live investigation is needed, call a read-only status tool, and compose a cited response. Explicit transitions make retries, limits, traces, and tests easier than an unconstrained loop. The current graph has no hidden tool loop and abstains when retrieval returns no evidence.

### How do you decide whether to call a live tool?

The workflow classifies the request before calling tools. Terms such as `current`, `live`, `ongoing`, and `status` route the request to a read-only status check. In production, this classifier would be evaluated on labeled requests and combined with authorization policy; keyword routing is only the initial deterministic implementation.

### How does the graph handle no-answer cases?

The retrieval node returns an empty evidence list when nothing authorized is relevant. The composition node produces an explicit insufficient-evidence response with no citations rather than fabricating an answer. This behavior is tested as a first-class path.

### Why use Ollama and a local model here?

The project is designed to be free to run locally, so the answer-generation path uses Ollama rather than a paid hosted API. The model is injected behind a small adapter, which lets us measure the workflow independently from the model provider. The important safety boundary remains retrieval authorization and abstention; the local model is never allowed to invent evidence.

### How do you prevent the model from answering from unsupported context?

The graph only calls the model after retrieval returns authorized evidence. The prompt labels the retrieved text as evidence and explicitly treats instructions inside it as untrusted. The response carries citations from the retrieved sources, and the no-evidence path returns a refusal without invoking the model.

### How do you handle local-model unavailability?

The API should distinguish model unavailability from retrieval failure. A production implementation can return a structured degraded response, retry within a deadline, or use a configured fallback model. It must not silently return a fabricated answer or hide that generation failed.

### How do you handle failed or slow tools?

Each tool has a timeout, bounded retry policy, circuit breaker, correlation ID, and structured error response. Retries are limited to transient failures and destructive operations are not blindly retried. If a tool remains unavailable, the agent returns a partial but honest answer and never claims success without a verified result.

### How do you prevent prompt injection from documents?

Retrieved documents are untrusted evidence, not instructions. They are delimited and inspected, while system and workflow instructions remain authoritative. Tool access is enforced independently through schemas and authorization, so a malicious document cannot grant itself permission to call a tool or expose data.

### How do you evaluate the end-to-end agent?

Evaluation is split into retrieval, generation, agent behavior, and security. We test source recall, citation validity, groundedness, answer correctness, tool selection, approval behavior, failure recovery, prompt injection, PII leakage, and cross-tenant access. Each run records model, prompt, retriever, embedding, and dataset versions.

### Which retrieval metrics do you use?

Recall@K measures whether the expected evidence appears in the top K results. Precision@K measures how much of the returned context is relevant. MRR rewards placing the first relevant result near the top. We also track forbidden-retrieval rate because retrieving unauthorized content is a security failure even if the answer is technically correct.

### Why should evaluation cases be versioned?

Retrieval quality depends on documents, chunking, embeddings, ranking weights, and access rules. A versioned dataset makes comparisons reproducible and allows us to detect regressions when any of those components changes. Evaluation data should include normal, ambiguous, no-answer, permission-sensitive, and adversarial queries.

### How do you test ACL correctness?

Each evaluation case can specify forbidden chunks or documents. The evaluator treats any forbidden result in the top K as a failure and reports a forbidden-retrieval rate. This metric is separate from relevance because a highly relevant unauthorized document is still unacceptable.

## Current implementation status

### Implemented

- PostgreSQL with the pgvector extension
- HNSW vector index and PostgreSQL full-text GIN index
- Local `sentence-transformers/all-MiniLM-L6-v2` embeddings
- Markdown, text, and PDF loaders
- Deterministic paragraph-aware chunking
- Tenant and subject-aware retrieval filtering
- Hybrid vector and keyword retrieval
- Document upsert and stale-chunk replacement
- Versioned SQL migration runner
- Redis and PostgreSQL Docker infrastructure
- Real ingestion and retrieval smoke test
- Unit tests and Ruff checks

### Not yet implemented

- Prompt-injection guardrail service
- Reranking model
- OpenTelemetry or Langfuse tracing
- Asynchronous ingestion workers
- Rate limits and per-workflow budgets
- CI/CD and deployment automation
- Production SSO/IdP integration and key rotation
- PostgreSQL Row-Level Security as a second tenant-isolation layer

### Recently added

- Versioned retrieval evaluation cases
- Recall@K, Precision@K, MRR, and forbidden-retrieval metrics
- Unit tests for evaluation behavior
- Typed FastAPI document-ingestion and retrieval endpoints
- JWT-derived tenant and subject context
- Initial PII masking guardrail before embeddings and storage
- MCP tool server with read-only and draft tools
- Application-side role checks and human approval authorization
- PostgreSQL-backed expiring approval records with hashed tokens
- Durable idempotency records with replay protection and failure state
- Bounded LangGraph retrieval and investigation workflow
- Local Ollama-backed answer generation through `POST /v1/agent/run`
- MCP client-to-server stdio transport for live incident status
- API approval and execution endpoints for a write-capable MCP tool

Be explicit about this boundary in an interview. It is stronger to say what is working and what remains than to claim enterprise features that have not been demonstrated.

## Short project explanation

> I built an enterprise agentic operations platform that ingests PDF, Markdown, and text documents, chunks them deterministically, creates free local embeddings, stores them in PostgreSQL with pgvector, and performs permission-aware hybrid retrieval using both vector similarity and full-text search. A bounded LangGraph workflow can investigate live incident status through MCP, while write actions require JWT-derived authorization, exact-argument human approval, durable idempotency, and failure tracking. The system also includes PII masking, evaluation metrics, Docker infrastructure, and automated tests; the remaining work is explicit production hardening rather than hidden demo behavior.

## Answer structure for interviews

For most questions, answer in this order:

1. State the design decision.
2. Explain the production reason.
3. Mention the security or reliability tradeoff.
4. Describe how you would measure it.
5. Be clear about what is implemented today.

### What is still incomplete in this project?

The working vertical slice now includes JWT-derived identity, PII masking, local embeddings, file ingestion, pgvector hybrid retrieval, ACL filtering, LangGraph orchestration, MCP stdio tools, Ollama generation, approval-gated writes, durable PostgreSQL idempotency, evaluation metrics, and automated tests. The remaining production hardening includes SSO/key rotation, prompt-injection testing, distributed tracing, asynchronous workers, rate limits, budgets, CI/CD, reranking, and a second tenant-isolation layer such as PostgreSQL RLS. Being explicit about that boundary is more credible than claiming unfinished enterprise integrations.
