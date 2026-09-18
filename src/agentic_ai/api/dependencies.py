from functools import lru_cache

from agentic_ai.config import get_settings
from agentic_ai.embeddings import LocalSentenceTransformerEmbedder
from agentic_ai.llm import OllamaChatModel
from agentic_ai.mcp import MCPStatusClient


@lru_cache
def get_embedder() -> LocalSentenceTransformerEmbedder:
    return LocalSentenceTransformerEmbedder(get_settings().embedding_model)


@lru_cache
def get_answer_model() -> OllamaChatModel:
    settings = get_settings()
    return OllamaChatModel(settings.ollama_base_url, settings.ollama_model)


@lru_cache
def get_mcp_status_client() -> MCPStatusClient:
    return MCPStatusClient()
