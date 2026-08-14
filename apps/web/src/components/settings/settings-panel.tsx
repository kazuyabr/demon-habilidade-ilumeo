"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { ProviderRegistryEntry, SettingsConfig, SettingsOut, TestResult } from "@/lib/types";

const EMPTY: SettingsConfig = {
  chat_provider: "",
  chat_model: "",
  embedding_provider: "",
  embedding_model: "",
  temperature: 0.1,
  max_tokens: 2048,
  chunk_size: 1200,
  top_k: 6,
  rag_hybrid: true,
  ff_agent_review_enabled: true,
  ff_eval_llm_judge: true,
};

function FieldRow({
  label,
  custom,
  children,
}: {
  label: string;
  custom?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Label>{label}</Label>
        {custom && <Badge variant="outline">customizado</Badge>}
      </div>
      {children}
    </div>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        checked ? "bg-primary" : "bg-input",
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-background transition-transform",
          checked ? "translate-x-6" : "translate-x-1",
        )}
      />
    </button>
  );
}

export function SettingsPanel() {
  const [draft, setDraft] = useState<SettingsConfig>(EMPTY);
  const [overridden, setOverridden] = useState<string[]>([]);
  const [providers, setProviders] = useState<ProviderRegistryEntry[]>([]);
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    const [sRes, pRes] = await Promise.all([
      fetch("/api/admin/settings"),
      fetch("/api/admin/providers"),
    ]);
    if (sRes.ok) {
      const s = (await sRes.json()) as SettingsOut;
      setDraft({ ...EMPTY, ...s.config });
      setOverridden(s.overridden ?? []);
    }
    if (pRes.ok) {
      const p = (await pRes.json()) as { providers: ProviderRegistryEntry[] };
      setProviders(p.providers ?? []);
    }
    setLoaded(true);
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const chatProviders = useMemo(() => providers.filter((p) => p.chat), [providers]);
  const embedProviders = useMemo(() => providers.filter((p) => p.embeddings), [providers]);

  const set = <K extends keyof SettingsConfig>(key: K, value: SettingsConfig[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setDirty((prev) => new Set(prev).add(key as string));
  };

  const chatModels = chatProviders.find((p) => p.id === draft.chat_provider)?.chat_models ?? [];
  const embedModels = embedProviders.find((p) => p.id === draft.embedding_provider)?.embedding_models ?? [];

  async function save() {
    if (dirty.size === 0) return;
    setSaving(true);
    const payload: Record<string, unknown> = {};
    dirty.forEach((k) => {
      payload[k] = (draft as unknown as Record<string, unknown>)[k];
    });
    const res = await fetch("/api/admin/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok) {
      toast.error(body.detail ?? "Falha ao salvar");
      setSaving(false);
      return;
    }
    setOverridden(body.overridden ?? []);
    setDirty(new Set());
    toast.success("Configuração salva e aplicada");
    setSaving(false);
  }

  async function testConnection() {
    setTesting(true);
    setTestResult(null);
    const res = await fetch("/api/admin/settings/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: draft.chat_provider, model: draft.chat_model }),
    });
    const body = (await res.json()) as TestResult;
    setTestResult(body);
    setTesting(false);
  }

  if (!loaded) {
    return <p className="text-sm text-muted-foreground">Carregando configurações…</p>;
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Modelos de IA</CardTitle>
          <CardDescription>
            Chat e embeddings podem usar providers diferentes. Chaves continuam no ambiente
            (env/Secret Manager) — aqui só se escolhe e testa.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FieldRow label="Provider de chat" custom={overridden.includes("chat_provider")}>
            <Select
              value={draft.chat_provider}
              onValueChange={(v) => {
                set("chat_provider", v);
                const first = chatProviders.find((p) => p.id === v)?.chat_models[0]?.id;
                if (first) set("chat_model", first);
              }}
            >
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                {chatProviders.map((p) => (
                  <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FieldRow>

          <FieldRow label="Modelo de chat" custom={overridden.includes("chat_model")}>
            <Select value={draft.chat_model} onValueChange={(v) => set("chat_model", v)}>
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                {chatModels.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.label} {m.free ? "(free)" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FieldRow>

          <FieldRow label="Provider de embeddings" custom={overridden.includes("embedding_provider")}>
            <Select
              value={draft.embedding_provider}
              onValueChange={(v) => {
                set("embedding_provider", v);
                const first = embedProviders.find((p) => p.id === v)?.embedding_models[0]?.id;
                if (first) set("embedding_model", first);
              }}
            >
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                {embedProviders.map((p) => (
                  <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FieldRow>

          <FieldRow label="Modelo de embeddings" custom={overridden.includes("embedding_model")}>
            <Select value={draft.embedding_model} onValueChange={(v) => set("embedding_model", v)}>
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                {embedModels.map((m) => (
                  <SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FieldRow>

          <div className="grid grid-cols-2 gap-4">
            <FieldRow label="Temperatura" custom={overridden.includes("temperature")}>
              <Input
                type="number"
                step={0.1}
                min={0}
                max={2}
                value={draft.temperature}
                onChange={(e) => set("temperature", parseFloat(e.target.value) || 0)}
              />
            </FieldRow>
            <FieldRow label="Máx. tokens" custom={overridden.includes("max_tokens")}>
              <Input
                type="number"
                step={128}
                min={64}
                value={draft.max_tokens}
                onChange={(e) => set("max_tokens", parseInt(e.target.value, 10) || 0)}
              />
            </FieldRow>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Pipeline RAG</CardTitle>
            <CardDescription>Chunking, recuperação e busca híbrida.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FieldRow label="Chunk size (caracteres)" custom={overridden.includes("chunk_size")}>
                <Input
                  type="number"
                  step={100}
                  min={200}
                  value={draft.chunk_size}
                  onChange={(e) => set("chunk_size", parseInt(e.target.value, 10) || 0)}
                />
              </FieldRow>
              <FieldRow label="Top-K" custom={overridden.includes("top_k")}>
                <Input
                  type="number"
                  step={1}
                  min={1}
                  value={draft.top_k}
                  onChange={(e) => set("top_k", parseInt(e.target.value, 10) || 0)}
                />
              </FieldRow>
            </div>
            <FieldRow label="Busca híbrida (vetorial + full-text)" custom={overridden.includes("rag_hybrid")}>
              <Toggle checked={draft.rag_hybrid} onChange={(v) => set("rag_hybrid", v)} />
            </FieldRow>
            <FieldRow
              label="Revisão sênior no agente"
              custom={overridden.includes("ff_agent_review_enabled")}
            >
              <Toggle
                checked={draft.ff_agent_review_enabled}
                onChange={(v) => set("ff_agent_review_enabled", v)}
              />
            </FieldRow>
            <FieldRow label="LLM-as-judge nos evals" custom={overridden.includes("ff_eval_llm_judge")}>
              <Toggle
                checked={draft.ff_eval_llm_judge}
                onChange={(v) => set("ff_eval_llm_judge", v)}
              />
            </FieldRow>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Testar conexão</CardTitle>
            <CardDescription>
              Testa o provider de chat selecionado acima (sem salvar).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button variant="outline" onClick={testConnection} disabled={testing || !draft.chat_provider}>
              {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
              Testar {draft.chat_provider || "chat"}
            </Button>
            {testResult && (
              <div
                className={cn(
                  "rounded-md border px-3 py-2 text-sm",
                  testResult.ok ? "border-emerald-300 dark:border-emerald-900" : "border-red-300 dark:border-red-900",
                )}
              >
                <p className="font-medium">
                  {testResult.ok ? "Conectado" : "Falha"} · {testResult.latency_ms}ms
                </p>
                {testResult.reply && <p className="text-muted-foreground">resposta: {testResult.reply}</p>}
                {testResult.error && <p className="text-destructive break-words">{testResult.error}</p>}
              </div>
            )}
          </CardContent>
        </Card>

        <Button className="w-full" onClick={save} disabled={saving || dirty.size === 0}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Salvar e aplicar ({dirty.size})
        </Button>
      </div>
    </div>
  );
}
