# RiskLens · Web

Frontend Next.js 16 (App Router) da plataforma de inteligência de risco.

- **SSR**: páginas de Dashboard, Documentos e Detalhe são Server Components que buscam
  dados da API com o JWT lido de cookie httpOnly (o browser nunca vê o token).
- **Route Handlers** (`src/app/api/*`) fazem proxy servidor → API (upload, RAG, agentes,
  evals); o agente transmite o trace ao vivo via SSE.
- **Design System**: Tailwind 4 + shadcn/ui (radix) · TanStack Query · sonner toasts.

## Rodar

```bash
cp .env.example .env.local      # API_INTERNAL_URL=http://127.0.0.1:8010
pnpm install
pnpm dev                        # http://127.0.0.1:3000
```

Validação: `pnpm run typecheck` · `pnpm run lint` · `pnpm run build`.
