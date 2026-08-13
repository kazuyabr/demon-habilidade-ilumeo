# RiskLens — Plataforma de Inteligência de Risco

Case técnico (projeto de demonstração): uma plataforma que ajuda gestores a tomarem
decisões de risco complexas a partir de dados não estruturados. Um analista sobe
relatórios de due diligence → o sistema extrai um perfil de risco estruturado (com
redação de PII) → indexa o conteúdo para RAG (pgvector) → gestores fazem perguntas
e um **agente orquestrado** produz análises multi-etapa com citações → um harness de
**evals** mede a qualidade das extrações para prevenir regressão.

## Stack

- **API**: Python 3.12 · FastAPI (async) · SQLAlchemy 2.0 async · Pydantic v2 · Alembic
- **DB/vector**: PostgreSQL 16 + pgvector · **Fila/cache**: Redis + arq (worker)
- **IA**: LM Studio (OpenAI-compatible) — `google/gemma-3-4b` + `text-embedding-nomic-embed-text-v1.5`;
  camada anticorrupção permite trocar para OpenAI/Anthropic/Ollama via env
- **Front**: Next.js 16 (App Router, SSR) · Tailwind 4 · shadcn/ui · TanStack Query
- **Observabilidade**: OpenTelemetry · **Segurança**: OAuth2 + JWT, RBAC, Argon2, PII redaction
- **Infra**: docker-compose (dev) · Terraform GCP de referência · CI em camadas

## Estrutura

```
apps/api/      → FastAPI + worker (arq) + Alembic + testes
apps/web/      → Next.js 16 (SSR + Route Handlers)
samples/       → relatórios de exemplo + golden set dos evals
infra/         → docker-compose.yml · terraform/gcp (referência)
.github/       → workflow CI + pull_request_template
```

## Como rodar

> Guia passo a passo completo em `.vibecoding/passo-de-uso/` (material de estudo do
> autor, fora do git).

### 1. Pré-requisitos

- Docker Desktop, Node 22, pnpm, uv, LM Studio
- **LM Studio**: carregue `google/gemma-3-4b` e `text-embedding-nomic-embed-text-v1.5` e
  ligue o servidor em `127.0.0.1:1234`

### 2. Infra

```bash
cp .env.example .env
docker compose up -d          # Postgres+pgvector e Redis
```

### 3. API + worker

```bash
cd apps/api
uv sync
uv run alembic upgrade head   # cria tabelas + extensão vector
uv run risklens-seed          # cria admin@risklens.local / Admin@12345
uv run risklens-worker        # (janela 2) processa a fila
uv run uvicorn risklens.main:app --host 127.0.0.1 --port 8010 --reload   # (janela 3)
```

### 4. Web

```bash
cd apps/web
cp .env.example .env.local
pnpm install
pnpm dev                     # http://127.0.0.1:3000
```

Login: `admin@risklens.local` / `Admin@12345`

### 5. Smoke test (valida o ambiente inteiro)

```bash
cd apps/api
uv run python -m risklens.scripts.smoke
```

## Testes

```bash
cd apps/api
uv run pytest tests/unit -q       # rápidos, sem infra
uv run pytest tests/integration   # requer Postgres/Redis (docker compose)
.venv/Scripts/ruff check src      # lint
cd apps/web && pnpm run typecheck && pnpm run build
```

## Feature flags (server-side, sem deploy)

| Flag | Efeito |
|---|---|
| `FF_AGENT_REVIEW_ENABLED` | liga/desliga a etapa de revisão sênior do agente |
| `FF_RAG_HYBRID_SEARCH` | busca híbrida (vetorial + FTS) vs só vetorial |
| `FF_EVAL_LLM_JUDGE` | LLM-as-judge nos evals |

## Modelo Git

- `main` sempre deployável; branches `feat/<área>-<tema>`; Conventional Commits;
  PRs com template; tags `vX.Y.Z`.
- `.vibecoding/` é material de estudo local e **não faz parte do repositório versionado**
  (não usar `git add .` — stage explícito).
