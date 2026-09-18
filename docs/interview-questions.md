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

### How should the API be designed?

The API should expose typed request and response contracts, validate tenant and subject context, keep model loading outside request handlers, and return stable identifiers and provenance. The current API slice exposes document ingestion and permission-aware search; authentication and RBAC will replace the client-supplied identity fields before production deployment.

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

- Authentication and SSO
- Formal RBAC policy engine
- PII detection and reversible masking
- Prompt-injection guardrail service
- LangGraph orchestration
- MCP servers and tool gateway
- Human approval service
- Reranking model
- Automated retrieval benchmark dataset
- OpenTelemetry or Langfuse tracing
- Asynchronous ingestion workers
- Rate limits and per-workflow budgets
- CI/CD and deployment automation

### Recently added

- Versioned retrieval evaluation cases
- Recall@K, Precision@K, MRR, and forbidden-retrieval metrics
- Unit tests for evaluation behavior
- Typed FastAPI document-ingestion and retrieval endpoints

Be explicit about this boundary in an interview. It is stronger to say what is working and what remains than to claim enterprise features that have not been demonstrated.

## Short project explanation

> I built the retrieval foundation for an enterprise agentic operations platform. It ingests PDF, Markdown, and text documents, chunks them deterministically, creates free local embeddings, stores them in PostgreSQL with pgvector, and performs permission-aware hybrid retrieval using both vector similarity and full-text search. Re-ingestion removes stale chunks, and a Docker-backed smoke test verifies that authorized users retrieve the correct evidence while cross-tenant users receive no results. The next layer adds guarded agent workflows, MCP tools, human approval, masking, and evaluation infrastructure.

## Answer structure for interviews

For most questions, answer in this order:

1. State the design decision.
2. Explain the production reason.
3. Mention the security or reliability tradeoff.
4. Describe how you would measure it.
5. Be clear about what is implemented today.

### What is still incomplete in this project?

The current vertical slice has local embeddings, file ingestion, pgvector hybrid retrieval, ACL filtering, and a real Docker-backed smoke test. The next production layers are authentication, formal RBAC, PII masking, MCP tool authorization, LangGraph orchestration, evaluation datasets, and observability. Being explicit about that boundary is more credible than claiming unfinished enterprise integrations.
