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
- **IA**: LM Studio (OpenAI-compatible) — `google/gemma-3-4b` + `text-embedding-nomic-embed-text-v1.5`; camada anticorrupção permite trocar para OpenAI/Anthropic/Ollama via env
- **Front**: Next.js 15 (App Router, SSR) · Tailwind · shadcn/ui · TanStack Query
- **Observabilidade**: OpenTelemetry · **Segurança**: OAuth2 + JWT, RBAC, Argon2, PII redaction

## Repositórios / modelo Git

- `main` sempre deployável; branches `feat/<área>-<tema>`; Conventional Commits;
  PRs com template; tags `vX.Y.Z`.
- O diretório `.vibecoding/` contém material didático e guia passo a passo do autor
  e **não faz parte do repositório versionado** (fica apenas local).

## Como rodar (resumo)

1. Copie `.env.example` para `.env` e ajuste se preciso.
2. Suba a infra: `docker compose up -d` (Postgres+pgvector e Redis).
3. API: `cd apps/api && uv sync && uv run alembic upgrade head && uv run seed && uv run uvicorn risklens.main:app --port 8010 --reload`
4. Worker: `cd apps/api && uv run arq risklens.worker.main.WorkerSettings`
5. Web: `cd apps/web && pnpm install && pnpm dev`
6. LM Studio: carregue os modelos e ligue o servidor local em `127.0.0.1:1234`.

> Guia completo passo a passo em `.vibecoding/passo-de-uso/` (fora do git).
