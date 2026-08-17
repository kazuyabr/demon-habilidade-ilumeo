"""Unit tests for the schema-agnostic eval comparison."""

from __future__ import annotations

from risklens.application.services.eval_service import _compare
from risklens.domain.schemas import CreditRiskReport

EXPECTED = {
    "company_name": "Transportadora Estrela S.A.",
    "sector": "logística e transporte de cargas",
    "analysis_date": "12/08/2026",
    "overall_risk_score": 75,
    "risk_rating": "C",
    "recommended_limit": "R$ 350 mil",
    "decision": "conditional",
    "decision_justification": "Aprovação condicional com limite de R$ 350 mil.",
    "confidence": 0.85,
    "red_flags": [
        {"flag": "Atraso de 90 dias com fornecedor", "severity": "high"},
        {"flag": "Notificações extrajudiciais", "severity": "medium"},
        {"flag": "Concentração de receita", "severity": "medium"},
    ],
}

SCALAR_COUNT = 9  # company_name, sector, analysis_date, overall_risk_score,
# risk_rating, recommended_limit, decision, decision_justification, confidence


def test_perfect_match() -> None:
    cmp = _compare(EXPECTED, dict(EXPECTED), CreditRiskReport)
    assert cmp["field_exact"] == cmp["field_total"] == SCALAR_COUNT
    assert cmp["fuzzy"] == 1.0
    assert cmp["score_mae"] == 0.0
    assert cmp["decision_match"] is True
    assert cmp["redflag_recall"] == 1.0
    assert cmp["redflag_expected"] == 3
    assert cmp["redflag_found"] == 3


def test_score_mae_and_decision_mismatch() -> None:
    actual = dict(EXPECTED)
    actual["overall_risk_score"] = 80
    actual["decision"] = "approve"
    cmp = _compare(EXPECTED, actual, CreditRiskReport)
    assert cmp["score_mae"] == 5.0
    assert cmp["decision_match"] is False


def test_redflag_recall_partial() -> None:
    actual = dict(EXPECTED)
    actual["red_flags"] = EXPECTED["red_flags"][:2]
    cmp = _compare(EXPECTED, actual, CreditRiskReport)
    assert cmp["redflag_expected"] == 3
    assert cmp["redflag_found"] == 2
    assert round(cmp["redflag_recall"], 2) == round(2 / 3, 2)


def test_redflag_recall_case_insensitive() -> None:
    actual = dict(EXPECTED)
    actual["red_flags"] = [
        {"flag": "atraso de 90 dias com fornecedor", "severity": "high"},
    ]
    cmp = _compare(EXPECTED, actual, CreditRiskReport)
    assert cmp["redflag_recall"] == round(1 / 3, 4)


def test_none_score_yields_none_mae() -> None:
    actual = dict(EXPECTED)
    actual["overall_risk_score"] = None
    cmp = _compare(EXPECTED, actual, CreditRiskReport)
    assert cmp["score_mae"] is None
