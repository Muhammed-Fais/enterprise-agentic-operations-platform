from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://agentic:agentic@localhost:5432/agentic"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "http://localhost:3000"
    langfuse_release: str = "local"
    langfuse_capture_content: bool = False
    rate_limit_requests_per_minute: int = 60
    agent_budget_units_per_day: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
