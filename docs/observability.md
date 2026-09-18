# Observability with Langfuse

The platform uses two complementary telemetry paths:

- PostgreSQL `audit_events` for durable tenant-scoped security and business events.
- Langfuse for agent, retrieval, model, tool, latency, and evaluation traces.

Langfuse is optional. With no credentials configured, the application uses a no-op tracer and remains fully functional. Content capture is disabled by default so prompts, answers, and retrieved text are not exported accidentally. Enable it only after reviewing tenant data handling and configuring a self-hosted or approved Langfuse endpoint.

## Configuration

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://localhost:3000
LANGFUSE_RELEASE=local
LANGFUSE_CAPTURE_CONTENT=false
```

The application currently creates an `agent.run` observation. The trace records execution status and safe metadata by default; enabling content capture makes the masked request available for prompt-level debugging and evaluation.

## Local self-hosting

For local experiments, use the official Langfuse Docker Compose deployment and open its UI on port 3000. The official deployment is intentionally kept separate from this application’s PostgreSQL and Redis stack because Langfuse has its own storage, migrations, and operational lifecycle. For production, use the official Kubernetes or managed deployment guidance with persistent storage, backups, secrets, and access control.

The application uses the same SDK contract for Langfuse Cloud and self-hosted Langfuse; only the endpoint and credentials change.
