"""API response/request schemas (presentation layer)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: str


class CredentialSummary(BaseModel):
    provider: str
    has_api_key: bool
    api_key_last4: str | None = None
    has_base_url: bool
    base_url: str | None = None  # host URL (not a secret) so the UI can pre-fill
    updated_at: str | None = None


class CredentialUpdate(BaseModel):
    api_key: str | None = Field(default=None, max_length=500)
    base_url: str | None = Field(default=None, max_length=2048)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    title: str
    content_type: str
    status: str
    error_message: str | None = None
    source: str | None = None
    size_bytes: int
    sha256: str
    created_at: datetime


class UploadResponse(BaseModel):
    document: DocumentOut
    duplicate: bool = False


class ExtractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    schema_name: str
    status: str
    data: dict | None
    model_used: str | None
    confidence: float | None
    error_message: str | None = None
    created_at: datetime


class CitationOut(BaseModel):
    index: int
    document_id: str
    document_title: str
    snippet: str
    score: float


class RagAnswer(BaseModel):
    question: str
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    grounded: bool


class AgentRunCreate(BaseModel):
    question: str = Field(min_length=5, max_length=2000)


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question: str
    status: str
    result: dict | None
    trace: list
    model_used: str | None
    error_message: str | None = None
    created_at: datetime


class AgentStepEvent(BaseModel):
    kind: str
    thought: str | None = None
    action: str | None = None
    action_input: str | None = None
    observation: str | None = None
    output: str | None = None
    ts: str


class EvalRunCreate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=128)
    definition_id: UUID | None = None
    provider: str | None = None  # override do modelo do run (default = ativo)
    model: str | None = None


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    definition_id: UUID | None = None
    status: str
    model_used: str | None
    metrics: dict | None
    items: list
    error_message: str | None = None
    created_at: datetime


class EvalCase(BaseModel):
    document_file: str | None = None  # nome do snapshot (ex.: nome do doc de origem)
    document_text: str
    expected: dict


class EvalDefinitionCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    schema_name: str = "credit_report"
    cases: list[EvalCase] = Field(min_length=1)


class EvalDefinitionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    schema_name: str | None = None
    cases: list[EvalCase] | None = None


class EvalDefinitionOut(BaseModel):
    id: UUID
    slug: str
    title: str
    description: str | None = None
    schema_name: str
    n_cases: int
    created_at: datetime
    updated_at: datetime


class EvalDefinitionDetail(EvalDefinitionOut):
    cases: list[EvalCase] = Field(default_factory=list)


class EvalValidateIn(BaseModel):
    schema_name: str = "credit_report"
    expected: dict


class EvalValidateOut(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class FeatureFlagsOut(BaseModel):
    agent_review_enabled: bool
    rag_hybrid_search: bool
    eval_llm_judge: bool
    llm_model: str
    llm_provider: str
    embedding_model: str
    embedding_provider: str
    embedding_dims: int


class ActiveProviderOut(BaseModel):
    provider: str
    model: str
    dims: int | None = None


class ProvidersOut(BaseModel):
    providers: list[dict]
    active_chat: ActiveProviderOut
    active_embeddings: ActiveProviderOut


class SettingsOut(BaseModel):
    config: dict
    overridden: list[str]


class SettingsUpdate(BaseModel):
    chat_provider: str | None = None
    chat_model: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=64, le=16384)
    chunk_size: int | None = Field(default=None, ge=200, le=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    rag_hybrid: bool | None = None
    ff_agent_review_enabled: bool | None = None
    ff_eval_llm_judge: bool | None = None


class SettingsTestIn(BaseModel):
    provider: str = Field(min_length=2)
    model: str = Field(min_length=1)


class SettingsTestOut(BaseModel):
    ok: bool
    latency_ms: int
    model: str
    reply: str | None = None
    error: str | None = None
