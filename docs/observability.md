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

## This local workspace

The official Langfuse repository is cloned as a sibling workspace at `../langfuse-local` and is intentionally not vendored into this application repository. Start or stop it with:

```bash
cd ../langfuse-local
docker compose up -d
docker compose ps
```

The dashboard is available at `http://localhost:3000`. The local stack uses host ports `55432` for its PostgreSQL, `56379` for its Redis, `8123`/`9000` for ClickHouse, and `9090`/`9091` for MinIO so it does not collide with the platform’s PostgreSQL and Redis containers.
