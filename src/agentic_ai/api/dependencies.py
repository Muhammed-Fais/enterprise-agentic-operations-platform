from functools import lru_cache

from redis.asyncio import Redis

from agentic_ai.config import get_settings
from agentic_ai.controls import RedisControls
from agentic_ai.embeddings import LocalSentenceTransformerEmbedder
from agentic_ai.llm import OllamaChatModel
from agentic_ai.mcp import (
    MCPStatusClient,
    PersistentToolAuthorization,
    ToolCapability,
    ToolPolicy,
)
from agentic_ai.observability import LangfuseObservability


@lru_cache
def get_embedder() -> LocalSentenceTransformerEmbedder:
    return LocalSentenceTransformerEmbedder(get_settings().embedding_model)


@lru_cache
def get_answer_model() -> OllamaChatModel:
    settings = get_settings()
    return OllamaChatModel(
        settings.ollama_base_url,
        settings.ollama_model,
        observability=get_observability(),
    )


@lru_cache
def get_observability() -> LangfuseObservability:
    return LangfuseObservability(get_settings())


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=False)


@lru_cache
def get_redis_controls() -> RedisControls:
    settings = get_settings()
    return RedisControls(
        get_redis(),
        requests_per_minute=settings.rate_limit_requests_per_minute,
        agent_budget_per_day=settings.agent_budget_units_per_day,
    )


@lru_cache
def get_mcp_status_client() -> MCPStatusClient:
    return MCPStatusClient(observability=get_observability())


@lru_cache
def get_tool_authorization() -> PersistentToolAuthorization:
    return PersistentToolAuthorization(
        [
            ToolPolicy(
                "create_incident_ticket",
                ToolCapability.WRITE,
                frozenset({"analyst", "incident_commander"}),
            )
        ]
    )
