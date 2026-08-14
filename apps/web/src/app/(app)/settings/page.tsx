import { SettingsPanel } from "@/components/settings/settings-panel";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Configurações</h1>
        <p className="text-sm text-muted-foreground">
          Configure os providers de IA (chat e embeddings), tuning do RAG e feature flags —
          aplicado em tempo real, sem redeploy. Ao selecionar um provider, defina seu host e
          chave (BYOK, criptografado) ou use o default do ambiente.
        </p>
      </div>
      <SettingsPanel />
    </div>
  );
}
