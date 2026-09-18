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

### What is still incomplete in this project?

The current vertical slice has local embeddings, file ingestion, pgvector hybrid retrieval, ACL filtering, and a real Docker-backed smoke test. The next production layers are authentication, formal RBAC, PII masking, MCP tool authorization, LangGraph orchestration, evaluation datasets, and observability. Being explicit about that boundary is more credible than claiming unfinished enterprise integrations.
