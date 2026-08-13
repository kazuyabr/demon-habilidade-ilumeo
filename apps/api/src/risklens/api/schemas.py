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
    name: str = Field(default="credit-report-golden", min_length=3)


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    model_used: str | None
    metrics: dict | None
    items: list
    error_message: str | None = None
    created_at: datetime


class FeatureFlagsOut(BaseModel):
    agent_review_enabled: bool
    rag_hybrid_search: bool
    eval_llm_judge: bool
    llm_model: str
    llm_provider: str
