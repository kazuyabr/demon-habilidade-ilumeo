# Evals: measuring extraction quality

LLM behavior is non-deterministic and versioned — a model or prompt change can silently
degrade extraction. The eval harness re-runs the **same production pipeline** over a
**golden set** (`samples/golden/credit_report.json`: 3 annotated reports) and produces
regression metrics, so model/prompt changes are gated instead of guessed.

Run it from the UI (Evals page) or the API: `POST /api/v1/evals/runs`.

## Metrics

| Metric | Definition |
|---|---|
| `decision_accuracy` | share of correct approve/conditional/decline decisions |
| `field_exact_accuracy` | share of fields matching exactly |
| `field_fuzzy_similarity` | mean token-Jaccard across string fields |
| `redflag_recall` | expected red flags found |
| `score_mae` | mean absolute error on the 0–100 risk score |
| `llm_judge_score` | LLM-as-judge rating (0–5) of actual vs expected |

## Results (measured, local model `google/gemma-3-4b`)

```
decision_accuracy         1.0
field_fuzzy_similarity    0.81
field_exact_accuracy      0.73
redflag_recall            0.44
score_mae                 ~13–15
llm_judge_score           4.0/5
```

Honest reading: the local 4B model gets every **decision** right and rates well overall,
but it only finds ~44% of expected red flags — good for a demo, not good enough for
production without review. This is exactly what the harness is for: measure before and
after a model/prompt change, block regressions, and justify provider upgrades with data
(e.g. expecting `redflag_recall > 0.7` on a stronger model).

## How it is used

- Regression gate for provider/prompt changes (CI-ready once the golden set grows).
- `EvalRun` is persisted (history) so quality evolution is visible over time.
- LLM-as-judge is a feature flag (`FF_EVAL_LLM_JUDGE`) because it costs extra calls and
  the judge should not be the same model producing the extraction.
