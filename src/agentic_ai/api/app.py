from uuid import uuid4

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request, status
from sqlalchemy import text

from agentic_ai.config import get_settings
from agentic_ai.db.session import engine

from .routes import router

app = FastAPI(title="Agentic AI Operations Platform", version="0.1.0")
app.include_router(router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def readiness() -> dict[str, object]:
    """Report whether dependencies required to serve traffic are available."""
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = "unavailable"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        ) from exc

    client = redis.from_url(get_settings().redis_url)
    try:
        await client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = "unavailable"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        ) from exc
    finally:
        await client.aclose()

    return {"status": "ready", "checks": checks}
