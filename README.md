# Agentic AI Operations Platform

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

The project is intentionally organized around replaceable interfaces. Retrieval, model providers, MCP clients, and observability implementations can evolve without coupling the core workflow to one vendor.
