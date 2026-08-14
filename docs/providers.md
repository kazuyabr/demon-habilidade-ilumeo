# Multi-provider AI

The AI layer is decoupled from any single vendor. Chat and embeddings are independent
ports (`LLMProvider` / `EmbeddingProvider`) selected by environment variables, with a
curated registry (models.dev-style) in `apps/api/src/risklens/infrastructure/ai/registry.py`,
exposed at `GET /api/v1/admin/providers`.

## Configuration

```ini
# Chat
LLM_PROVIDER=lmstudio          # opencode | openai | anthropic | google | groq | lmstudio | ollama | vertex | custom
LLM_MODEL=google/gemma-3-4b
# Embeddings (independent — the RAG embedder can differ from the generator)
EMBEDDING_PROVIDER=lmstudio    # openai | lmstudio | ollama | fastembed | vertex | custom
EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
EMBEDDING_DIMS=768             # fixed across providers (see docs/design.md)
# Per-provider credentials (only the one in use needs to exist)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
OPENCODE_API_KEY=
VERTEX_PROJECT=
VERTEX_REGION=us-central1
VERTEX_API_KEY=
```

Switching providers is a `.env` change; no code changes.

## Scenarios

| Scenario | Chat | Embeddings | Notes |
|---|---|---|---|
| Offline dev / demo | LM Studio | LM Studio | no keys, no internet, reliable |
| Cloud free | OpenCode Zen (`mimo-v2.5-free`) | fastembed (self-hosted) | zero cost, no host dependency |
| Production (GCP) | Vertex (Gemini) | Vertex (`text-embedding-005`) | Workload Identity + Secret Manager |
| Production (portable) | OpenAI (`gpt-4o-mini`) | OpenAI (`text-embedding-3-small`) | one key, any cloud |

## Honest caveat: free tiers

The OpenCode Zen free tier is genuinely free (the `mimo-v2.5-free` model is cost 0) and
excellent for single-call flows (extraction, RAG). **Free tiers rate-limit bursts**:
multi-call agent orchestration can hit `429 FreeUsageLimitError`. For agent/evals-heavy
workloads, use a local model, a paid provider, or Vertex — the `.env` makes the switch
trivial.

## Why separate chat and embeddings

The RAG embedder does not have to match the generator. Example: chat on OpenCode Zen
(free) + embeddings on fastembed (self-hosted, keyless) gives a zero-cost stack that runs
in Docker and cloud without any host dependency. All supported embedders emit 768 dims,
so switching keeps the pgvector column and vectors stable.
