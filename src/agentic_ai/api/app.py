from uuid import uuid4

from fastapi import FastAPI, Request

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
