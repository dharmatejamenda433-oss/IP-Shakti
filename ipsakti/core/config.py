"""Application configuration.

All settings are read from environment variables (or a local `.env`) with the
`IPSAKTI_` prefix. See `.env.example` for the full list. Secrets are never
hard-coded; they must come from the environment.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production", "test"]


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are populated from environment variables prefixed with `IPSAKTI_`
    (e.g. `IPSAKTI_DATABASE_URL`). A local `.env` file is also read when present.
    """

    model_config = SettingsConfigDict(
        env_prefix="IPSAKTI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    env: Environment = "development"
    log_level: str = "INFO"
    secret_key: SecretStr = Field(default=SecretStr("insecure-dev-only-key"))
    api_v1_prefix: str = "/api/v1"

    # --- Security / tokens ---
    access_token_ttl_minutes: int = Field(default=15, ge=1)
    refresh_token_ttl_days: int = Field(default=7, ge=1)
    jwt_algorithm: str = "HS256"

    # --- PostgreSQL (system of record) ---
    database_url: str = "postgresql+psycopg://ipsakti:ipsakti@localhost:5432/ipsakti"

    # --- Qdrant (derived vector index) ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "ipsakti_chunks"

    # --- Embeddings / reranking ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = Field(default=384, ge=1)
    reranker_model: str = "BAAI/bge-reranker-base"

    # --- Retrieval tunables ---
    rrf_k: int = Field(default=60, ge=1)
    candidate_pool_size: int = Field(default=30, ge=1)
    final_result_size: int = Field(default=8, ge=1)
    relevance_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    # --- Chunking tunables ---
    chunk_target_tokens: int = Field(default=600, ge=50)
    chunk_overlap_tokens: int = Field(default=75, ge=0)

    # --- Generation (Groq) ---
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.1-70b-versatile"

    # --- Storage ---
    storage_root: str = "data/storage"
    max_upload_bytes: int = Field(default=52_428_800, ge=1)

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        """Normalize and validate the log level name."""
        normalized = value.strip().upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if normalized not in allowed:
            msg = f"log_level must be one of {sorted(allowed)}; got {value!r}"
            raise ValueError(msg)
        return normalized

    @field_validator("chunk_overlap_tokens")
    @classmethod
    def _validate_overlap(cls, value: int, info: object) -> int:
        """Ensure chunk overlap stays strictly smaller than the chunk target."""
        # `info.data` holds fields validated so far; guard for ordering.
        data = getattr(info, "data", {})
        target = data.get("chunk_target_tokens")
        if isinstance(target, int) and value >= target:
            msg = "chunk_overlap_tokens must be smaller than chunk_target_tokens"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _require_strong_production_secret(self) -> Settings:
        """Reject development and placeholder signing keys in production."""
        if self.env == "production":
            secret = self.secret_key.get_secret_value().strip()
            lowered = secret.lower()
            placeholders = ("insecure-dev-only-key", "change-me", "replace-me", "your-secret")
            if len(secret) < 32 or any(marker in lowered for marker in placeholders):
                msg = (
                    "production requires IPSAKTI_SECRET_KEY to be a non-placeholder "
                    "random secret of at least 32 characters"
                )
                raise ValueError(msg)
        return self

    @property
    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self.env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()
