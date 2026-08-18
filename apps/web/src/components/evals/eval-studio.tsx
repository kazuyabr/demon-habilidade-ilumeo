"use client";

import { useCallback, useEffect, useState } from "react";
import {
  FlaskConical,
  Loader2,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type {
  DocumentItem,
  EvalCase,
  EvalDefinition,
  EvalDefinitionDetail,
  EvalItem,
  EvalRun,
  EvalValidateResult,
  ProviderRegistryEntry,
} from "@/lib/types";

const METRIC_LABELS: Record<string, string> = {
  decision_accuracy: "Acerto de decisão",
  field_exact_accuracy: "Acerto exato de campos",
  field_fuzzy_similarity: "Similaridade fuzzy",
  redflag_recall: "Recall de red flags",
  score_mae: "Erro médio de score",
  llm_judge_score: "Nota LLM judge (0–5)",
  n_cases: "Casos",
};

function pct(value: unknown): string {
  return typeof value === "number" ? `${(value * 100).toFixed(0)}%` : "—";
}

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

// ---------------------------------------------------------------------------
// Run model picker
// ---------------------------------------------------------------------------

interface ModelOption {
  value: string; // provider::model
  provider: string;
  model: string;
  label: string;
  free?: boolean;
}

function useModelOptions() {
  const [options, setOptions] = useState<ModelOption[]>([]);
  const [defaultValue, setDefaultValue] = useState<string>("");

  useEffect(() => {
    let active = true;
    fetch("/api/admin/providers")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { providers: ProviderRegistryEntry[]; active_chat: { provider: string; model: string } } | null) => {
        if (!data || !active) return;
        const opts: ModelOption[] = [];
        for (const p of data.providers) {
          if (!p.chat) continue;
          for (const m of p.chat_models) {
            opts.push({
              value: `${p.id}::${m.id}`,
              provider: p.id,
              model: m.id,
              label: `${p.label} · ${m.label}${m.free ? " (free)" : ""}`,
              free: m.free,
            });
          }
        }
        setOptions(opts);
        const activeValue = `${data.active_chat.provider}::${data.active_chat.model}`;
        if (opts.some((o) => o.value === activeValue) || opts.length === 0) {
          setDefaultValue(activeValue);
        } else {
          setDefaultValue(opts[0].value);
        }
      })
      .catch(() => {
        /* providers unavailable — run will fall back to the active model */
      });
    return () => {
      active = false;
    };
  }, []);

  return { options, defaultValue };
}

function RunDialog({
  definition,
  onClose,
  onRun,
}: {
  definition: EvalDefinition;
  onClose: () => void;
  onRun: (models: Array<{ provider: string; model: string }>) => Promise<void>;
}) {
  const { options, defaultValue } = useModelOptions();
  const [selected, setSelected] = useState<Set<string>>(() => new Set(defaultValue ? [defaultValue] : []));
  const [busy, setBusy] = useState(false);

  function toggle(value: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  async function submit() {
    setBusy(true);
    const models = [...selected].map((v) => {
      const [provider, model] = v.split("::");
      return { provider, model };
    });
    try {
      await onRun(models);
      onClose();
    } catch {
      /* toast handled by caller */
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Rodar {definition.title}</DialogTitle>
          <DialogDescription>
            {definition.n_cases} casos · schema {definition.schema_name}. Escolha 1 ou mais modelos —
            vários = comparação A/B na aba Execuções.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label>Provider / modelo (marque os desejados)</Label>
          {options.length === 0 ? (
            <p className="text-xs text-muted-foreground">Usando o modelo ativo (sem seletor disponível)…</p>
          ) : (
            <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border p-1.5">
              {options.map((o) => {
                const checked = selected.has(o.value);
                return (
                  <label
                    key={o.value}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                  >
                    <input type="checkbox" checked={checked} onChange={() => toggle(o.value)} className="h-4 w-4" />
                    <span className="truncate">{o.label}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={busy || selected.size === 0}>
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Executar{selected.size > 1 ? ` (${selected.size} modelos)` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Create/edit definition form
// ---------------------------------------------------------------------------

type CaseDraft = {
  source: "paste" | "document";
  document_file: string;
  docId: string;
  document_text: string;
  expectedJson: string;
  valid?: boolean | null;
};

const EMPTY_CASE: CaseDraft = {
  source: "paste",
  document_file: "",
  docId: "",
  document_text: "",
  expectedJson: "{}",
  valid: null,
};

function DefinitionFormDialog({
  definition,
  documents,
  onClose,
  onSave,
}: {
  definition: EvalDefinitionDetail | null; // null = create
  documents: DocumentItem[];
  onClose: () => void;
  onSave: (payload: {
    slug?: string;
    title: string;
    description: string | null;
    schema_name: string;
    cases: EvalCase[];
    thresholds: Record<string, number> | null;
  }) => Promise<void>;
}) {
  const [slug, setSlug] = useState(definition?.slug ?? "");
  const [title, setTitle] = useState(definition?.title ?? "");
  const [description, setDescription] = useState(definition?.description ?? "");
  const [schemaName, setSchemaName] = useState(definition?.schema_name ?? "credit_report");
  const [thresholds, setThresholds] = useState<Record<string, string>>(() => {
    const t = definition?.thresholds ?? {};
    return {
      decision_accuracy: t.decision_accuracy != null ? String(Math.round(t.decision_accuracy * 100)) : "",
      redflag_recall: t.redflag_recall != null ? String(Math.round(t.redflag_recall * 100)) : "",
    };
  });
  const [cases, setCases] = useState<CaseDraft[]>(
    definition
      ? definition.cases.map((c) => ({
          source: "paste" as const,
          document_file: c.document_file ?? "",
          docId: "",
          document_text: c.document_text,
          expectedJson: JSON.stringify(c.expected, null, 2),
          valid: null,
        }))
      : [EMPTY_CASE],
  );
  const [busy, setBusy] = useState(false);
  const [loadingDoc, setLoadingDoc] = useState<number | null>(null);

  function updateCase(i: number, patch: Partial<CaseDraft>) {
    setCases((prev) => prev.map((c, idx) => (idx === i ? { ...c, ...patch, valid: null } : c)));
  }

  async function loadDocumentText(i: number, docId: string) {
    setLoadingDoc(i);
    try {
      const res = await fetch(`/api/documents/${docId}/text`);
      if (!res.ok) throw new Error("Falha ao ler o documento");
      const body = (await res.json()) as { filename: string; text: string };
      updateCase(i, {
        source: "document",
        document_file: body.filename,
        docId,
        document_text: body.text,
      });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao carregar documento");
    } finally {
      setLoadingDoc(null);
    }
  }

  async function fillFromExtraction(i: number) {
    const docId = cases[i].docId;
    if (!docId) {
      toast.error("Selecione um documento primeiro");
      return;
    }
    setLoadingDoc(i);
    try {
      const res = await fetch(`/api/extractions/document/${docId}`);
      if (!res.ok) throw new Error("Documento sem extração concluída");
      const body = (await res.json()) as { data?: Record<string, unknown> | null };
      if (!body.data) {
        toast.error("Documento sem extração concluída");
        return;
      }
      updateCase(i, { expectedJson: JSON.stringify(body.data, null, 2) });
      toast.success("Expected preenchido a partir da extração");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao carregar extração");
    } finally {
      setLoadingDoc(null);
    }
  }

  async function validateCase(i: number) {
    let expected: Record<string, unknown>;
    try {
      expected = JSON.parse(cases[i].expectedJson);
    } catch {
      updateCase(i, { valid: false });
      toast.error(`Caso ${i + 1}: JSON inválido`);
      return;
    }
    const res = await fetch("/api/evals/definitions/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schema_name: schemaName, expected }),
    });
    const body = (await res.json()) as EvalValidateResult;
    updateCase(i, { valid: body.valid });
    if (!body.valid && body.errors.length) {
      toast.error(`Caso ${i + 1}: ${body.errors[0]}`);
    }
  }

  async function submit() {
    setBusy(true);
    try {
      const payloadCases: EvalCase[] = [];
      for (let i = 0; i < cases.length; i++) {
        const c = cases[i];
        if (!c.document_text.trim()) {
          toast.error(`Caso ${i + 1}: documento/texto vazio`);
          return;
        }
        let expected: Record<string, unknown>;
        try {
          expected = JSON.parse(c.expectedJson);
        } catch {
          toast.error(`Caso ${i + 1}: JSON do expected inválido`);
          return;
        }
        payloadCases.push({
          document_file: c.document_file || null,
          document_text: c.document_text,
          expected,
        });
      }
      const thr: Record<string, number> = {};
      const dAcc = parseFloat(thresholds.decision_accuracy);
      const rRec = parseFloat(thresholds.redflag_recall);
      if (!Number.isNaN(dAcc)) thr.decision_accuracy = Math.min(100, Math.max(0, dAcc)) / 100;
      if (!Number.isNaN(rRec)) thr.redflag_recall = Math.min(100, Math.max(0, rRec)) / 100;
      const payload = {
        ...(definition ? {} : { slug }),
        title: title.trim() || slug || title,
        description: description.trim() || null,
        schema_name: schemaName,
        cases: payloadCases,
        thresholds: Object.keys(thr).length ? thr : null,
      };
      await onSave(payload);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  const editing = definition !== null;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? `Editar ${definition.title}` : "Nova definição de eval"}</DialogTitle>
          <DialogDescription>
            Golden set com casos (texto + expected) que o pipeline de extração roda para medir regressões.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="def-title">Título</Label>
            <Input id="def-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Credit report — varejo" />
          </div>
          {!editing && (
            <div className="space-y-2">
              <Label htmlFor="def-slug">Slug (único, a-z0-9-)</Label>
              <Input id="def-slug" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="credit-report-varejo" />
            </div>
          )}
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="def-desc">Descrição</Label>
            <Input id="def-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Opcional" />
          </div>
          <div className="space-y-2">
            <Label>Schema</Label>
            <Select value={schemaName} onValueChange={setSchemaName}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="credit_report">credit_report</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label>Limiares do gate (vazio = padrão global)</Label>
            <p className="text-xs text-muted-foreground">
              Padrão: acerto de decisão ≥ 90% · recall de red flags ≥ 40%. Cada execução marca
              &quot;Passou/Falhou&quot; no painel e no dashboard.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Acerto de decisão (%)</Label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  step={5}
                  placeholder="90"
                  value={thresholds.decision_accuracy}
                  onChange={(e) => setThresholds((p) => ({ ...p, decision_accuracy: e.target.value }))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Recall de red flags (%)</Label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  step={5}
                  placeholder="40"
                  value={thresholds.redflag_recall}
                  onChange={(e) => setThresholds((p) => ({ ...p, redflag_recall: e.target.value }))}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Casos ({cases.length})</p>
            <Button variant="outline" size="sm" onClick={() => setCases((prev) => [...prev, { ...EMPTY_CASE }])}>
              <Plus className="mr-1 h-4 w-4" />
              Adicionar caso
            </Button>
          </div>

          {cases.map((c, i) => (
            <div key={i} className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-muted-foreground">Caso {i + 1}</p>
                {cases.length > 1 && (
                  <Button variant="ghost" size="icon-sm" onClick={() => setCases((prev) => prev.filter((_, idx) => idx !== i))}>
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={c.source}
                  onValueChange={(v: "paste" | "document") => updateCase(i, { source: v })}
                >
                  <SelectTrigger className="w-44">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="paste">Colar texto</SelectItem>
                    <SelectItem value="document">Usar documento enviado</SelectItem>
                  </SelectContent>
                </Select>
                {c.source === "document" && (
                  <div className="flex flex-wrap items-center gap-2">
                    <Select value="" onValueChange={(v) => v && loadDocumentText(i, v)}>
                      <SelectTrigger className="w-64">
                        <SelectValue placeholder="Escolher documento…" />
                      </SelectTrigger>
                      <SelectContent>
                        {documents.map((d) => (
                          <SelectItem key={d.id} value={d.id}>
                            {d.title}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {loadingDoc === i && <Loader2 className="h-4 w-4 animate-spin" />}
                    {c.docId && (
                      <Button variant="outline" size="sm" onClick={() => fillFromExtraction(i)} disabled={loadingDoc === i}>
                        Usar extração atual como esperado
                      </Button>
                    )}
                  </div>
                )}
              </div>

              <Textarea
                value={c.document_text}
                onChange={(e) => updateCase(i, { document_text: e.target.value })}
                placeholder="Texto do documento (snapshot do caso)…"
                rows={4}
                className="font-mono text-xs"
              />

              <div className="flex items-start gap-2">
                <Textarea
                  value={c.expectedJson}
                  onChange={(e) => updateCase(i, { expectedJson: e.target.value })}
                  placeholder='{"company_name": "...", "overall_risk_score": 0, ...}'
                  rows={4}
                  className="flex-1 font-mono text-xs"
                />
                <Button variant="outline" size="sm" onClick={() => validateCase(i)}>
                  Validar
                </Button>
              </div>
              {c.valid !== null && (
                <p className={cn("text-xs", c.valid ? "text-emerald-600" : "text-destructive")}>
                  {c.valid ? "Expected válido contra o schema" : "Expected inválido contra o schema"}
                </p>
              )}
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={busy}>
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {editing ? "Salvar alterações" : "Criar definição"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Per-case diff (expected vs actual)
// ---------------------------------------------------------------------------

function CaseRow({ item, expected }: { item: EvalItem; expected?: EvalCase }) {
  const [open, setOpen] = useState(false);
  const m = item.metrics;
  // snapshot stored at run time wins; otherwise fall back to the current definition
  const expectedObj = item.expected ?? expected?.expected ?? {};
  return (
    <div className="rounded-md border px-3 py-2">
      <button type="button" className="flex w-full items-center justify-between text-left" onClick={() => setOpen((o) => !o)}>
        <p className="text-sm font-medium">
          {String(item.case)}
          {expected?.document_file && expected.document_file !== item.case && (
            <span className="ml-2 text-xs text-muted-foreground">(snapshot: {expected.document_file})</span>
          )}
        </p>
        <div className="flex items-center gap-2">
          <Badge variant={item.status === "completed" ? "default" : "destructive"}>{String(item.status)}</Badge>
        </div>
      </button>

      {m && (
        <p className="mt-1 text-xs text-muted-foreground">
          decisão: {String(m.decision_match)} · fuzzy: {(m.fuzzy ?? 0).toFixed(2)} · recall red flags:{" "}
          {(m.redflag_recall ?? 0).toFixed(2)}
          {typeof m.score_mae === "number" && ` · |Δscore|: ${m.score_mae}`}
        </p>
      )}
      {item.error && <p className="mt-1 text-xs text-destructive">{String(item.error)}</p>}

      {open && (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Esperado</p>
            <pre className="max-h-64 overflow-auto rounded-md bg-muted/60 p-2 text-xs">
              {JSON.stringify(expectedObj, null, 2)}
            </pre>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Real (modelo)</p>
            <pre className="max-h-64 overflow-auto rounded-md bg-muted/60 p-2 text-xs">
              {JSON.stringify(item.actual ?? {}, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Studio
// ---------------------------------------------------------------------------

export function EvalStudio() {
  const [tab, setTab] = useState<"definitions" | "runs">("definitions");
  const [definitions, setDefinitions] = useState<EvalDefinition[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvalRun | null>(null);
  const [runDefinition, setRunDefinition] = useState<EvalDefinitionDetail | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [runTarget, setRunTarget] = useState<EvalDefinition | null>(null);
  const [editTarget, setEditTarget] = useState<EvalDefinitionDetail | null | "new">(null);

  const load = useCallback(async () => {
    const [defRes, runRes, docRes] = await Promise.all([
      fetch("/api/evals/definitions"),
      fetch("/api/evals/runs"),
      fetch("/api/documents"),
    ]);
    if (defRes.ok) setDefinitions((await defRes.json()) as EvalDefinition[]);
    if (runRes.ok) {
      const list = (await runRes.json()) as EvalRun[];
      setRuns(list);
      // keep the selected run in sync so metrics/status refresh on poll
      setSelectedRun((prev) => (prev ? list.find((r) => r.id === prev.id) ?? prev : prev));
    }
    if (docRes.ok) setDocuments((await docRes.json()) as DocumentItem[]);
    setLoading(false);
  }, []);

  useEffect(() => {
    // initial data load + polling — setState happens after an await
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    if (!selectedRun?.definition_id) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRunDefinition(null);
      return;
    }
    let active = true;
    fetch(`/api/evals/definitions/${selectedRun.definition_id}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: EvalDefinitionDetail | null) => {
        if (active) setRunDefinition(d);
      })
      .catch(() => {
        /* expected snapshot unavailable */
      });
    return () => {
      active = false;
    };
  }, [selectedRun?.definition_id, selectedRun?.id]);

  async function startRun(def: EvalDefinition, models: Array<{ provider: string; model: string }>) {
    if (models.length === 0) return;
    if (models.length === 1) {
      const { provider, model } = models[0];
      const res = await fetch("/api/evals/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ definition_id: def.id, provider, model }),
      });
      const body = await res.json();
      if (!res.ok) {
        toast.error(body.detail ?? "Falha ao iniciar o eval");
        throw new Error("run_failed");
      }
      setSelectedRun(body as EvalRun);
      toast.success("Eval enfileirado");
    } else {
      const res = await fetch("/api/evals/runs/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ definition_id: def.id, models }),
      });
      const body = await res.json();
      if (!res.ok) {
        toast.error(body.detail ?? "Falha ao iniciar os evals");
        throw new Error("batch_failed");
      }
      const runs = body as EvalRun[];
      if (runs.length) setSelectedRun(runs[0]);
      toast.success(`${runs.length} evals enfileirados (A/B)`);
    }
    setTab("runs");
    setTimeout(load, 400);
  }

  async function saveDefinition(payload: {
    slug?: string;
    title: string;
    description: string | null;
    schema_name: string;
    cases: EvalCase[];
  }) {
    if (editTarget === "new") {
      const res = await fetch("/api/evals/definitions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) {
        toast.error(body.detail ?? "Falha ao criar definição");
        throw new Error("create_failed");
      }
      toast.success("Definição criada");
    } else if (editTarget) {
      const res = await fetch(`/api/evals/definitions/${editTarget.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) {
        toast.error(body.detail ?? "Falha ao salvar definição");
        throw new Error("update_failed");
      }
      toast.success("Definição salva");
    }
    await load();
  }

  async function deleteDefinition(def: EvalDefinition) {
    if (!window.confirm(`Excluir "${def.title}"? Os runs anteriores são preservados.`)) return;
    const res = await fetch(`/api/evals/definitions/${def.id}`, { method: "DELETE" });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      toast.error(body?.detail ?? "Falha ao excluir (pode haver execução em andamento)");
      return;
    }
    toast.success("Definição excluída");
    await load();
  }

  const metrics = selectedRun?.metrics ?? {};
  const items = (selectedRun?.items ?? []) as EvalItem[];
  // runs of the same definition with real metrics (drives the A/B comparison)
  const comparableRuns = selectedRun?.definition_id
    ? runs.filter(
        (r) => r.definition_id === selectedRun.definition_id && r.metrics?.decision_accuracy != null,
      )
    : [];
  const showComparison = comparableRuns.length >= 2;

  return (
    <div className="space-y-6">
      <Tabs value={tab} onValueChange={(v) => setTab(v as "definitions" | "runs")}>
        <div className="flex items-center justify-between gap-4">
          <TabsList>
            <TabsTrigger value="definitions">Definições ({definitions.length})</TabsTrigger>
            <TabsTrigger value="runs">Execuções ({runs.length})</TabsTrigger>
          </TabsList>
          <Button onClick={() => setEditTarget("new")}>
            <Plus className="mr-2 h-4 w-4" />
            Nova definição
          </Button>
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground">Carregando…</p>
        ) : (
          <>
            <TabsContent value="definitions" className="space-y-4">
              {definitions.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Nenhuma definição. Crie uma ou rode o seed (risklens-seed --with-evals).
                </p>
              )}
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {definitions.map((d) => (
                  <Card key={d.id}>
                    <CardHeader>
                      <CardTitle className="text-sm">{d.title}</CardTitle>
                      <p className="text-xs text-muted-foreground">
                        {d.slug} · schema {d.schema_name} · {d.n_cases} casos
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {d.description && <p className="text-xs text-muted-foreground">{d.description}</p>}
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" onClick={() => setRunTarget(d)}>
                          <Play className="mr-1 h-3.5 w-3.5" />
                          Rodar
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            fetch(`/api/evals/definitions/${d.id}`)
                              .then((r) => (r.ok ? r.json() : null))
                              .then((detail) => setEditTarget(detail as EvalDefinitionDetail))
                          }
                        >
                          <Pencil className="mr-1 h-3.5 w-3.5" />
                          Editar
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => deleteDefinition(d)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="runs">
              <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
                <Card className="h-fit">
                  <CardHeader>
                    <CardTitle className="text-sm">Execuções</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {runs.map((r) => (
                      <button
                        key={r.id}
                        onClick={() => setSelectedRun(r)}
                        className={cn(
                          "w-full rounded-md border px-3 py-2 text-left hover:bg-accent",
                          selectedRun?.id === r.id && "bg-accent",
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
                              r.status === "completed"
                                ? "bg-emerald-500"
                                : r.status === "failed"
                                  ? "bg-red-500"
                                  : "bg-blue-500",
                            )}
                          />
                          {r.status} · {new Date(r.created_at).toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo" })}
                        </p>
                        {r.model_used && <p className="mt-0.5 text-xs text-muted-foreground">modelo: {r.model_used}</p>}
                      </button>
                    ))}
                    {runs.length === 0 && <p className="text-sm text-muted-foreground">Nenhuma execução ainda.</p>}
                  </CardContent>
                </Card>

                <div className="space-y-4">
                  {showComparison && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Comparação (A/B) — {comparableRuns.length} execuções</CardTitle>
                      </CardHeader>
                      <CardContent className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-xs text-muted-foreground">
                              <th className="py-1 pr-3">Modelo</th>
                              <th className="py-1 pr-3">Status</th>
                              <th className="py-1 pr-3">Decisão</th>
                              <th className="py-1 pr-3">Recall</th>
                              <th className="py-1 pr-3">Fuzzy</th>
                              <th className="py-1 pr-3">Judge</th>
                              <th className="py-1">Gate</th>
                            </tr>
                          </thead>
                          <tbody>
                            {comparableRuns.map((r) => (
                              <tr
                                key={r.id}
                                className="border-t cursor-pointer hover:bg-accent"
                                onClick={() => setSelectedRun(r)}
                              >
                                <td className="py-1.5 pr-3 font-mono text-xs">{r.model_used}</td>
                                <td className="py-1.5 pr-3 text-xs">{r.status}</td>
                                <td className="py-1.5 pr-3">{pct(r.metrics?.decision_accuracy)}</td>
                                <td className="py-1.5 pr-3">{pct(r.metrics?.redflag_recall)}</td>
                                <td className="py-1.5 pr-3">{pct(r.metrics?.field_fuzzy_similarity)}</td>
                                <td className="py-1.5 pr-3">{String(r.metrics?.llm_judge_score ?? "—")}</td>
                                <td className="py-1.5">
                                  {r.metrics?.passed === true ? (
                                    <span className="font-medium text-emerald-600">Passou</span>
                                  ) : r.metrics?.passed === false ? (
                                    <span className="font-medium text-destructive">Falhou</span>
                                  ) : (
                                    "—"
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </CardContent>
                    </Card>
                  )}

                  {selectedRun ? (
                    <>
                      <Card>
                        <CardHeader>
                          <div className="flex items-center justify-between gap-2">
                            <CardTitle className="text-sm">{selectedRun.name}</CardTitle>
                            {typeof selectedRun.metrics?.passed === "boolean" && (
                              <Badge variant={selectedRun.metrics.passed ? "default" : "destructive"}>
                                {selectedRun.metrics.passed ? "Passou (gate)" : "Abaixo do limiar"}
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground">modelo: {selectedRun.model_used}</p>
                        </CardHeader>
                        <CardContent>
                          {Object.keys(metrics).length === 0 ? (
                            <p className="text-sm text-muted-foreground">
                              {selectedRun.status === "failed"
                                ? selectedRun.error_message ?? "Falha na execução"
                                : selectedRun.status === "running"
                                  ? "Aguardando resultado…"
                                  : "Sem métricas ainda."}
                            </p>
                          ) : (
                            <>
                              {selectedRun.status === "failed" && selectedRun.error_message && (
                                <p className="mb-3 text-xs text-destructive">{selectedRun.error_message}</p>
                              )}
                              <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                                {Object.entries(metrics)
                                  .filter(([k]) => k in METRIC_LABELS)
                                  .map(([k, v]) => (
                                    <Metric key={k} label={METRIC_LABELS[k]} value={v} />
                                  ))}
                              </div>
                            </>
                          )}
                        </CardContent>
                      </Card>

                      {items.length > 0 && (
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-sm">Por caso</CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-2">
                            {items.map((it) => {
                              const expected =
                                typeof it.index === "number" ? runDefinition?.cases[it.index] : undefined;
                              return <CaseRow key={String(it.case)} item={it} expected={expected} />;
                            })}
                            <div className="flex items-center gap-2 pt-1">
                              <RotateCcw className="h-3.5 w-3.5 text-muted-foreground" />
                              <span className="text-xs text-muted-foreground">
                                Clique em um caso para comparar esperado × real.
                              </span>
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </>
                  ) : (
                    <Card>
                      <CardContent className="py-16 text-center text-sm text-muted-foreground">
                        Selecione uma execução ou rode um eval na aba Definições.
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>
            </TabsContent>
          </>
        )}
      </Tabs>

      {runTarget && (
        <RunDialog definition={runTarget} onClose={() => setRunTarget(null)} onRun={(m) => startRun(runTarget, m)} />
      )}
      {editTarget !== null && (
        <DefinitionFormDialog
          definition={editTarget === "new" ? null : editTarget}
          documents={documents}
          onClose={() => setEditTarget(null)}
          onSave={saveDefinition}
        />
      )}
    </div>
  );
}