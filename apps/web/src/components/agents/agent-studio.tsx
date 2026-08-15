"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Play, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { AgentRun, AgentStep } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  plan: "Planejamento",
  retrieve: "Recuperação",
  analyze: "Análise",
  review: "Revisão",
  final: "Final",
};

const KIND_COLOR: Record<string, string> = {
  plan: "bg-violet-100 text-violet-700 dark:bg-violet-950",
  retrieve: "bg-blue-100 text-blue-700 dark:bg-blue-950",
  analyze: "bg-amber-100 text-amber-700 dark:bg-amber-950",
  review: "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-950",
  final: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950",
};

function StepCard({ step }: { step: AgentStep }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="mb-1 flex items-center justify-between">
        <Badge className={cn(KIND_COLOR[step.kind] ?? "bg-zinc-100 dark:bg-zinc-800")}>
          {KIND_LABEL[step.kind] ?? step.kind}
        </Badge>
        <span className="text-[10px] text-muted-foreground">{new Date(step.ts).toLocaleTimeString("pt-BR")}</span>
      </div>
      {step.thought && <p className="text-xs italic text-muted-foreground">{step.thought}</p>}
      {step.action && (
        <p className="mt-1 text-xs">
          <span className="font-mono text-muted-foreground">ação:</span> {step.action}
        </p>
      )}
      {step.action_input && <p className="mt-0.5 text-xs text-muted-foreground line-clamp-3">{step.action_input}</p>}
      {step.observation && (
        <p className="mt-1 text-xs">
          <span className="font-mono text-muted-foreground">observação:</span> {step.observation}
        </p>
      )}
      {step.output && <p className="mt-1 text-xs font-medium whitespace-pre-wrap">{step.output}</p>}
    </div>
  );
}

function ReportView({ result }: { result: Record<string, unknown> | null }) {
  if (!result) return null;
  return (
    <Card className="border-emerald-300 dark:border-emerald-900">
      <CardHeader><CardTitle className="text-sm">Relatório final</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p>{String(result.summary ?? "")}</p>
        <div className="flex flex-wrap gap-2">
          <Badge>Risco {String(result.risk_score ?? "—")}/100</Badge>
          <Badge variant="outline">Rating {String(result.risk_rating ?? "—")}</Badge>
          <Badge variant="outline">Decisão: {String(result.decision ?? "—")}</Badge>
        </div>
        {Array.isArray(result.key_findings) && (
          <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
            {result.key_findings.map((f, i) => (
              <li key={i}>{String(f)}</li>
            ))}
          </ul>
        )}
        {Array.isArray(result.citations) && result.citations.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Fontes: {result.citations.join(", ")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function AgentStudio() {
  const [question, setQuestion] = useState("");
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [active, setActive] = useState<AgentRun | null>(null);
  const [running, setRunning] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const seenRef = useRef<Set<string>>(new Set());

  async function loadRuns() {
    const res = await fetch("/api/agents/runs");
    if (res.ok) setRuns(await res.json());
  }

  useEffect(() => {
    // initial data load from server — setState happens after an await
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadRuns();
    return () => esRef.current?.close();
  }, []);

  async function startRun() {
    if (!question.trim() || running) return;
    setRunning(true);
    seenRef.current = new Set();
    const res = await fetch("/api/agents/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) {
      setRunning(false);
      return;
    }
    const run = (await res.json()) as AgentRun;
    setActive(run);
    setQuestion("");

    const es = new EventSource(`/api/agents/runs/${run.id}/stream`);
    esRef.current = es;
    es.onmessage = (ev) => {
      const step = JSON.parse(ev.data) as AgentStep;
      if (seenRef.current.has(step.ts)) return;
      seenRef.current.add(step.ts);
      setActive((prev) => {
        if (!prev) return prev;
        const exists = (prev.trace ?? []).some((s) => s.ts === step.ts);
        return exists ? prev : { ...prev, trace: [...(prev.trace ?? []), step] };
      });
    };
    es.addEventListener("done", () => {
      es.close();
      setActive((prev) => (prev ? { ...prev, status: prev.status } : prev));
      setRunning(false);
      loadRuns();
    });
  }

  const steps = active?.trace ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
      <div className="space-y-4">
        <Card>
          <CardHeader><CardTitle className="text-sm">Nova análise</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              placeholder="Ex.: Analise o risco de crédito da Transportadora Estrela."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
            />
            <Button className="w-full" onClick={startRun} disabled={running || !question.trim()}>
              {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
              {running ? "Executando…" : "Iniciar análise"}
            </Button>
            <p className="text-xs text-muted-foreground">
              O agente executa plan → retrieve → analyze → review → final. Trace chega ao vivo via SSE (Redis pub/sub).
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-sm">Histórico ({runs.length})</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {runs.map((r) => (
              <button
                key={r.id}
                onClick={() => setActive(r)}
                className="w-full rounded-md border px-3 py-2 text-left hover:bg-accent"
              >
                <p className="truncate text-sm">{r.question}</p>
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
            {runs.length === 0 && <p className="text-sm text-muted-foreground">Nenhuma análise ainda.</p>}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        {active ? (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Execução em andamento</CardTitle>
                <p className="text-xs text-muted-foreground">{active.question}</p>
              </CardHeader>
              <CardContent className="space-y-2">
                {steps.length === 0 && !running && (
                  <p className="text-sm text-muted-foreground">Sem passos registrados.</p>
                )}
                {steps.map((s, i) => (
                  <StepCard key={`${s.ts}-${i}`} step={s} />
                ))}
                {running && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <Bot className="h-4 w-4" /> agente pensando…
                  </div>
                )}
              </CardContent>
            </Card>
            {active.result && <ReportView result={active.result} />}
          </>
        ) : (
          <Card>
            <CardContent className="py-16 text-center">
              <Sparkles className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Inicie uma análise ou selecione uma do histórico para ver o trace do agente.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
