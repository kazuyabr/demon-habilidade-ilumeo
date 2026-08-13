"use client";

import { useCallback, useEffect, useState } from "react";
import { FlaskConical, Loader2, Play } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { EvalItem, EvalRun } from "@/lib/types";

const METRIC_LABELS: Record<string, string> = {
  decision_accuracy: "Acerto de decisão",
  field_exact_accuracy: "Acerto exato de campos",
  field_fuzzy_similarity: "Similaridade fuzzy",
  redflag_recall: "Recall de red flags",
  score_mae: "Erro médio de score",
  llm_judge_score: "Nota LLM judge (0–5)",
  n_cases: "Casos",
};

function Metric({ label, value }: { label: string; value: unknown }) {
  let display = String(value ?? "—");
  let highlight = false;
  if (typeof value === "number") {
    if (label.includes("accuracy") || label.includes("recall") || label.includes("similarity")) {
      display = `${(value * 100).toFixed(1)}%`;
      highlight = value >= 0.7;
    }
    if (label.includes("LLM")) display = value.toFixed(1);
  }
  return (
    <div className="rounded-md bg-accent/50 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("text-lg font-semibold", highlight && "text-emerald-600")}>{display}</p>
    </div>
  );
}

export function EvalStudio() {
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [selected, setSelected] = useState<EvalRun | null>(null);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const res = await fetch("/api/evals/runs");
    if (res.ok) {
      const list = (await res.json()) as EvalRun[];
      setRuns(list);
      if (!selected && list.length) setSelected(list[0]);
      const active = list.some((r) => r.status === "running");
      setRunning(active);
    }
    setLoading(false);
  }, [selected]);

  useEffect(() => {
    // initial data load + polling — setState happens after an await
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const id = setInterval(load, 3000); // poll while any run is active
    return () => clearInterval(id);
  }, [load]);

  async function startEval() {
    setRunning(true);
    const res = await fetch("/api/evals/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "credit-report-golden" }),
    });
    if (res.ok) {
      const run = (await res.json()) as EvalRun;
      setSelected(run);
      setTimeout(load, 500);
    } else {
      setRunning(false);
    }
  }

  const metrics = selected?.metrics ?? {};
  const items = selected?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Roda o mesmo pipeline de extração sobre o golden set (samples/golden) e mede regressões.
        </p>
        <Button onClick={startEval} disabled={running}>
          {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
          {running ? "Executando…" : "Rodar eval"}
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <Card className="h-fit">
          <CardHeader><CardTitle className="text-sm">Execuções ({runs.length})</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {loading && <p className="text-sm text-muted-foreground">Carregando…</p>}
            {runs.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelected(r)}
                className={cn(
                  "w-full rounded-md border px-3 py-2 text-left hover:bg-accent",
                  selected?.id === r.id && "bg-accent",
                )}
              >
                <p className="flex items-center gap-2 text-sm">
                  <FlaskConical className="h-3.5 w-3.5 text-muted-foreground" />
                  {r.name}
                </p>
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      r.status === "completed" ? "bg-emerald-500" : r.status === "failed" ? "bg-red-500" : "bg-blue-500",
                    )}
                  />
                  {r.status} · {new Date(r.created_at).toLocaleTimeString("pt-BR")}
                </p>
              </button>
            ))}
            {!loading && runs.length === 0 && <p className="text-sm text-muted-foreground">Nenhum eval ainda.</p>}
          </CardContent>
        </Card>

        <div className="space-y-4">
          {selected ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">{selected.name}</CardTitle>
                  <p className="text-xs text-muted-foreground">modelo: {selected.model_used}</p>
                </CardHeader>
                <CardContent>
                  {Object.keys(metrics).length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {running ? "Aguardando resultado…" : "Sem métricas ainda."}
                    </p>
                  ) : (
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                      {Object.entries(metrics)
                        .filter(([k]) => k in METRIC_LABELS)
                        .map(([k, v]) => (
                          <Metric key={k} label={METRIC_LABELS[k]} value={v} />
                        ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {items.length > 0 && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">Por caso</CardTitle></CardHeader>
                  <CardContent className="space-y-2">
                    {items.map((it) => {
                      const item = it as EvalItem;
                      const m = item.metrics;
                      return (
                        <div key={String(item.case)} className="rounded-md border px-3 py-2">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-medium">{String(item.case)}</p>
                            <Badge variant="outline">{String(item.status)}</Badge>
                          </div>
                          {m && (
                            <p className="mt-1 text-xs text-muted-foreground">
                              decisão: {String(m.decision_match)} · fuzzy: {(m.fuzzy ?? 0).toFixed(2)} · recall red
                              flags: {(m.redflag_recall ?? 0).toFixed(2)}
                              {typeof m.score_mae === "number" && ` · |Δscore|: ${m.score_mae}`}
                            </p>
                          )}
                          {item.error && <p className="mt-1 text-xs text-destructive">{String(item.error)}</p>}
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="py-16 text-center text-sm text-muted-foreground">
                Selecione uma execução ou rode um eval.
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
