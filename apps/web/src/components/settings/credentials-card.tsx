"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { KeyRound, Loader2, Save, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CredentialSummary, ProviderRegistryEntry } from "@/lib/types";

type Draft = { base_url: string; api_key: string };

export function CredentialsCard() {
  const [providers, setProviders] = useState<ProviderRegistryEntry[]>([]);
  const [creds, setCreds] = useState<Record<string, CredentialSummary>>({});
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    const [pRes, cRes] = await Promise.all([
      fetch("/api/admin/providers"),
      fetch("/api/auth/credentials"),
    ]);
    if (pRes.ok) {
      const p = (await pRes.json()) as { providers: ProviderRegistryEntry[] };
      const creditable = (p.providers ?? []).filter((pr) => (pr.chat || pr.embeddings) && pr.id !== "fastembed");
      setProviders(creditable);
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

  const setDraft = (provider: string, field: keyof Draft, value: string) => {
    setDrafts((prev) => ({ ...prev, [provider]: { ...(prev[provider] ?? { base_url: "", api_key: "" }), [field]: value } }));
  };

  async function save(provider: string) {
    setSaving(provider);
    const d = drafts[provider] ?? { base_url: "", api_key: "" };
    const payload: Record<string, string> = {};
    if (d.base_url.trim()) payload.base_url = d.base_url.trim();
    if (d.api_key.trim()) payload.api_key = d.api_key.trim();
    const res = await fetch(`/api/auth/credentials/${provider}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json();
      toast.error(body.detail ?? "Falha ao salvar credencial");
      setSaving(null);
      return;
    }
    const summary = (await res.json()) as CredentialSummary;
    setCreds((prev) => ({ ...prev, [provider]: summary }));
    setDrafts((prev) => ({ ...prev, [provider]: { base_url: "", api_key: "" } }));
    toast.success(`Credencial de ${provider} salva`);
    setSaving(null);
  }

  async function remove(provider: string) {
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

  const sorted = useMemo(
    () => [...providers].sort((a, b) => a.label.localeCompare(b.label)),
    [providers],
  );

  if (!loaded) {
    return <p className="text-sm text-muted-foreground">Carregando credenciais…</p>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Minhas credenciais (BYOK)</CardTitle>
        <CardDescription>
          Cada usuário traz a própria chave/host por provider — criptografadas em repouso.
          Onde você não definir, usa-se o default do ambiente. A chave nunca é exibida.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {sorted.map((p) => {
          const c = creds[p.id];
          const d = drafts[p.id];
          return (
            <div key={p.id} className="rounded-md border px-3 py-3">
              <div className="mb-2 flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">{p.label}</span>
                {c?.has_api_key && (
                  <Badge variant="outline">chave ••••{c.api_key_last4}</Badge>
                )}
                {c?.has_base_url && <Badge variant="outline">host próprio</Badge>}
                {!c && <Badge variant="secondary">usa default do env</Badge>}
              </div>
              <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
                <div className="space-y-1">
                  <Label className="text-xs">Host (opcional — p/ local/gateway)</Label>
                  <Input
                    placeholder={p.api ?? "https://..."}
                    value={d?.base_url ?? ""}
                    onChange={(e) => setDraft(p.id, "base_url", e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">API key (opcional)</Label>
                  <Input
                    type="password"
                    placeholder="••••••••"
                    value={d?.api_key ?? ""}
                    onChange={(e) => setDraft(p.id, "api_key", e.target.value)}
                  />
                </div>
                <div className="flex items-end gap-1">
                  <Button size="sm" onClick={() => save(p.id)} disabled={saving === p.id}>
                    {saving === p.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Salvar
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove(p.id)}
                    disabled={!c}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
