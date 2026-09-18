from functools import lru_cache

from agentic_ai.config import get_settings
from agentic_ai.embeddings import LocalSentenceTransformerEmbedder


@lru_cache
def get_embedder() -> LocalSentenceTransformerEmbedder:
    return LocalSentenceTransformerEmbedder(get_settings().embedding_model)
