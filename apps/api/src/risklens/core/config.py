"""Application configuration loaded from environment (.env / process env).

Single source of truth for runtime settings. Secrets never live in code —
everything comes from environment variables through pydantic-settings.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    """Resolve the repo-root .env regardless of the process CWD (uvicorn/worker
    run from apps/api, but the documented .env lives at the repo root)."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / ".env"
        if candidate.exists():
            return str(candidate)
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
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

    # --- BYOK credentials (encryption at rest) ---
    # AES-256 key for per-user provider credentials (base64, 32 bytes).
    # Falls back to a deterministic derivation from JWT_SECRET in dev.
    credentials_enc_key: str = Field(default="", repr=False)

    # --- Seed ---
    seed_admin_email: str = "admin@risklens.local"
    seed_admin_password: str = "Admin@12345"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://risklens:risklens@127.0.0.1:5432/risklens"

    # --- Redis ---
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- LLM chat provider ---
    # opencode | openai | anthropic | google | groq | lmstudio | ollama | vertex | custom
    llm_provider: str = "lmstudio"
    llm_model: str = "google/gemma-3-4b"
    # Overrides used by 'custom' (or as fallback for any provider)
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_api_key: str = Field(default="lm-studio", repr=False)
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # Per-provider credentials (only the ones in use need to be set)
    openai_api_key: str = Field(default="", repr=False)
    anthropic_api_key: str = Field(default="", repr=False)
    gemini_api_key: str = Field(default="", repr=False)
    groq_api_key: str = Field(default="", repr=False)
    opencode_api_key: str = Field(default="", repr=False)
    lm_studio_base_url: str = "http://127.0.0.1:1234/v1"

    # Google Vertex AI (enterprise/GCP) — uses google-genai; ADC when no api key
    vertex_project: str = ""
    vertex_region: str = "us-central1"
    vertex_api_key: str = Field(default="", repr=False)

    # --- Embeddings (independent of chat provider) ---
    # openai | lmstudio | ollama | fastembed | vertex | custom
    embedding_provider: str = "lmstudio"
    embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    # Fixed dimension across providers so pgvector vector(768) never needs a migration
    embedding_dims: int = 768
    embedding_base_url: str = "http://127.0.0.1:1234/v1"
    embedding_api_key: str = Field(default="lm-studio", repr=False)

    # --- Observability ---
    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str = "http://127.0.0.1:4318"
    otel_service_name: str = "risklens-api"

    # --- Feature flags ---
    ff_agent_review_enabled: bool = True
    ff_rag_hybrid_search: bool = True
    ff_eval_llm_judge: bool = True

    # --- RAG tuning (env defaults; overridable at runtime via the settings panel) ---
    rag_chunk_size: int = 1200
    rag_top_k: int = 6

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
