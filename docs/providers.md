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
| **Cloud reliable (paid)** | **OpenCode Go (`deepseek-v4-flash`)** | fastembed (self-hosted) | **flat US$10/mo, no burst rate-limit — great for agents/evals** |
| Production (GCP) | Vertex (Gemini) | Vertex (`text-embedding-005`) | Workload Identity + Secret Manager |
| Production (portable) | OpenAI (`gpt-4o-mini`) | OpenAI (`text-embedding-3-small`) | one key, any cloud |
| Unmapped gateway | `custom` | `custom` | any OpenAI-compatible base URL |

## Per-model protocol (especificação por modelo)

OpenCode Zen/Go expose models through different API shapes, so each model in the
registry is tagged with its **protocol** and dispatched to the right adapter:

| Protocol | Endpoint | Adapter | Exemplos (Go) |
|---|---|---|---|
| `chat` | `/v1/chat/completions` | OpenAI-compatible | `deepseek-v4-flash`, `mimo-v2.5`, `glm-5.x`, `kimi-*`, `hy3` |
| `responses` | `/v1/responses` | OpenAI Responses API | `grok-4.5`, `gpt-5.6-luna` |
| `messages` | `/v1/messages` | Anthropic Messages | `qwen3.7-max`, `minimax-m3` |
| `google` | `/models/{id}:generateContent` | Gemini SDK | `gemini-3.7-flash` (Zen) |

`custom` (OpenAI-compatible) remains available for any gateway not mapped in the
registry — set `LLM_PROVIDER=custom` + `LLM_BASE_URL`/`LLM_API_KEY`.

## Bring Your Own Key (BYOK)

Per-user credentials live in the DB encrypted at rest (AES-256-GCM via
`CREDENTIALS_ENC_KEY`; dev fallback derives from `JWT_SECRET`). Each user stores their
own **host + api-key** per provider from the UI and the platform uses them for that
user's requests (RAG, documents, agent runs). Fields the user does not set fall back to
the deployment env. Secrets are never returned by the API — only the last 4 characters.

## Honest caveat: free tiers

The OpenCode Zen free tier is genuinely free (the `mimo-v2.5-free` model is cost 0) and
excellent for single-call flows (extraction, RAG). **Free tiers rate-limit bursts**:
multi-call agent orchestration can hit `429 FreeUsageLimitError`. For agent/evals-heavy
workloads, use a local model, a paid provider, or Vertex — the `.env` makes the switch
trivial.

## Chinese-provider models (Go gating)

The docs state Zen hosts all models in the US and Go provides global access; the `/models`
API does not expose hosting region. Models from Chinese providers (`deepseek-*`, `qwen-*`,
`glm-*`, `kimi-*`, `minimax-*`, `mimo-*`, `hy3`) may require enabling **"models hosted in
China"** on the Go subscription when a call fails with a permission error. The UI marks
these models and, on a permission-like connection failure, guides the client to
`opencode.ai/auth` instead of showing a raw error.

## Why separate chat and embeddings

The RAG embedder does not have to match the generator. Example: chat on OpenCode Zen
(free) + embeddings on fastembed (self-hosted, keyless) gives a zero-cost stack that runs
in Docker and cloud without any host dependency. All supported embedders emit 768 dims,
so switching keeps the pgvector column and vectors stable.
