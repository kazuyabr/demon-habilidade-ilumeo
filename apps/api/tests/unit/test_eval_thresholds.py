"""Unit tests for eval threshold evaluation (quality gate)."""

from __future__ import annotations

from risklens.application.services.eval_service import _evaluate_thresholds


def test_passes_above_defaults() -> None:
    results, passed, effective = _evaluate_thresholds({"decision_accuracy": 1.0, "redflag_recall": 0.5}, None)
    assert passed is True
    assert effective == {"decision_accuracy": 0.9, "redflag_recall": 0.4}
    assert results["decision_accuracy"]["pass"] is True


def test_fails_below_default() -> None:
    _, passed, _ = _evaluate_thresholds({"decision_accuracy": 0.8, "redflag_recall": 0.5}, None)
    assert passed is False


def test_at_threshold_passes() -> None:
    results, passed, _ = _evaluate_thresholds({"decision_accuracy": 0.9, "redflag_recall": 0.4}, None)
    assert passed is True
    assert results["decision_accuracy"]["pass"] is True


def test_definition_overrides_global_default() -> None:
    metrics = {"decision_accuracy": 0.85, "redflag_recall": 0.3}
    _, passed, effective = _evaluate_thresholds(metrics, {"decision_accuracy": 0.8, "redflag_recall": 0.25})
    assert passed is True
    assert effective["decision_accuracy"] == 0.8


def test_unmeasured_metric_does_not_fail_gate() -> None:
    metrics = {"decision_accuracy": 1.0, "redflag_recall": 0.5, "llm_judge_score": None}
    results, passed, _ = _evaluate_thresholds(metrics, {"llm_judge_score": 4.0})
    assert results["llm_judge_score"]["pass"] is None
    assert passed is True


def test_score_mae_lower_is_better() -> None:
    ok, passed, _ = _evaluate_thresholds(
        {"decision_accuracy": 1.0, "redflag_recall": 0.5, "score_mae": 10.0}, {"score_mae": 15.0}
    )
    assert ok["score_mae"]["pass"] is True
    assert passed is True

    bad, _, _ = _evaluate_thresholds({"score_mae": 20.0}, {"score_mae": 15.0})
    assert bad["score_mae"]["pass"] is False
