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
