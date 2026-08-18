"""Eval harness: regression quality measurement for structured extraction.

Runs the SAME extraction pipeline used in production over a golden set of
cases with expected JSON (an ``eval definition``), then computes metrics.
This is how a model/prompt change is gated before deploy — the LLM-regression
story. The comparison is **schema-agnostic**: it introspects the Pydantic
schema so any extraction template in ``SCHEMA_REGISTRY`` can be evaluated.

Metrics (same names as the previous credit-only version):
- field_exact_accuracy   fraction of scalar fields that match exactly
- field_fuzzy_similarity mean token-Jaccard across scalar fields
- score_mae              mean absolute error on the numeric score field
- decision_accuracy      decision field match rate
- redflag_recall         list-field recall (items matched by a key, e.g. "flag")
- llm_judge_score        (feature flag) 0-5 grading by the LLM itself
"""

from __future__ import annotations

import json
from types import UnionType
from typing import Literal, Union, get_args, get_origin
from uuid import UUID

from risklens.application.ports import LLMProvider
from risklens.application.services.extraction_service import extract_from_text
from risklens.core.config import settings
from risklens.domain.schemas import SCHEMA_REGISTRY
from risklens.infrastructure.ai import runtime
from risklens.infrastructure.db import repository as repo

_SCALAR_TYPES = {str, int, float, bool}
_LIST_KEY_PREFERENCES = ("flag", "name", "factor", "key", "label", "title")
_LOWER_IS_BETTER = {"score_mae"}


def _evaluate_thresholds(metrics: dict, thresholds: dict | None) -> tuple[dict, bool, dict]:
    """Evaluate per-metric pass/fail. Definition thresholds override global
    defaults; metrics not measured are skipped (do not fail the gate)."""
    defaults = settings.eval_default_thresholds or {}
    effective = {**defaults, **(thresholds or {})}
    results: dict[str, dict] = {}
    for metric, threshold in effective.items():
        value = metrics.get(metric)
        if value is None:
            results[metric] = {"threshold": threshold, "value": None, "pass": None}
            continue
        ok = float(value) <= float(threshold) if metric in _LOWER_IS_BETTER else float(value) >= float(threshold)
        results[metric] = {"threshold": threshold, "value": value, "pass": ok}
    passed = all(r["pass"] is not False for r in results.values())
    return results, passed, effective


def _jaccard(a: str, b: str) -> float:
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


def _union_args(ann):
    origin = get_origin(ann)
    if origin in (Union, UnionType):
        return [a for a in get_args(ann) if a is not type(None)]
    return None


def _is_scalar(t) -> bool:
    if t in _SCALAR_TYPES:
        return True
    return get_origin(t) is Literal


def _scalar_field_names(model_cls) -> list[str]:
    """Names of fields holding a single scalar (str/int/float/bool/Literal/Optional)."""
    names = []
    for name, field in model_cls.model_fields.items():
        args = _union_args(field.annotation)
        candidates = args if args is not None else [field.annotation]
        if candidates and all(_is_scalar(t) for t in candidates):
            names.append(name)
    return names


def _list_field_items(model_cls) -> dict[str, type | None]:
    """Name -> item type for list-typed fields (None when the item is primitive)."""
    out = {}
    for name, field in model_cls.model_fields.items():
        origin = get_origin(field.annotation)
        if origin is list:
            out[name] = get_args(field.annotation)[0]
    return out


def _item_key(item_cls) -> str | None:
    """Field used to compare list items by identity (e.g. RedFlag.flag)."""
    if not isinstance(item_cls, type) or not hasattr(item_cls, "model_fields"):
        return None
    fields = item_cls.model_fields
    for preferred in _LIST_KEY_PREFERENCES:
        if preferred in fields:
            return preferred
    for name, field in fields.items():
        if _is_scalar(field.annotation) or (
            _union_args(field.annotation) and all(_is_scalar(t) for t in _union_args(field.annotation))
        ):
            return name
    return None


def _extract_keys(items: list, key: str | None) -> set[str]:
    out = set()
    for item in items:
        if isinstance(item, dict) and key and key in item:
            out.add(str(item[key]).lower())
        else:
            out.add(str(item).lower())
    return out


def _compare(expected: dict, actual: dict, model_cls) -> dict:
    """Per-case metrics. ``expected``/``actual`` are dumped dicts of the schema."""
    scalars = _scalar_field_names(model_cls)
    exact = [f for f in scalars if expected.get(f) == actual.get(f)]
    fuzz = [_jaccard(str(expected.get(f, "") or ""), str(actual.get(f, "") or "")) for f in scalars]

    score_field = next(
        (f for f in scalars if f in ("overall_risk_score", "score", "risk_score")),
        (scalars[0] if scalars else None),
    )
    score_mae: float | None = None
    if score_field is not None:
        exp_score, act_score = expected.get(score_field), actual.get(score_field)
        if isinstance(exp_score, (int, float)) and isinstance(act_score, (int, float)):
            score_mae = abs(float(exp_score) - float(act_score))

    decision_field = next((f for f in scalars if f == "decision"), None)
    decision_match = decision_field is not None and expected.get(decision_field) == actual.get(decision_field)

    list_items = _list_field_items(model_cls)
    rf_field = next((f for f in list_items if f in ("red_flags", "flags", "alerts")), None)
    rf_expected = rf_found = 0
    recall = 1.0
    if rf_field is not None:
        key = _item_key(list_items[rf_field])
        exp_flags = _extract_keys(expected.get(rf_field) or [], key)
        act_flags = _extract_keys(actual.get(rf_field) or [], key)
        rf_expected, rf_found = len(exp_flags), len(act_flags)
        matched = exp_flags & act_flags
        recall = len(matched) / len(exp_flags) if exp_flags else 1.0

    return {
        "field_exact": len(exact),
        "field_total": len(scalars),
        "fuzzy": round(sum(fuzz) / len(fuzz), 4) if fuzz else 0.0,
        "score_mae": round(score_mae, 1) if score_mae is not None else None,
        "decision_match": decision_match,
        "redflag_recall": round(recall, 4),
        "redflag_expected": rf_expected,
        "redflag_found": rf_found,
    }


async def _llm_judge(llm: LLMProvider, *, expected: dict, actual: dict) -> float:
    prompt = (
        "Compare a extração real com a esperada e avalie a qualidade (0 a 5, 5 = perfeita). "
        'Responda APENAS JSON: {"score": 0-5, "justification": string}.\n'
        f"Esperado: {json.dumps(expected, ensure_ascii=False)}\n"
        f"Real: {json.dumps(actual, ensure_ascii=False)}"
    )
    raw = await llm.complete(
        system="Você é um avaliador de qualidade de extração estruturada.",
        user=prompt,
        max_tokens=200,
        temperature=0,
    )
    from risklens.infrastructure.ai.json_utils import parse_json_output

    try:
        return float(parse_json_output(raw).get("score", 0.0))
    except Exception:
        return 0.0


async def run_eval(
    llm: LLMProvider,
    *,
    eval_run_id: UUID,
    name: str,
    cases: list[dict],
    schema_name: str = "credit_report",
    thresholds: dict | None = None,
) -> dict:
    """Run the extraction pipeline over a definition's cases and persist metrics.

    ``cases`` come from an ``EvalDefinition`` row: each has ``document_text``
    (snapshot) and ``expected``. The validated ``expected`` is snapshotted into
    each run item so historical diffs never change if the definition is edited.
    ``thresholds`` are per-definition overrides of the global defaults; the run
    persists ``passed`` + ``threshold_results`` for the quality gate.
    """
    schema_cls = SCHEMA_REGISTRY.get(schema_name)
    if schema_cls is None:
        raise ValueError(f"schema desconhecido: {schema_name}")

    items: list[dict] = []
    agg = {
        "field_exact_accuracy": 0.0,
        "field_fuzzy_similarity": 0.0,
        "score_mae": None,
        "decision_accuracy": 0.0,
        "redflag_recall": 0.0,
        "llm_judge_score": None,
        "n_cases": len(cases),
    }

    total_exact = total_fields = 0
    fuzz_sum = 0.0
    decision_ok = 0
    recall_sum = 0.0
    judge_sum = 0.0
    judge_n = 0

    for index, case in enumerate(cases):
        src_name = case.get("document_file") or f"caso {index + 1}"
        text = case.get("document_text") or ""
        if not text:
            items.append(
                {
                    "case": src_name,
                    "index": index,
                    "status": "failed",
                    "error": "document_text vazio",
                }
            )
            continue
        result: dict = {"case": src_name, "index": index, "status": "completed"}
        try:
            expected = schema_cls.model_validate(case["expected"]).model_dump()
            result["expected"] = expected  # immutable snapshot for historical diffs
            actual, _, _ = await extract_from_text(llm, text=text, schema_name=schema_name)
            cmp = _compare(expected, actual, schema_cls)
            result["metrics"] = cmp
            result["actual"] = actual

            total_exact += cmp["field_exact"]
            total_fields += cmp["field_total"]
            fuzz_sum += cmp["fuzzy"]
            if cmp["decision_match"]:
                decision_ok += 1
            recall_sum += cmp["redflag_recall"]
            if cmp["score_mae"] is not None:
                if agg["score_mae"] is None:
                    agg["score_mae"] = 0.0
                agg["score_mae"] = round(float(agg["score_mae"]) + cmp["score_mae"], 2)

            if runtime.get_cached_config()["ff_eval_llm_judge"]:
                judge = await _llm_judge(llm, expected=expected, actual=actual)
                judge_sum += judge
                judge_n += 1
                result["llm_judge"] = judge
        except Exception as exc:
            result["status"] = "failed"
            result["error"] = str(exc)[:500]
        items.append(result)

    n = len(cases)
    agg["field_exact_accuracy"] = round(total_exact / total_fields, 4) if total_fields else 0.0
    agg["field_fuzzy_similarity"] = round(fuzz_sum / n, 4) if n else 0.0
    agg["decision_accuracy"] = round(decision_ok / n, 4) if n else 0.0
    agg["redflag_recall"] = round(recall_sum / n, 4) if n else 0.0
    if agg["score_mae"] is not None:
        agg["score_mae"] = round(agg["score_mae"] / n, 2)
    if judge_n:
        agg["llm_judge_score"] = round(judge_sum / judge_n, 2)

    failed = sum(1 for i in items if i["status"] == "failed")
    final_status = "completed" if failed == 0 else "completed_with_failures"

    threshold_results, passed, effective = _evaluate_thresholds(agg, thresholds)
    agg["thresholds"] = effective
    agg["threshold_results"] = threshold_results
    agg["passed"] = passed

    await repo.finish_eval_run(eval_run_id, status=final_status, metrics=agg, items=items)
    return agg
