"""Domain schema registry for structured extraction.

Each schema describes one extraction template (e.g. a credit-risk report).
The same Pydantic model drives: the LLM prompt (JSON Schema), validation of
the LLM output, and the API response shape — one source of truth.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class KeyMetric(BaseModel):
    name: str
    value: str  # kept as string on purpose: LLMs make numeric mistakes; preserve raw
    unit: str | None = None
    period: str | None = None


class CreditFactor(BaseModel):
    factor: str
    assessment: str | None = None  # optional: not every factor yields a clean sentence
    severity: Literal["low", "medium", "high"]
    notes: str | None = None


class RedFlag(BaseModel):
    flag: str
    severity: Literal["low", "medium", "high"]
    evidence: str | None = None  # optional: LLM may not capture explicit evidence


class FinancialHealth(BaseModel):
    revenue: str | None = None
    net_profit: str | None = None
    total_debt: str | None = None
    liquidity_ratio: str | None = None
    debt_to_equity: str | None = None


class CreditRiskReport(BaseModel):
    """Structured profile extracted from an unstructured credit/research report."""

    company_name: str
    sector: str
    analysis_date: str | None = None
    overall_risk_score: int = Field(ge=0, le=100)
    risk_rating: Literal["A", "B", "C", "D"]
    key_metrics: list[KeyMetric] = Field(default_factory=list)
    financial_health: FinancialHealth = Field(default_factory=FinancialHealth)
    credit_factors: list[CreditFactor] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    recommended_limit: str | None = None
    decision: Literal["approve", "conditional", "decline"]
    decision_justification: str
    confidence: float = Field(default=0.0, ge=0, le=1)


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "credit_report": CreditRiskReport,
}
