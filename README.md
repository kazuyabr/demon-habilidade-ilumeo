# RiskLens — Plataforma de Inteligência de Risco

Case técnico (projeto de demonstração): uma plataforma que ajuda gestores a tomarem
decisões de risco complexas a partir de dados não estruturados. Um analista sobe
relatórios de due diligence → o sistema extrai um perfil de risco estruturado (com
redação de PII) → indexa o conteúdo para RAG (pgvector) → gestores fazem perguntas
e um **agente orquestrado** produz análises multi-etapa com citações → um harness de
**evals** mede a qualidade das extrações para prevenir regressão — com **definições de
eval gerenciáveis pelo painel** (casos + expected, provider/modelo por execução).

## Stack

- **API**: Python 3.12 · FastAPI (async) · SQLAlchemy 2.0 async · Pydantic v2 · Alembic
- **DB/vector**: PostgreSQL 16 + pgvector · **Fila/cache**: Redis + arq (worker)
- **IA (multi-provider)**: chat e embeddings **selecionáveis por env** (registry no estilo
  models.dev). Chat: LM Studio · OpenCode Zen (`mimo-v2.5-free`, grátis) · OpenAI · Anthropic ·
  Google Gemini · Groq · Vertex. Embeddings: LM Studio · fastembed (self-hosted, sem chave) ·
  OpenAI · Vertex — todos em **768 dims** (pgvector `vector(768)` inalterado)
- **Front**: Next.js 16 (App Router, SSR) · Tailwind 4 · shadcn/ui · TanStack Query · dark mode (default escuro + toggle)
- **Observabilidade**: OpenTelemetry · **Segurança**: OAuth2 + JWT, RBAC, Argon2, PII redaction
- **Infra**: docker-compose (stack completa: postgres/redis/migrate/seed/api/worker/web) · Terraform GCP de referência · CI em camadas

## Estrutura

```
apps/api/      → FastAPI + worker (arq) + Alembic + testes
apps/web/      → Next.js 16 (SSR + Route Handlers)
samples/       → relatórios de exemplo + golden set dos evals
infra/         → terraform/gcp (referência) · docker-compose.yml na raiz
docs/          → arquitetura · decisões de design · providers · evals
.github/       → workflow CI + pull_request_template
```

## Documentação

- [docs/architecture.md](docs/architecture.md) — pipeline, monólito modular, ports & adapters, fila async
- [docs/design.md](docs/design.md) — decisões-chave e trade-offs (worker serial, extração resiliente, 768 dims, PII, idempotência)
- [docs/providers.md](docs/providers.md) — configuração multi-provider (LM Studio / opencode free / Vertex / OpenAI) e cenários
- [docs/evals.md](docs/evals.md) — harness de avaliação e resultados medidos

## Como rodar

> Guia passo a passo completo em `.vibecoding/passo-de-uso/` (material de estudo do
> autor, fora do git).

### Opção 1 — Tudo via Docker (recomendado)

```bash
# 1. LM Studio (para a IA local): carregue google/gemma-3-4b e
#    text-embedding-nomic-embed-text-v1.5 e ligue o servidor em 127.0.0.1:1234
#    (o compose acessa via host.docker.internal)

# 2. Suba a stack inteira (Postgres, Redis, migrate, seed, api, worker, web)
docker compose up --build -d

# 3. Acesse
#    Web:  http://127.0.0.1:3000   (admin@risklens.local / Admin@12345)
#    API:  http://127.0.0.1:8010/health

# Smoke test contra a stack dockerizada (a partir da raiz do repo):
#   cd apps/api && .venv/Scripts/python -m risklens.scripts.smoke
```

> A IA é **multi-provider via `.env`/compose**: o default do docker usa **LM Studio local**
> (confiável/offline). Para **cloud grátis** (`opencode` + `fastembed`, sem chave) ou
> **produção** (`vertex`/`openai`), edite o bloco `environment` do compose — ver
> [docs/providers.md](docs/providers.md).

### Opção 2 — App nativo (dev iterativo)

#### 1. Pré-requisitos

- Docker Desktop, Node 22, pnpm, uv, LM Studio
- **LM Studio**: carregue `google/gemma-3-4b` e `text-embedding-nomic-embed-text-v1.5` e
  ligue o servidor em `127.0.0.1:1234`

#### 2. Infra

```bash
cp .env.example .env
docker compose up -d postgres redis   # só a infra (ou omita e suba tudo)
```

#### 3. API + worker

```bash
cd apps/api
uv sync
uv run alembic upgrade head   # cria tabelas + extensão vector
uv run risklens-seed          # cria admin@risklens.local / Admin@12345
uv run risklens-worker        # (janela 2) processa a fila
uv run uvicorn risklens.main:app --host 127.0.0.1 --port 8010 --reload   # (janela 3)
```

#### 4. Web

```bash
cd apps/web
cp .env.example .env.local
pnpm install
pnpm dev                     # http://127.0.0.1:3000
```

Login: `admin@risklens.local` / `Admin@12345`

#### 5. Smoke test (valida o ambiente inteiro)

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
