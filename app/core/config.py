"""
app/core/config.py
Application settings loaded from environment variables.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql://hr_ai:hr_ai_secret@localhost:5432/hr_ai_router"

    # ── MinIO / Object Storage ────────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "hr_ai_minio"
    minio_secret_key: str = "hr_ai_minio_secret"
    minio_secure: bool = False
    minio_bucket_resumes: str = "resumes"

    # ── Cohere Embedding ──────────────────────────────────────────────────────
    cohere_api_key: Optional[str] = None
    cohere_embed_model: str = "embed-english-v3.0"
    embed_dimension: int = 1024

    # ── API Provider Keys (forwarded to router layer) ─────────────────────────
    groq_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    cerebras_api_key: Optional[str] = None

    # ── FastAPI ───────────────────────────────────────────────────────────────
    app_title: str = "HR AI Platform"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    debug: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
