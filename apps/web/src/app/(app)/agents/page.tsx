import { AgentStudio } from "@/components/agents/agent-studio";

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Agentes</h1>
        <p className="text-sm text-muted-foreground">
          Orquestração multi-etapa (plan → retrieve → analyze → review → final) com trace ao vivo via SSE.
        </p>
      </div>
      <AgentStudio />
    </div>
  );
}
