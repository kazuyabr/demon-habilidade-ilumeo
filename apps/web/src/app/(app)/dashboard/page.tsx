import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { backendFetch } from "@/lib/api";
import type { AgentRun, DocumentItem, EvalRun, FeatureFlags } from "@/lib/types";
import { STATUS_COLORS } from "@/lib/types";
import Link from "next/link";

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// One failing endpoint must not crash the whole page (SSR resilience).
async function safeFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const [docs, evals, agents, flags] = await Promise.all([
    safeFetch(() => backendFetch<DocumentItem[]>("/documents?limit=200")),
    safeFetch(() => backendFetch<EvalRun[]>("/evals/runs")),
    safeFetch(() => backendFetch<AgentRun[]>("/agents/runs")),
    safeFetch(() => backendFetch<FeatureFlags>("/admin/flags")),
  ]);

  const docList = docs ?? [];
  const completed = docList.filter((d) => d.status === "completed");
  const lastEval = evals?.[0] ?? null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <span>
            Chat: <span className="font-mono">{flags?.llm_provider ?? "—"}</span>{" "}
            <span className="font-mono">{flags?.llm_model ?? "—"}</span>
          </span>
          <span>
            Embeddings: <span className="font-mono">{flags?.embedding_provider ?? "—"}</span>{" "}
            <span className="font-mono">{flags?.embedding_model ?? "—"}</span>{" "}
            {flags?.embedding_dims ? `(${flags.embedding_dims}d)` : ""}
          </span>
          <span>
            RAG híbrido: {flags ? (flags.rag_hybrid_search ? "ligado" : "desligado") : "—"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Documentos</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{docList.length}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Processados</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold text-emerald-600">{completed.length}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Análises (agente)</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{agents?.length ?? 0}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Evals</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{evals?.length ?? 0}</p></CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Última avaliação de extração</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {lastEval ? (
              <>
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-mono text-xs">{lastEval.name}</span>
                  <Badge variant="outline">{lastEval.status}</Badge>
                </div>
                {lastEval.metrics && (
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground">Decisão</p>
                      <p className="font-semibold">
                        {Math.round(((lastEval.metrics.decision_accuracy as number) ?? 0) * 100)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Fuzzy</p>
                      <p className="font-semibold">
                        {((lastEval.metrics.field_fuzzy_similarity as number) ?? 0).toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">LLM judge</p>
                      <p className="font-semibold">{String(lastEval.metrics.llm_judge_score ?? "—")}</p>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Nenhuma avaliação ainda. Rode em Evals.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-sm">Documentos recentes</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {completed.slice(0, 6).map((d) => (
              <Link
                key={d.id}
                href={`/documents/${d.id}`}
                className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-accent"
              >
                <span className="truncate text-sm">{d.title}</span>
                <span className="ml-2 flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                  <span className={`h-2 w-2 rounded-full ${STATUS_COLORS[d.status]}`} />
                  {fmtDate(d.created_at)}
                </span>
              </Link>
            ))}
            {completed.length === 0 && (
              <p className="text-sm text-muted-foreground">Nenhum documento processado ainda.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
