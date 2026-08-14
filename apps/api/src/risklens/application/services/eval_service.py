"""Eval harness: regression quality measurement for structured extraction.

Runs the SAME extraction pipeline used in production over a golden set of
documents with expected JSON, then computes metrics. This is how a model/
prompt change is gated before deploy — the LLM-regression story.

Metrics:
- field_exact_accuracy   fraction of fields that match exactly
- field_fuzzy_similarity mean token-Jaccard across string fields
- score_mae              mean absolute error on overall_risk_score
- decision_accuracy      decision match rate
- redflag_recall         red flags found / expected
- llm_judge_score        (feature flag) 0-5 grading by the LLM itself
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from risklens.application.ports import LLMProvider
from risklens.application.services.extraction_service import extract_from_text
from risklens.core.config import settings
from risklens.domain.schemas import CreditRiskReport
from risklens.infrastructure.ai import runtime
from risklens.infrastructure.db import repository as repo


def _jaccard(a: str, b: str) -> float:
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


def _compare(expected: dict, actual: dict) -> dict:
    fields = ["company_name", "sector", "analysis_date", "risk_rating", "recommended_limit"]
    exact = [f for f in fields if expected.get(f) == actual.get(f)]
    fuzz = [_jaccard(str(expected.get(f, "") or ""), str(actual.get(f, "") or "")) for f in fields]

    exp_score = expected.get("overall_risk_score")
    act_score = actual.get("overall_risk_score")
    score_ok = isinstance(exp_score, (int, float)) and isinstance(act_score, (int, float))
    score_mae = abs(float(exp_score) - float(act_score)) if score_ok else None

    exp_flags = {str(f.get("flag", "")).lower() for f in expected.get("red_flags", [])}
    act_flags = {str(f.get("flag", "")).lower() for f in actual.get("red_flags", [])}
    matched = exp_flags & act_flags
    recall = len(matched) / len(exp_flags) if exp_flags else 1.0

    return {
        "field_exact": len(exact),
        "field_total": len(fields),
        "fuzzy": round(sum(fuzz) / len(fuzz), 4) if fuzz else 0.0,
        "score_mae": round(score_mae, 1) if score_mae is not None else None,
        "decision_match": expected.get("decision") == actual.get("decision"),
        "redflag_recall": round(recall, 4),
        "redflag_expected": len(exp_flags),
        "redflag_found": len(act_flags),
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


async def run_eval(llm: LLMProvider, *, eval_run_id: UUID, name: str) -> dict:
    golden_dir = Path(settings.samples_dir) / "golden"
    doc_dir = Path(settings.samples_dir) / "documents"
    golden_file = golden_dir / "credit_report.json"
    if not golden_file.exists():
        raise FileNotFoundError(f"golden set not found: {golden_file}")

    cases = json.loads(golden_file.read_text(encoding="utf-8"))
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

    for case in cases:
        src = doc_dir / case["document_file"]
        text = src.read_text(encoding="utf-8") if src.exists() else ""
        expected = CreditRiskReport.model_validate(case["expected"]).model_dump()
        result: dict = {"case": case["document_file"], "status": "completed"}
        try:
            actual, _, _ = await extract_from_text(llm, text=text, schema_name="credit_report")
            cmp = _compare(expected, actual)
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
            recall_sum += 0.0
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
    await repo.finish_eval_run(
        eval_run_id, status=final_status, metrics=agg, items=items
    )
    return agg
