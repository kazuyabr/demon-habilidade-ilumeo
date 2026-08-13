"use client";

import { useState } from "react";
import { Send, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { RagAnswer } from "@/lib/types";

const SUGGESTIONS = [
  "Qual é o principal risco de crédito da Transportadora Estrela?",
  "A Indústria Lumina tem bandeiras vermelhas?",
  "Qual empresa tem o melhor perfil de crédito e por quê?",
  "Qual o endividamento da Varejo Horizonte?",
];

export function Chat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [loading, setLoading] = useState(false);

  async function ask(q: string) {
    if (!q.trim() || loading) return;
    setLoading(true);
    setAnswer(null);
    try {
      const res = await fetch("/api/rag/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? "Erro");
      setAnswer(body as RagAnswer);
    } catch (e) {
      setAnswer({
        question: q,
        answer: `Erro ao consultar: ${(e as Error).message}`,
        citations: [],
        grounded: false,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Card className="h-fit">
        <CardHeader>
          <CardTitle className="text-sm">Pergunte aos documentos</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Textarea
              placeholder="Ex.: Qual o risco de crédito da Transportadora Estrela?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(question);
                }
              }}
              rows={2}
            />
            <Button onClick={() => ask(question)} disabled={loading || !question.trim()} className="h-auto">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>

          {answer && (
            <div className="space-y-3 rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">Pergunta: {answer.question}</p>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{answer.answer}</p>
              {answer.citations.length > 0 && (
                <div className="space-y-2 border-t pt-3">
                  <p className="text-xs font-medium text-muted-foreground">
                    Fontes ({answer.citations.length})
                  </p>
                  {answer.citations.map((c) => (
                    <div key={c.index} className="rounded bg-muted/60 px-3 py-2">
                      <p className="text-xs">
                        <Badge variant="outline" className="mr-2">[{c.index}]</Badge>
                        {c.document_title}
                        <span className="ml-2 text-muted-foreground">score {c.score.toFixed(3)}</span>
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{c.snippet}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="h-fit">
        <CardHeader><CardTitle className="text-sm">Sugestões</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => {
                setQuestion(s);
                ask(s);
              }}
              className="w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-accent"
            >
              {s}
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
