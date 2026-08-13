import { Chat } from "@/components/ask/chat";

export default function AskPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Perguntar (RAG)</h1>
        <p className="text-sm text-muted-foreground">
          Respostas fundamentadas nos documentos indexados, com busca híbrida (vetorial + FTS) e citações.
        </p>
      </div>
      <Chat />
    </div>
  );
}
