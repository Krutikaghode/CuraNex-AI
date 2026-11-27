"""Application settings loaded from environment variables or a local .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CURANEX_", extra="ignore")

    app_name: str = "CuraNex AI"
    environment: str = "development"
    # SQLite for local dev; docker-compose points this at Postgres.
    database_url: str = "sqlite:///./data/curanex.db"
    # Directory for uploaded reports and trained model artifacts (later phases).
    data_dir: str = "./data"
    # LLM provider for the RAG assistant (later phase): "ollama" or "anthropic".
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"


@lru_cache
def get_settings() -> Settings:
    return Settings()
