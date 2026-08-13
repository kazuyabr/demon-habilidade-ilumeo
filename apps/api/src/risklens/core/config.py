"""Application configuration loaded from environment (.env / process env).

Single source of truth for runtime settings. Secrets never live in code —
everything comes from environment variables through pydantic-settings.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "RiskLens"
    app_env: str = "development"
    app_debug: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8010
    api_public_url: str = "http://127.0.0.1:8010"

    # --- Auth / JWT ---
    # Dev-only default; production MUST set a strong JWT_SECRET (>= 32 bytes)
    jwt_secret: str = Field(default="dev-only-secret-change-me-in-prod-0123456789", repr=False)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- Seed ---
    seed_admin_email: str = "admin@risklens.local"
    seed_admin_password: str = "Admin@12345"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://risklens:risklens@127.0.0.1:5432/risklens"

    # --- Redis ---
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- LLM provider ---
    llm_provider: str = "lmstudio"  # lmstudio | openai | anthropic | ollama
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_api_key: str = Field(default="lm-studio", repr=False)
    llm_model: str = "google/gemma-3-4b"
    llm_embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    llm_embedding_dims: int = 768
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # --- Observability ---
    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str = "http://127.0.0.1:4318"
    otel_service_name: str = "risklens-api"

    # --- Feature flags ---
    ff_agent_review_enabled: bool = True
    ff_rag_hybrid_search: bool = True
    ff_eval_llm_judge: bool = True

    # --- Storage ---
    upload_dir: str = "./uploads"
    max_upload_mb: int = 10
    allowed_extensions: str = "txt,md,pdf"
    samples_dir: str = "../../samples"

    @property
    def allowed_extension_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
