# Contribuindo

## Fluxo de trabalho (Git)

- `main` é a única linha **sempre deployável**. Nada quebrado em `main`.
- Trabalhe em branches curtos e descritivos: `feat/<área>-<tema>` (ex.: `feat/api-core`, `feat/rag-hybrid`), `fix/<desc>`, `docs/<desc>`.
- Todo merge em `main` acontece via **Pull Request** com `--no-ff` (merge commit), preservando a intenção do branch.
- Versões via tags semânticas em `main`: `v0.1.0`.

## Mensagens de commit (Conventional Commits)

Formato: `<tipo>(<escopo>): <resumo>`

Tipos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `perf`, `build`.

- Resumo no **imperativo**, ≤ 72 caracteres.
- Corpo explica o **porquê** (contexto/decidir), não o quê.
- Escopo opcional indica a camada: `api`, `web`, `extraction`, `rag`, `agent`, `evals`, `infra`.

Exemplos:

```
feat(extraction): add resilient JSON parse with repair fallback

gemma-3-4b often wraps JSON in fences or truncates; parse now strips
fences, tries Pydantic validation and retries once with a repair prompt.
```

```
fix(rag): dedupe citations across overlapping chunks

Overlapping chunk windows returned the same source twice. Collect
sources by document + page before rendering citations.
```

## Pull Requests

Use o template em `.github/pull_request_template.md`. Preencha sempre:

- **Contexto** (por que existe a feature, não o que faz).
- **Mudanças** (arquivos/camadas afetadas).
- **Como testar** (passos reproduzíveis).
- **Checklist** de qualidade (testes, lint, segurança/PII).

## Qualidade

- Lint/format: `ruff` (`cd apps/api && uv run ruff check .`).
- Testes em camadas: unitários (rápidos, sem infra) e integração (Postgres/Redis).
- Cobertura de segurança: não logar PII, não commitar secrets, usar `.env`.
