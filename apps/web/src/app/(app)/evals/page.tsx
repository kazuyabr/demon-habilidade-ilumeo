import { EvalStudio } from "@/components/evals/eval-studio";

export default function EvalsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Evals</h1>
        <p className="text-sm text-muted-foreground">
          Definições de eval gerenciáveis pelo painel — o guardrail para trocar modelo ou prompt sem regressão.
        </p>
      </div>
      <EvalStudio />
    </div>
  );
}
