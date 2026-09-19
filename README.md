# Enterprise Agentic Operations Platform

An extensible enterprise multi-agent platform for incident response and support operations.

The first vertical slice will answer incident questions from authorized knowledge-base documents, use read-only MCP tools for investigation, and require approval before taking write actions.

## Initial architecture

- FastAPI API layer
- LangGraph orchestration
- PostgreSQL + pgvector for durable document and vector storage
- Redis for caching and asynchronous work
- MCP servers for controlled tool access
- Typed skills and guardrails
- Evaluation datasets for retrieval, grounding, tool use, and security

## Local development

```bash
cp .env.example .env
docker compose up -d postgres redis
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

The project is intentionally organized around replaceable interfaces. The default embedding path is local and free: `sentence-transformers/all-MiniLM-L6-v2`, with model files cached locally after the first download. Retrieval, model providers, MCP clients, and observability implementations remain behind typed boundaries so they can be benchmarked independently.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the platform diagrams, request lifecycle, trust boundaries, and evaluation loop. The diagrams use Mermaid and render directly on GitHub.

For an interview-ready visual deck, open [the presentation source](docs/enterprise-agentic-operations-platform.html) or download the generated PDF from the repository releases/artifacts when available.

## Database foundation

The initial schema is in [001_initial.sql](infra/migrations/001_initial.sql). It creates tenant-aware documents, vectorized chunks, ingestion jobs, and audit events. The ingestion package currently provides deterministic paragraph-aware chunking so ingestion behavior can be evaluated and versioned.

The retrieval implementation combines pgvector cosine similarity with PostgreSQL full-text search. Once PostgreSQL is available, apply the schema with:

```bash
.venv/bin/python -m agentic_ai.db.migrate
```

Run the local infrastructure with Docker Desktop:

```bash
docker compose up -d postgres redis
```

To run the complete containerized API stack, including an idempotent migration job:

```bash
docker compose --profile app up --build
```

`/health` is a liveness check. `/ready` verifies PostgreSQL and Redis before the API is marked ready, which allows an orchestrator to keep traffic away during dependency outages or startup.

See [production interview questions and answers](docs/interview-questions.md) for the reasoning behind the retrieval, security, agent, MCP, and operations design.

See [observability.md](docs/observability.md) for the Langfuse tracing setup. Langfuse is optional and content capture is disabled by default; PostgreSQL remains the durable audit source for security and business events.

The first versioned retrieval cases live in [retrieval_cases.jsonl](data/evaluation/retrieval_cases.jsonl), with metric calculations in `agentic_ai.evaluation`. Evaluation cases are treated as code: changes should be reviewed and run in CI.

Run the deterministic retrieval quality gate locally:

```bash
PYTHONPATH=src .venv/bin/python -m agentic_ai.evaluation.cli \
  --cases data/evaluation/retrieval_cases.jsonl \
  --predictions data/evaluation/retrieval_smoke_predictions.jsonl \
  --output retrieval-evaluation.json \
  --min-recall-at-k 1.0 \
  --max-forbidden-retrieval-rate 0.0 \
  --max-p95-latency-ms 100
```

Production retriever adapters should write the same prediction format. CI treats missing evidence, unauthorized chunks, and latency regressions as quality-gate failures and stores the JSON report as an artifact.

Run the deterministic security gate locally:

```bash
PYTHONPATH=src .venv/bin/python -m agentic_ai.evaluation.security_cli \
  --cases data/evaluation/security_cases.jsonl \
  --output security-evaluation.json
```

The security suite covers PII masking, prompt-injection detection, cross-tenant retrieval leakage, role-based tool authorization, and approval enforcement. It is a baseline control suite; production deployments should add tenant-specific adversarial cases and external DLP/identity-provider tests.

Local development uses an HMAC JWT secret. For an identity-provider deployment, set `JWT_JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`, and an asymmetric `JWT_ALGORITHM` such as `RS256`; the API resolves signing keys by token `kid`, caches the JWKS briefly, and validates issuer/audience claims. PostgreSQL RLS is enabled and forced on tenant-owned tables, with the authenticated tenant written into a transaction-local database setting before application queries run.

The API can be started with:

```bash
.venv/bin/uvicorn agentic_ai.api.app:app --reload
```

It currently exposes synchronous `POST /v1/documents`, asynchronous `POST /v1/ingestion/jobs` with `GET /v1/ingestion/jobs/{job_id}`, `POST /v1/search`, `POST /v1/agent/run`, `POST /v1/actions/request-approval`, and `POST /v1/actions/execute`. Identity is derived from JWT claims.

The complete Compose profile also starts an ingestion worker:

```bash
docker compose --profile app up --build
```

Async jobs store masked document payloads and tenant context durably in PostgreSQL, while Redis Streams carry only job IDs. The worker claims each job, increments its attempt count, retries transient failures up to the configured limit, acknowledges successful messages, and leaves terminal failures in the PostgreSQL job record for inspection.

The MCP demo server can be run with:

```bash
.venv/bin/python -m agentic_ai.mcp.server
```

Tool authorization is enforced in the application layer, including role checks, hashed expiring approval records, exact-argument binding, durable PostgreSQL idempotency, and failure state. MCP tool annotations are treated as metadata, not as a security boundary. The in-memory authorization class is retained only for isolated unit tests; the API uses the persistent implementation.

The agent answer path uses local Ollama through `OLLAMA_MODEL` and defaults to `llama3:latest` in this environment. The graph abstains before calling the model when no authorized evidence is retrieved.

Protected API routes use Redis-backed per-tenant/user rate limits and daily agent workflow budgets. Configure `RATE_LIMIT_REQUESTS_PER_MINUTE` and `AGENT_BUDGET_UNITS_PER_DAY` in `.env`; Redis control failures fail closed with `503`.

## CI/CD and containerization

GitHub Actions runs Ruff, the test suite, dependency auditing, CodeQL analysis, and a Docker build on pushes and pull requests. The application image runs as a non-root user and does not contain `.env`, tests, credentials, or model caches. Deployment credentials and runtime secrets must be provided through the target environment’s secret manager.
