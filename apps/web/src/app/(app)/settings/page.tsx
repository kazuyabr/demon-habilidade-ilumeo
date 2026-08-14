import { CredentialsCard } from "@/components/settings/credentials-card";
import { SettingsPanel } from "@/components/settings/settings-panel";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Configurações</h1>
        <p className="text-sm text-muted-foreground">
          Configure os providers de IA (chat e embeddings), tuning do RAG e feature flags —
          aplicado em tempo real, sem redeploy. Chaves permanecem no ambiente ou nas suas
          credenciais (BYOK).
        </p>
      </div>
      <SettingsPanel />
      <CredentialsCard />
    </div>
  );
}
