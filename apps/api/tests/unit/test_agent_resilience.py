"""Unit tests for the agent orchestration resilience helpers."""

from __future__ import annotations

import pytest

from risklens.application.services.agent_service import (
    _build_fallback_report,
    _json_call,
    _merge_revision,
    _safe_int,
)

# --- _safe_int ---------------------------------------------------------------


def test_safe_int_accepts_int_and_numeric_string() -> None:
    assert _safe_int(75) == 75
    assert _safe_int("65") == 65
    assert _safe_int(80.0) == 80


def test_safe_int_clamps_to_0_100() -> None:
    assert _safe_int(-5) == 0
    assert _safe_int(150) == 100


def test_safe_int_rejects_labels_and_bools() -> None:
    assert _safe_int("Reavaliar - dados inconsistentes") is None
    assert _safe_int("Revisar") is None
    assert _safe_int(True) is None
    assert _safe_int(None) is None


# --- _merge_revision ---------------------------------------------------------


def test_merge_revision_rejects_string_risk_score() -> None:
    analysis = {"risk_score": 65, "risk_rating": "C", "decision": "conditional"}
    revision = {"risk_score": "Reavaliar - dados inconsistentes"}
    merged, rejected = _merge_revision(analysis, revision)
    assert merged["risk_score"] == 65
    assert rejected == ["risk_score"]


def test_merge_revision_rejects_out_of_domain_rating() -> None:
    analysis = {"risk_score": 65, "risk_rating": "B", "decision": "conditional"}
    revision = {"risk_rating": "Yellow"}
    merged, rejected = _merge_revision(analysis, revision)
    assert merged["risk_rating"] == "B"
    assert rejected == ["risk_rating"]


def test_merge_revision_applies_valid_fields() -> None:
    analysis = {"risk_score": 65, "risk_rating": "C", "decision": "conditional"}
    revision = {"risk_score": 70, "risk_rating": "B", "key_findings": ["achado"]}
    merged, rejected = _merge_revision(analysis, revision)
    assert merged["risk_score"] == 70
    assert merged["risk_rating"] == "B"
    assert merged["key_findings"] == ["achado"]
    assert rejected == []


def test_merge_revision_rejects_unknown_and_non_list_fields() -> None:
    analysis = {"risk_score": 65, "risk_rating": "C", "decision": "conditional", "key_findings": ["original"]}
    revision = {"summary": "não aplicável", "key_findings": "string, não lista"}
    merged, rejected = _merge_revision(analysis, revision)
    assert merged["key_findings"] == ["original"]
    assert set(rejected) == {"summary", "key_findings"}


# --- _build_fallback_report --------------------------------------------------


def test_fallback_never_crashes_on_dirty_analysis() -> None:
    analysis = {
        "risk_score": "Reavaliar - dados inconsistentes",
        "risk_rating": "Yellow",
        "decision": "maybe",
        "key_findings": ["achado 1", 42],
    }
    report = _build_fallback_report(analysis, ["doc.md"])
    assert report.risk_score == 0
    assert report.risk_rating == "D"
    assert report.decision == "conditional"
    assert report.key_findings == ["achado 1"]
    assert report.citations == ["doc.md"]


def test_fallback_keeps_clean_values() -> None:
    analysis = {"risk_score": 70, "risk_rating": "B", "decision": "approve", "key_findings": ["ok"]}
    report = _build_fallback_report(analysis, ["doc.md"])
    assert report.risk_score == 70
    assert report.risk_rating == "B"
    assert report.decision == "approve"


# --- _json_call repair retry -------------------------------------------------


class _FakeLLM:
    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls = 0

    async def complete(self, *, system: str, user: str, **kwargs) -> str:
        self.calls += 1
        return self._replies.pop(0)


async def test_json_call_repairs_invalid_output() -> None:
    llm = _FakeLLM(["prosa sem JSON", '{"sub_queries": ["a", "b"]}'])
    result = await _json_call(llm, system="s", user="u")
    assert result == {"sub_queries": ["a", "b"]}
    assert llm.calls == 2


async def test_json_call_raises_when_repair_also_fails() -> None:
    llm = _FakeLLM(["prosa sem JSON", "mais prosa"])
    with pytest.raises(ValueError):
        await _json_call(llm, system="s", user="u")
    assert llm.calls == 2
