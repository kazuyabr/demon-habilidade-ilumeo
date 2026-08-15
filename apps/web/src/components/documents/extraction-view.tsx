"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { CreditReportData } from "@/lib/types";

function severityColor(s: string) {
  if (s === "high") return "bg-red-100 text-red-700 dark:bg-red-950";
  if (s === "medium") return "bg-amber-100 text-amber-700 dark:bg-amber-950";
  return "bg-emerald-100 text-emerald-700 dark:bg-emerald-950";
}

function ratingColor(r: string) {
  const map: Record<string, string> = {
    A: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950",
    B: "bg-blue-100 text-blue-700 dark:bg-blue-950",
    C: "bg-amber-100 text-amber-700 dark:bg-amber-950",
    D: "bg-red-100 text-red-700 dark:bg-red-950",
  };
  return map[r] ?? "bg-zinc-100 dark:bg-zinc-800";
}

const decisionLabel: Record<string, string> = {
  approve: "Aprovado",
  conditional: "Condicional",
  decline: "Recusado",
};

export function ExtractionView({ data }: { data: Record<string, unknown> | null }) {
  if (!data) {
    return <p className="text-sm text-muted-foreground">Nenhuma extração disponível.</p>;
  }
  const d = data as CreditReportData;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{d.company_name ?? "—"}</CardTitle>
            <p className="text-sm text-muted-foreground">{d.sector ?? ""}</p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-muted-foreground">Risco global</span>
                <span className="font-semibold">{d.overall_risk_score ?? "—"}/100</span>
              </div>
              <Progress value={d.overall_risk_score ?? 0} className="h-2" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge className={cn(ratingColor(d.risk_rating ?? "?"))}>Rating {d.risk_rating ?? "—"}</Badge>
              <Badge variant="outline">{decisionLabel[d.decision ?? "conditional"] ?? d.decision ?? "—"}</Badge>
              <Badge variant="outline">Confiança {(d.confidence ?? 0).toFixed(2)}</Badge>
            </div>
            <p className="text-sm">{d.decision_justification}</p>
            {d.recommended_limit && (
              <p className="text-sm">
                <span className="text-muted-foreground">Limite recomendado: </span>
                <span className="font-medium">{d.recommended_limit}</span>
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-sm">Saúde financeira</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-2 text-sm">
            {Object.entries(d.financial_health ?? {})
              .filter(([, v]) => v)
              .map(([k, v]) => (
                <div key={k} className="rounded-md bg-accent/50 px-3 py-2">
                  <p className="text-xs text-muted-foreground capitalize">{k.replace("_", " ")}</p>
                  <p className="font-medium">{String(v)}</p>
                </div>
              ))}
          </CardContent>
        </Card>
      </div>

      {d.key_metrics && d.key_metrics.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Métricas-chave</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Métrica</TableHead>
                  <TableHead>Valor</TableHead>
                  <TableHead>Período</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(d.key_metrics ?? []).map((m, i) => (
                  <TableRow key={i}>
                    <TableCell>{m.name}</TableCell>
                    <TableCell className="font-medium">{m.value} {m.unit ?? ""}</TableCell>
                    <TableCell className="text-muted-foreground">{m.period ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {d.credit_factors && d.credit_factors.length > 0 && (
          <Card>
            <CardHeader><CardTitle className="text-sm">Fatores de crédito</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {(d.credit_factors ?? []).map((f, i) => (
                <div key={i} className="rounded-md border px-3 py-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{f.factor}</p>
                    <Badge className={cn(severityColor(f.severity))}>{f.severity}</Badge>
                  </div>
                  {f.assessment && <p className="text-xs text-muted-foreground">{f.assessment}</p>}
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {d.red_flags && d.red_flags.length > 0 && (
          <Card>
            <CardHeader><CardTitle className="text-sm text-destructive">Bandeiras vermelhas</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {(d.red_flags ?? []).map((f, i) => (
                <div key={i} className="rounded-md border border-red-200 px-3 py-2 dark:border-red-950">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{f.flag}</p>
                    <Badge className={cn(severityColor(f.severity))}>{f.severity}</Badge>
                  </div>
                  {f.evidence && <p className="text-xs text-muted-foreground">{f.evidence}</p>}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      <details className="rounded-md border px-4 py-2">
        <summary className="cursor-pointer text-sm text-muted-foreground">Ver JSON completo</summary>
        <pre className="mt-2 max-h-96 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(data, null, 2)}</pre>
      </details>
    </div>
  );
}
