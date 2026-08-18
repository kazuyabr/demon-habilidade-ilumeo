"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  ChevronDown,
  ChevronRight,
  Dices,
  Info,
  KeyRound,
  Loader2,
  Save,
  Trash2,
  Zap,
} from "lucide-react";

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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type {
  CredentialSummary,
  ProviderRegistryEntry,
  SettingsConfig,
  SettingsOut,
  TestResult,
} from "@/lib/types";

const EMPTY: SettingsConfig = {
  chat_provider: "",
  chat_model: "",
  embedding_provider: "",
  embedding_model: "",
  temperature: 0.1,
  max_tokens: 2048,
  top_p: 1,
  sampling_top_k: null,
  min_p: null,
  frequency_penalty: 0,
  presence_penalty: 0,
  seed: null,
  chunk_size: 1200,
  top_k: 6,
  agent_max_chars_per_chunk: 1200,
  agent_max_evidence_chars: 8000,
  rag_hybrid: true,
  ff_agent_review_enabled: true,
  ff_eval_llm_judge: true,
};

// Optional numeric knobs: empty input = null (provider default / random).
const numOrNull = (v: string): number | null => (v.trim() === "" ? null : parseInt(v, 10) || null);
const floatOrNull = (v: string): number | null => (v.trim() === "" ? null : parseFloat(v) || 0);

function FieldRow({
  label,
  help,
  custom,
  children,
}: {
  label: string;
  help?: string;
  custom?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Label>{label}</Label>
        {help && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                tabIndex={-1}
                aria-label={`Ajuda sobre ${label}`}
                className="text-muted-foreground hover:text-foreground"
              >
                <Info className="h-3.5 w-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top">{help}</TooltipContent>
          </Tooltip>
        )}
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

function protocolBadge(protocol?: string) {
  if (!protocol) return null;
  return <span className="ml-1 text-[10px] text-muted-foreground">· {protocol}</span>;
}

function looksLikePermissionError(error: string): boolean {
  const e = error.toLowerCase();
  return /permission|not allowed|forbidden|disabled|403|china|hosted/i.test(e);
}

// Resolved endpoint for a model, per its API protocol (OpenCode Zen/Go docs).
function endpointOf(
  provider: ProviderRegistryEntry | undefined,
  modelId: string,
  host: string,
): string {
  const base = host || provider?.api || "";
  if (!base) return "(definir host)";
  const proto = provider?.chat_models.find((m) => m.id === modelId)?.protocol ?? "chat";
  if (proto === "responses") return `${base}/responses`;
  if (proto === "messages") return `${base}/messages`;
  if (proto === "google") return `${base}/models/${modelId}:generateContent`;
  return `${base}/chat/completions`;
}

export function SettingsPanel() {
  const [draft, setDraft] = useState<SettingsConfig>(EMPTY);
  const [overridden, setOverridden] = useState<string[]>([]);
  const [providers, setProviders] = useState<ProviderRegistryEntry[]>([]);
  const [creds, setCreds] = useState<Record<string, CredentialSummary>>({});
  const [credDrafts, setCredDrafts] = useState<Record<string, { base_url: string; api_key: string }>>({});
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [savingCred, setSavingCred] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [showSampling, setShowSampling] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    const [sRes, pRes, cRes] = await Promise.all([
      fetch("/api/admin/settings"),
      fetch("/api/admin/providers"),
      fetch("/api/auth/credentials"),
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
    if (cRes.ok) {
      const list = (await cRes.json()) as CredentialSummary[];
      setCreds(Object.fromEntries(list.map((c) => [c.provider, c])));
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

  const chatProviderObj = chatProviders.find((p) => p.id === draft.chat_provider);
  const embedProviderObj = embedProviders.find((p) => p.id === draft.embedding_provider);
  const chatModels = chatProviderObj?.chat_models ?? [];
  const embedModels = embedProviderObj?.embedding_models ?? [];
  const chatIsCustom = draft.chat_provider === "custom";
  const embedIsCustom = draft.embedding_provider === "custom";

  // Effective host for a provider: typed draft > saved (BYOK) > provider default.
  const hostValue = (provider: string, providerObj: ProviderRegistryEntry | undefined): string =>
    credDrafts[provider]?.base_url ?? creds[provider]?.base_url ?? providerObj?.api ?? "";

  const setCredField = (provider: string, field: "base_url" | "api_key", value: string) => {
    setCredDrafts((prev) => ({
      ...prev,
      [provider]: { ...(prev[provider] ?? { base_url: "", api_key: "" }), [field]: value },
    }));
  };

  async function saveCred(provider: string, providerObj?: ProviderRegistryEntry | undefined) {
    setSavingCred(provider);
    const d = credDrafts[provider] ?? { base_url: "", api_key: "" };
    const effective = d.base_url.trim() || creds[provider]?.base_url || "";
    const defaultBase = providerObj?.api ?? "";
    const payload: Record<string, string> = {};
    if (d.api_key.trim()) payload.api_key = d.api_key.trim();
    // only persist a host when it differs from the auto-detected default
    if (effective && effective !== defaultBase) payload.base_url = effective;
    if (Object.keys(payload).length === 0) {
      toast.info("Nada para salvar — host igual ao padrão e sem chave nova");
      setSavingCred(null);
      return;
    }
    const res = await fetch(`/api/auth/credentials/${provider}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json();
      toast.error(body.detail ?? "Falha ao salvar credencial");
      setSavingCred(null);
      return;
    }
    const summary = (await res.json()) as CredentialSummary;
    setCreds((prev) => ({ ...prev, [provider]: summary }));
    setCredDrafts((prev) => ({ ...prev, [provider]: { base_url: "", api_key: "" } }));
    toast.success(`Credencial de ${provider} salva`);
    setSavingCred(null);
  }

  async function deleteCred(provider: string) {
    const res = await fetch(`/api/auth/credentials/${provider}`, { method: "DELETE" });
    if (res.ok) {
      setCreds((prev) => {
        const next = { ...prev };
        delete next[provider];
        return next;
      });
      toast.success(`Credencial de ${provider} removida`);
    } else {
      toast.error("Falha ao remover");
    }
  }

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

  // Renders the BYOK host/api-key fields for a selected provider (plain function,
  // not a component — avoids input remounts).
  const renderCredFields = (provider: string, providerObj: ProviderRegistryEntry | undefined) => {
    const d = credDrafts[provider];
    const c = creds[provider];
    const host = hostValue(provider, providerObj);
    const selectedModel = provider === draft.chat_provider ? chatModels.find((m) => m.id === draft.chat_model) : undefined;
    return (
      <div className="space-y-2 rounded-md border px-3 py-3">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <KeyRound className="h-3.5 w-3.5" />
          Credenciais deste provider (BYOK)
          {c && (
            <Badge variant="outline">
              {c.has_api_key ? `chave ••••${c.api_key_last4}` : ""}
              {c.has_api_key && c.has_base_url ? " · " : ""}
              {c.has_base_url ? "host próprio" : ""}
            </Badge>
          )}
          {!c && <Badge variant="secondary">usa default do env</Badge>}
        </div>
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <div className="space-y-1">
            <Label className="flex items-center gap-1 text-xs">
              Host (auto-preenchido — edite se quiser)
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" tabIndex={-1} aria-label="Ajuda sobre Host" className="text-muted-foreground hover:text-foreground">
                    <Info className="h-3 w-3" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top">
                  Endereço do servidor deste provider. Auto-preenchido; edite para apontar para um
                  servidor ou gateway próprio (BYOK).
                </TooltipContent>
              </Tooltip>
            </Label>
            <Input
              placeholder={providerObj?.api ?? "https://..."}
              value={host}
              onChange={(e) => setCredField(provider, "base_url", e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="flex items-center gap-1 text-xs">
              API key
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" tabIndex={-1} aria-label="Ajuda sobre API key" className="text-muted-foreground hover:text-foreground">
                    <Info className="h-3 w-3" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top">
                  Sua chave deste provider, guardada criptografada (só o final aparece). Sem chave,
                  usa a do ambiente.
                </TooltipContent>
              </Tooltip>
            </Label>
            <Input
              type="password"
              placeholder={c?.has_api_key ? `••••${c.api_key_last4}` : "adicione sua key"}
              value={d?.api_key ?? ""}
              onChange={(e) => setCredField(provider, "api_key", e.target.value)}
            />
          </div>
          <div className="flex items-end gap-1">
            <Button size="sm" onClick={() => saveCred(provider, providerObj)} disabled={savingCred === provider}>
              {savingCred === provider ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Salvar
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => deleteCred(provider)}
              disabled={!c}
              className="text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
        {!c?.has_api_key && (
          <p className="text-[11px] text-muted-foreground">
            Adicione sua API key para testar/configurar este provider — ou deixe para usar a do ambiente.
          </p>
        )}
        {provider === draft.chat_provider && draft.chat_model && selectedModel && (
          <div className="space-y-0.5 rounded-md bg-muted px-3 py-2 font-mono text-[11px]">
            <p>
              <span className="text-muted-foreground">endpoint:</span>{" "}
              {endpointOf(providerObj, draft.chat_model, host)}
            </p>
            <p>
              <span className="text-muted-foreground">ai-sdk:</span> {selectedModel.sdk ?? "—"}{" "}
              <span className="text-muted-foreground">· protocolo:</span> {selectedModel.protocol ?? "chat"}
            </p>
          </div>
        )}
      </div>
    );
  };

  if (!loaded) {
    return <p className="text-sm text-muted-foreground">Carregando configurações…</p>;
  }

  return (
    <TooltipProvider>
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Modelos de IA</CardTitle>
          <CardDescription>
            Chat e embeddings podem usar providers diferentes. Host e chave são por usuário
            (BYOK, criptografado) — sem chave sua, usa o default do ambiente.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FieldRow
            label="Provider de chat"
            help="De onde vêm as respostas (extração, RAG e agente). Pode ser um modelo local (LM Studio), gratuito (OpenCode) ou nuvem (Vertex/OpenAI)."
            custom={overridden.includes("chat_provider")}
          >
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

          <FieldRow
            label="Modelo de chat"
            help="Qual modelo desse provider será usado. Modelos maiores tendem a ser melhores, porém mais lentos e caros."
            custom={overridden.includes("chat_model")}
          >
            {chatIsCustom ? (
              <Input
                placeholder="ex.: meu-modelo-custom"
                value={draft.chat_model}
                onChange={(e) => set("chat_model", e.target.value)}
              />
            ) : (
              <Select value={draft.chat_model} onValueChange={(v) => set("chat_model", v)}>
                <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
                <SelectContent>
                  {chatModels.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.label} {m.free ? "(free)" : ""}
                      {protocolBadge(m.protocol)}
                      {m.china_gated && (
                        <span
                          className="ml-1 rounded bg-amber-100 px-1 text-[10px] text-amber-700 dark:bg-amber-950 dark:text-amber-400"
                          title="Provedor chinês — se o uso falhar por permissão, habilite 'modelos hospedados na China' na sua assinatura GO (opencode.ai/auth)."
                        >
                          liberação China (GO)
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FieldRow>

          {chatProviderObj && renderCredFields(draft.chat_provider, chatProviderObj)}

          <FieldRow
            label="Provider de embeddings"
            help="De onde vêm os vetores da busca (RAG). Pode ser independente do chat — ex.: fastembed local sem chave."
            custom={overridden.includes("embedding_provider")}
          >
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

          <FieldRow
            label="Modelo de embeddings"
            help="Modelo que transforma textos em vetores para a busca semântica. Todos geram 768 dimensões."
            custom={overridden.includes("embedding_model")}
          >
            {embedIsCustom ? (
              <Input
                placeholder="ex.: meu-embedder-custom"
                value={draft.embedding_model}
                onChange={(e) => set("embedding_model", e.target.value)}
              />
            ) : (
              <Select value={draft.embedding_model} onValueChange={(v) => set("embedding_model", v)}>
                <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
                <SelectContent>
                  {embedModels.map((m) => (
                    <SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FieldRow>

          {embedProviderObj && renderCredFields(draft.embedding_provider, embedProviderObj)}

          <div className="grid grid-cols-2 gap-4">
            <FieldRow
              label="Temperatura"
              help="O quanto a IA pode variar nas respostas. Baixo (0–0.3) = estável e consistente; alto = mais criativo. Para análise de risco, prefira baixo."
              custom={overridden.includes("temperature")}
            >
              <Input
                type="number"
                step={0.1}
                min={0}
                max={2}
                value={draft.temperature}
                onChange={(e) => set("temperature", parseFloat(e.target.value) || 0)}
              />
            </FieldRow>
            <FieldRow
              label="Máx. tokens"
              help="Tamanho máximo da resposta (em pedaços de texto). Se a resposta cortar no meio, aumente este valor."
              custom={overridden.includes("max_tokens")}
            >
              <Input
                type="number"
                step={128}
                min={64}
                value={draft.max_tokens}
                onChange={(e) => set("max_tokens", parseInt(e.target.value, 10) || 0)}
              />
            </FieldRow>
          </div>

          <div className="border-t pt-3">
            <button
              type="button"
              onClick={() => setShowSampling((s) => !s)}
              className="flex w-full items-center justify-between text-sm font-medium"
            >
              <span>Amostragem (avançado)</span>
              {showSampling ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
            {showSampling && (
              <div className="mt-3 space-y-3">
                <p className="text-xs text-muted-foreground">
                  Peso de amostragem por request. Alguns só se aplicam a certos providers: Top-K e
                  Min-P são para modelos locais/Anthropic/Vertex; penalidades não se aplicam ao
                  Anthropic; Seed fixo dá resultados determinísticos (útil para evals).
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <FieldRow
                    label="Top-P"
                    help="Amostragem de núcleo: limita a escolha às opções mais prováveis. 1.0 = usa todas; menor = resposta mais focada e previsível."
                    custom={overridden.includes("top_p")}
                  >
                    <Input
                      type="number"
                      step={0.05}
                      min={0}
                      max={1}
                      value={draft.top_p}
                      onChange={(e) => set("top_p", parseFloat(e.target.value) || 0)}
                    />
                  </FieldRow>
                  <FieldRow
                    label="Top-K (amostragem)"
                    help="Considera apenas as K opções mais prováveis a cada passo. Vazio = padrão do modelo. Só se aplica a modelos locais, Anthropic e Vertex."
                    custom={overridden.includes("sampling_top_k")}
                  >
                    <Input
                      type="number"
                      step={1}
                      min={1}
                      placeholder="vazio = padrão"
                      value={draft.sampling_top_k ?? ""}
                      onChange={(e) => set("sampling_top_k", numOrNull(e.target.value))}
                    />
                  </FieldRow>
                  <FieldRow
                    label="Min-P"
                    help="Descarta opções muito menos prováveis que a melhor escolha. Reduz ruído em modelos locais. Vazio = padrão."
                    custom={overridden.includes("min_p")}
                  >
                    <Input
                      type="number"
                      step={0.05}
                      min={0}
                      max={1}
                      placeholder="vazio = padrão"
                      value={draft.min_p ?? ""}
                      onChange={(e) => set("min_p", floatOrNull(e.target.value))}
                    />
                  </FieldRow>
                  <FieldRow
                    label="Penalidade de frequência"
                    help="Penaliza palavras repetidas na resposta. Valores maiores reduzem repetição em textos longos."
                    custom={overridden.includes("frequency_penalty")}
                  >
                    <Input
                      type="number"
                      step={0.1}
                      min={-2}
                      max={2}
                      value={draft.frequency_penalty}
                      onChange={(e) => set("frequency_penalty", parseFloat(e.target.value) || 0)}
                    />
                  </FieldRow>
                  <FieldRow
                    label="Penalidade de presença"
                    help="Penaliza repetir assuntos já usados. Valores maiores incentivam variedade de temas."
                    custom={overridden.includes("presence_penalty")}
                  >
                    <Input
                      type="number"
                      step={0.1}
                      min={-2}
                      max={2}
                      value={draft.presence_penalty}
                      onChange={(e) => set("presence_penalty", parseFloat(e.target.value) || 0)}
                    />
                  </FieldRow>
                  <FieldRow
                    label="Seed"
                    help="Semente da aleatoriedade. Vazio = aleatório (varia a cada vez). Fixar um número = resultados repetíveis — útil para avaliar evals e comparar mudanças."
                    custom={overridden.includes("seed")}
                  >
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        step={1}
                        min={0}
                        placeholder="vazio = aleatório"
                        value={draft.seed ?? ""}
                        onChange={(e) => set("seed", numOrNull(e.target.value))}
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        title="Gerar um seed aleatório e fixar"
                        onClick={() => set("seed", Math.floor(Math.random() * 1_000_000_000))}
                      >
                        <Dices className="h-4 w-4" />
                      </Button>
                    </div>
                  </FieldRow>
                </div>
              </div>
            )}
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
              <FieldRow
                label="Chunk size (caracteres)"
                help="Tamanho de cada trecho em que o documento é dividido para a busca. Menor = busca mais fina; maior = mais contexto por trecho."
                custom={overridden.includes("chunk_size")}
              >
                <Input
                  type="number"
                  step={100}
                  min={200}
                  value={draft.chunk_size}
                  onChange={(e) => set("chunk_size", parseInt(e.target.value, 10) || 0)}
                />
              </FieldRow>
              <FieldRow
                label="Top-K"
                help="Quantos trechos o sistema recupera por consulta. Mais trechos = mais contexto na resposta, porém mais tokens (custo) por pergunta."
                custom={overridden.includes("top_k")}
              >
                <Input
                  type="number"
                  step={1}
                  min={1}
                  value={draft.top_k}
                  onChange={(e) => set("top_k", parseInt(e.target.value, 10) || 0)}
                />
              </FieldRow>
            </div>
            <FieldRow
              label="Busca híbrida (vetorial + full-text)"
              help="Une busca por significado (vetorial — acha sinônimos) e por termos exatos (textual — acha nomes e siglas). Recomendado: ligado; só vetorial pode perder nomes exatos."
              custom={overridden.includes("rag_hybrid")}
            >
              <Toggle checked={draft.rag_hybrid} onChange={(v) => set("rag_hybrid", v)} />
            </FieldRow>
            <FieldRow
              label="Revisão sênior no agente"
              help="O agente faz uma segunda passada 'sênior' antes do relatório final. Torna a análise mais conservadora, porém usa mais chamadas."
              custom={overridden.includes("ff_agent_review_enabled")}
            >
              <Toggle
                checked={draft.ff_agent_review_enabled}
                onChange={(v) => set("ff_agent_review_enabled", v)}
              />
            </FieldRow>
            <FieldRow
              label="LLM-as-judge nos evals"
              help="Um LLM extra dá nota de 0 a 5 à qualidade da extração nos evals (comparando com o esperado). Custa chamadas extras, mas mede a qualidade de forma holística."
              custom={overridden.includes("ff_eval_llm_judge")}
            >
              <Toggle
                checked={draft.ff_eval_llm_judge}
                onChange={(v) => set("ff_eval_llm_judge", v)}
              />
            </FieldRow>
            <div className="border-t pt-3">
              <p className="mb-2 text-sm font-medium">Agente — contexto</p>
              <div className="grid grid-cols-2 gap-4">
                <FieldRow
                  label="Máx. caracteres por trecho"
                  help="Limite de caracteres de cada evidência que o agente envia ao modelo. Menor = respostas mais rápidas e baratas."
                  custom={overridden.includes("agent_max_chars_per_chunk")}
                >
                  <Input
                    type="number"
                    step={100}
                    min={200}
                    value={draft.agent_max_chars_per_chunk}
                    onChange={(e) => set("agent_max_chars_per_chunk", parseInt(e.target.value, 10) || 0)}
                  />
                </FieldRow>
                <FieldRow
                  label="Máx. evidência por passo"
                  help="Limite total de contexto das evidências em cada passo do agente. Protege contra estourar a janela de contexto do modelo."
                  custom={overridden.includes("agent_max_evidence_chars")}
                >
                  <Input
                    type="number"
                    step={500}
                    min={1000}
                    value={draft.agent_max_evidence_chars}
                    onChange={(e) => set("agent_max_evidence_chars", parseInt(e.target.value, 10) || 0)}
                  />
                </FieldRow>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Testar conexão</CardTitle>
            <CardDescription>
              Testa o provider de chat selecionado acima, usando suas credenciais (BYOK).
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
                {testResult.error && (
                  <div className="space-y-1">
                    <p className="break-words text-destructive">{testResult.error}</p>
                    {looksLikePermissionError(testResult.error) && (
                      <p className="rounded bg-amber-100 px-2 py-1 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                        Parece erro de permissão: se este modelo for de provedor chinês, habilite{" "}
                        <span className="font-medium">&quot;modelos hospedados na China&quot;</span> na sua
                        assinatura GO (opencode.ai/auth) e teste novamente.
                      </p>
                    )}
                  </div>
                )}
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
    </TooltipProvider>
  );
}
