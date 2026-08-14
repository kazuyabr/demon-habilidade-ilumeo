# Architecture

RiskLens is a risk-intelligence platform. Analysts upload unstructured due-diligence
reports; the system extracts a structured risk profile (with PII redaction), indexes the
content for retrieval-augmented generation, lets managers ask questions in natural
language (with citations), and measures extraction quality with an eval harness.

## Pipeline

```
Upload (web/API)
  → arq job (Redis queue)
  → worker:
      1. extract text            (md/txt/pdf)
      2. structured extraction   (LLM → JSON parse → Pydantic validation → repair loop)
      3. PII redaction           (deterministic regex, before persistence)
      4. chunk + embed           (768-dim vectors → pgvector)
Queries
  - RAG      : question → embed → hybrid search (cosine ANN + Postgres FTS) → answer with [n] citations
  - Agent    : plan → gather → analyze → review → final report (trace streamed via SSE)
  - Evals    : same extraction pipeline over a golden set → regression metrics
```

## Monolith, not microservices (a context decision)

The application is a **modular monolith**: domain/application/infrastructure layers with
product modules (`ingestion`, `extraction`, `rag`, `agents`, `evals`) isolated by
interfaces. This is a deliberate, context-driven choice:

- small team and domain, so a single deployable is cheaper to operate;
- extraction → indexing → querying are stages of one flow; a queue already decouples them
  temporally without a deployment split;
- transactional data (documents + extractions + chunks) lives in one Postgres — atomic,
  no sagas.

Each module would become a service by replacing its adapter, not by rewriting logic.
The trigger to split would be independent teams with autonomous deploys, asymmetric
scale, or a provider needing fault isolation.

## Ports & adapters (hexagonal / anti-corruption)

`application/ports.py` defines protocols the services depend on. Infrastructure adapters
implement them; swapping a vendor is a config change, not a code change:

| Port | Adapters |
|---|---|
| `LLMProvider` (chat) | OpenAI-compatible (OpenCode Zen, OpenAI, Groq, Gemini, LM Studio, Ollama), Anthropic, Vertex |
| `EmbeddingProvider` | OpenAI-compatible, fastembed (self-hosted ONNX), Vertex |
| `VectorStore` | pgvector |
| `DocumentStorage` | local filesystem (GCS/S3 behind the same port) |
| `JobQueue` | arq (Redis) — SQS/Pub/Sub behind the same port |

## Async & queue

- API is fully async (FastAPI + asyncpg + redis-py).
- Heavy work (extraction, indexing, agent runs, evals) runs on an **arq worker**;
  uploads respond immediately and the client tracks `pending → processing → completed`.
- The worker is serialized (`max_jobs=1`) because the local LLM serves one model at a
  time — predictable latency over throughput; scale is a config change for cloud
  providers.

## Multi-provider AI

Chat and embeddings are independent ports selected by env (`LLM_PROVIDER` /
`EMBEDDING_PROVIDER`), with a models.dev-style registry. See [`docs/providers.md`](providers.md).

## Frontend (Next.js 16)

- App Router, Server Components for SSR pages (dashboard, documents, detail); JWT lives
  in an httpOnly cookie and is consumed server-side by Route Handlers that proxy to the
  API — the browser never sees the token.
- RAG chat with citations, live agent trace over SSE (Redis pub/sub replayed from the DB),
  evals studio.
