# Design decisions & trade-offs

This project deliberately makes several trade-offs. Each is documented here with the
rationale, the alternative considered, and when the decision would change.

## 1. Worker serialized: `max_jobs = 1`

- **Why**: the local LLM (LM Studio) serves one model at a time; concurrent calls race
  model swap and return 400s. A single worker gives predictable per-job latency.
- **Trade-off**: lower throughput vs parallel execution. With a cloud provider (rate
  limits per API key, not VRAM) you scale horizontally — the queue distributes; the
  architecture is the same.

## 2. Resilient structured extraction (no `response_format`)

- **Why**: the local server rejects `response_format` (400) and even supported providers
  are not immune to malformed JSON on small models. The pipeline parses raw output
  (strip fences → balanced `{...}` slice), validates against a Pydantic schema, and runs
  a repair loop (2 retries) that feeds the validation error back to the model.
- **Trade-off**: a few extra tokens on failure vs hard dependency on a provider feature.
  Works identically across providers.

## 3. One schema = prompt + validation + API contract

`CreditRiskReport` (Pydantic) drives the LLM prompt (JSON Schema), validates the output,
and shapes the API response. Numeric values in `KeyMetric` are kept as strings on
purpose — LLMs make arithmetic mistakes; conversion is the consumer's job. Secondary
fields (e.g. red-flag evidence) are optional because models do not always capture them;
core fields (company, score, rating, decision) are required.

## 4. Fixed 768-dim embeddings

Every supported embedder emits **768 dims** (LM Studio nomic, fastembed nomic ONNX,
OpenAI text-embedding-3-small with `dimensions=768`, Vertex text-embedding-005 with
`output_dimensionality=768`). This keeps the pgvector `vector(768)` column and the
embedding space stable regardless of provider — no migration, interchangeable vectors.

## 5. DDD + anti-corruption layer

Domain/application layers depend on protocol interfaces (`application/ports.py`), never
on concrete vendors. Swapping LLM, vector store, storage or queue is env/config only.
This is what made "multi-provider" and "dockerize without host dependency" possible.

## 6. Postgres for everything transactional

Documents, extractions and chunks are atomic in one database (`ON DELETE CASCADE`).
JSONB columns absorb schema drift from AI output without migrations. pgvector keeps
relational + vectors in one store up to ~1M vectors; a dedicated vector DB becomes
worthwhile only at much larger scale. BigQuery is the analytical layer (evals/aggregates)
when volume grows — not the operational one.

## 7. Deterministic PII redaction

Regex-based masking (CPF, CNPJ, email, phone, card) applied to every string before
persistence — the API never returns raw PII. Deterministic, testable, zero inference
cost. An NER layer would add person-name coverage at the cost of determinism.

## 8. Idempotency

- Upload: content `sha256` is unique → re-upload returns the existing document
  (`duplicate: true`), no duplicate work.
- Jobs: `_job_id = aggregate_id` in arq → re-enqueueing an aggregate never duplicates.

## 9. JSONB over rigid schema for AI output

Extraction data, agent traces and eval metrics are JSONB. Trade-off: less type safety at
the DB boundary in exchange for no migrations when a schema evolves. Validation happens
in the application layer (Pydantic), not the database.

## 10. Runtime configuration (settings panel)

Env vars provide the baseline; a settings panel persists **overrides** in a single
`app_settings` JSONB row (no secrets — API keys stay in env/Secret Manager). The
effective config is cached in memory, and a Redis version counter lets the API and the
arq worker **rebuild providers lazily** when settings change — no redeploy. Feature flags
and RAG knobs (chunk size, top-k, hybrid search) resolve the same way, so tuning and
provider switches are runtime actions.
