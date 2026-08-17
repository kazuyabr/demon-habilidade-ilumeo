"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
  decision_accuracy: "Acerto de decisÃ£o",
  field_exact_accuracy: "Acerto exato de campos",
  field_fuzzy_similarity: "Similaridade fuzzy",
  redflag_recall: "Recall de red flags",
  score_mae: "Erro mÃ©dio de score",
  llm_judge_score: "Nota LLM judge (0â€“5)",
  n_cases: "Casos",
};

function Metric({ label, value }: { label: string; value: unknown }) {
  let display = String(value ?? "â€”");
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
              label: `${p.label} Â· ${m.label}${m.free ? " (free)" : ""}`,
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
        /* providers unavailable â€” run will fall back to the active model */
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
  onRun: (provider: string | null, model: string | null) => Promise<void>;
}) {
  const { options, defaultValue } = useModelOptions();
  const [value, setValue] = useState<string>(defaultValue);
  const [busy, setBusy] = useState(false);

  const activeValue = useMemo(
    () => value || defaultValue,
    [value, defaultValue],
  );

  async function submit() {
    setBusy(true);
    const [provider, model] = activeValue ? activeValue.split("::") : [null, null];
    try {
      await onRun(provider, model);
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
            {definition.n_cases} casos Â· schema {definition.schema_name}. Escolha o modelo (default = ativo).
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="run-model">Provider / modelo</Label>
          {options.length === 0 ? (
            <p className="text-xs text-muted-foreground">Usando o modelo ativo (sem seletor disponÃ­vel)â€¦</p>
          ) : (
            <Select value={activeValue} onValueChange={setValue}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Selecione o modelo" />
              </SelectTrigger>
              <SelectContent>
                {options.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={busy}>
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Executar
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
  document_text: string;
  expectedJson: string;
  valid?: boolean | null;
};

const EMPTY_CASE: CaseDraft = {
  source: "paste",
  document_file: "",
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
  }) => Promise<void>;
}) {
  const [slug, setSlug] = useState(definition?.slug ?? "");
  const [title, setTitle] = useState(definition?.title ?? "");
  const [description, setDescription] = useState(definition?.description ?? "");
  const [schemaName, setSchemaName] = useState(definition?.schema_name ?? "credit_report");
  const [cases, setCases] = useState<CaseDraft[]>(
    definition
      ? definition.cases.map((c) => ({
          source: "paste" as const,
          document_file: c.document_file ?? "",
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
        document_text: body.text,
      });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao carregar documento");
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
      toast.error(`Caso ${i + 1}: JSON invÃ¡lido`);
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
          toast.error(`Caso ${i + 1}: JSON do expected invÃ¡lido`);
          return;
        }
        payloadCases.push({
          document_file: c.document_file || null,
          document_text: c.document_text,
          expected,
        });
      }
      const payload = {
        ...(definition ? {} : { slug }),
        title: title.trim() || slug || title,
        description: description.trim() || null,
        schema_name: schemaName,
        cases: payloadCases,
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
          <DialogTitle>{editing ? `Editar ${definition.title}` : "Nova definiÃ§Ã£o de eval"}</DialogTitle>
          <DialogDescription>
            Golden set com casos (texto + expected) que o pipeline de extraÃ§Ã£o roda para medir regressÃµes.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="def-title">TÃ­tulo</Label>
            <Input id="def-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Credit report â€” varejo" />
          </div>
          {!editing && (
            <div className="space-y-2">
              <Label htmlFor="def-slug">Slug (Ãºnico, a-z0-9-)</Label>
              <Input id="def-slug" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="credit-report-varejo" />
            </div>
          )}
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="def-desc">DescriÃ§Ã£o</Label>
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
                  <div className="flex items-center gap-2">
                    <Select value="" onValueChange={(v) => v && loadDocumentText(i, v)}>
                      <SelectTrigger className="w-64">
                        <SelectValue placeholder="Escolher documentoâ€¦" />
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
                  </div>
                )}
              </div>

              <Textarea
                value={c.document_text}
                onChange={(e) => updateCase(i, { document_text: e.target.value })}
                placeholder="Texto do documento (snapshot do caso)â€¦"
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
                  {c.valid ? "Expected vÃ¡lido contra o schema" : "Expected invÃ¡lido contra o schema"}
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
            {editing ? "Salvar alteraÃ§Ãµes" : "Criar definiÃ§Ã£o"}
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
          decisÃ£o: {String(m.decision_match)} Â· fuzzy: {(m.fuzzy ?? 0).toFixed(2)} Â· recall red flags:{" "}
          {(m.redflag_recall ?? 0).toFixed(2)}
          {typeof m.score_mae === "number" && ` Â· |Î”score|: ${m.score_mae}`}
        </p>
      )}
      {item.error && <p className="mt-1 text-xs text-destructive">{String(item.error)}</p>}

      {open && (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Esperado</p>
            <pre className="max-h-64 overflow-auto rounded-md bg-muted/60 p-2 text-xs">
              {JSON.stringify(expected?.expected ?? {}, null, 2)}
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
  const [running, setRunning] = useState(false);
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
      setRunning(list.some((r) => r.status === "running"));
    }
    if (docRes.ok) setDocuments((await docRes.json()) as DocumentItem[]);
    setLoading(false);
  }, []);

  useEffect(() => {
    // initial data load + polling â€” setState happens after an await
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

  async function startRun(def: EvalDefinition, provider: string | null, model: string | null) {
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
    setTab("runs");
    toast.success("Eval enfileirado");
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
        toast.error(body.detail ?? "Falha ao criar definiÃ§Ã£o");
        throw new Error("create_failed");
      }
      toast.success("DefiniÃ§Ã£o criada");
    } else if (editTarget) {
      const res = await fetch(`/api/evals/definitions/${editTarget.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) {
        toast.error(body.detail ?? "Falha ao salvar definiÃ§Ã£o");
        throw new Error("update_failed");
      }
      toast.success("DefiniÃ§Ã£o salva");
    }
    await load();
  }

  async function deleteDefinition(def: EvalDefinition) {
    if (!window.confirm(`Excluir "${def.title}"? Os runs anteriores sÃ£o preservados.`)) return;
    const res = await fetch(`/api/evals/definitions/${def.id}`, { method: "DELETE" });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      toast.error(body?.detail ?? "Falha ao excluir (pode haver execuÃ§Ã£o em andamento)");
      return;
    }
    toast.success("DefiniÃ§Ã£o excluÃ­da");
    await load();
  }

  const metrics = selectedRun?.metrics ?? {};
  const items = (selectedRun?.items ?? []) as EvalItem[];

  return (
    <div className="space-y-6">
      <Tabs value={tab} onValueChange={(v) => setTab(v as "definitions" | "runs")}>
        <div className="flex items-center justify-between gap-4">
          <TabsList>
            <TabsTrigger value="definitions">DefiniÃ§Ãµes ({definitions.length})</TabsTrigger>
            <TabsTrigger value="runs">ExecuÃ§Ãµes ({runs.length})</TabsTrigger>
          </TabsList>
          <Button onClick={() => setEditTarget("new")}>
            <Plus className="mr-2 h-4 w-4" />
            Nova definiÃ§Ã£o
          </Button>
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground">Carregandoâ€¦</p>
        ) : (
          <>
            <TabsContent value="definitions" className="space-y-4">
              {definitions.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Nenhuma definiÃ§Ã£o. Crie uma ou rode o seed (risklens-seed --with-evals).
                </p>
              )}
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {definitions.map((d) => (
                  <Card key={d.id}>
                    <CardHeader>
                      <CardTitle className="text-sm">{d.title}</CardTitle>
                      <p className="text-xs text-muted-foreground">
                        {d.slug} Â· schema {d.schema_name} Â· {d.n_cases} casos
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
                    <CardTitle className="text-sm">ExecuÃ§Ãµes</CardTitle>
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
                          {r.status} Â· {new Date(r.created_at).toLocaleTimeString("pt-BR")}
                        </p>
                        {r.model_used && <p className="mt-0.5 text-xs text-muted-foreground">modelo: {r.model_used}</p>}
                      </button>
                    ))}
                    {runs.length === 0 && <p className="text-sm text-muted-foreground">Nenhuma execuÃ§Ã£o ainda.</p>}
                  </CardContent>
                </Card>

                <div className="space-y-4">
                  {selectedRun ? (
                    <>
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-sm">{selectedRun.name}</CardTitle>
                          <p className="text-xs text-muted-foreground">modelo: {selectedRun.model_used}</p>
                        </CardHeader>
                        <CardContent>
                          {Object.keys(metrics).length === 0 ? (
                            <p className="text-sm text-muted-foreground">
                              {running ? "Aguardando resultadoâ€¦" : "Sem mÃ©tricas ainda."}
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
                                Clique em um caso para comparar esperado Ã— real.
                              </span>
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </>
                  ) : (
                    <Card>
                      <CardContent className="py-16 text-center text-sm text-muted-foreground">
                        Selecione uma execuÃ§Ã£o ou rode um eval na aba DefiniÃ§Ãµes.
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
        <RunDialog definition={runTarget} onClose={() => setRunTarget(null)} onRun={(p, m) => startRun(runTarget, p, m)} />
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