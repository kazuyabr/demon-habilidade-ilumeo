"""Unit tests for extraction schema validation and registry."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from risklens.domain.schemas import CreditRiskReport, SCHEMA_REGISTRY


def test_registry_has_credit_report() -> None:
    assert "credit_report" in SCHEMA_REGISTRY
    assert SCHEMA_REGISTRY["credit_report"] is CreditRiskReport


def test_valid_report() -> None:
    report = CreditRiskReport(
        company_name="Acme",
        sector="logística",
        overall_risk_score=70,
        risk_rating="C",
        decision="conditional",
        decision_justification="just",
        confidence=0.8,
    )
    assert report.overall_risk_score == 70
    assert report.key_metrics == []  # default lists


def test_score_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        CreditRiskReport(
            company_name="Acme",
            sector="x",
            overall_risk_score=101,
            risk_rating="C",
            decision="approve",
            decision_justification="j",
        )


def test_optional_evidence_allowed() -> None:
    report = CreditRiskReport.model_validate(
        {
            "company_name": "Acme",
            "sector": "x",
            "overall_risk_score": 50,
            "risk_rating": "B",
            "decision": "approve",
            "decision_justification": "j",
            "red_flags": [{"flag": "atraso", "severity": "high", "evidence": None}],
        }
    )
    assert report.red_flags[0].evidence is None


def test_required_field_missing() -> None:
    with pytest.raises(ValidationError):
        CreditRiskReport.model_validate(
            {"sector": "x", "overall_risk_score": 50, "risk_rating": "B"}
        )
