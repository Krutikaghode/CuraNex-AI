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
    # Trained model artifacts; each model lives in its own subdirectory.
    models_dir: str = "./models"
    # LLM provider for the RAG assistant: "ollama" (default) or "fake" (tests/offline demo).
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    llm_timeout_seconds: float = 120.0
    # Auth. The default secret only works in development; production refuses to start with it.
    jwt_secret: str = "dev-only-insecure-secret-change-me-before-deploying"
    jwt_expire_minutes: int = 60
    # Optional first-run admin, created on startup if no users exist yet.
    admin_email: str | None = None
    admin_password: str | None = None
    # Retrieval
    rag_chunk_chars: int = 900
    rag_chunk_overlap: int = 150
    rag_top_k: int = 5
    # Cosine cut-off below which chunks are dropped. Model-dependent; tune with app.rag.evaluate.
    rag_min_score: float = 0.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
