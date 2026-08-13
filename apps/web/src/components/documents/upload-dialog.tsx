"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function UploadDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleUpload() {
    if (!file) {
      toast.warning("Selecione um arquivo");
      return;
    }
    setLoading(true);
    const form = new FormData();
    form.append("file", file);
    if (source) form.append("source", source);

    const res = await fetch("/api/documents/upload", { method: "POST", body: form });
    const body = await res.json();
    if (!res.ok) {
      toast.error(body.detail ?? "Falha no upload");
      setLoading(false);
      return;
    }
    toast.success(body.duplicate ? "Documento já existia (deduplicado)" : "Upload enfileirado");
    setOpen(false);
    setFile(null);
    setSource("");
    if (inputRef.current) inputRef.current.value = "";
    router.refresh();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button><Upload className="mr-2 h-4 w-4" />Upload</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload de relatório</DialogTitle>
          <DialogDescription>
            Submeta um relatório (.md, .txt, .pdf). O worker extrai o perfil de risco, redige PII e indexa para RAG.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <Label htmlFor="file">Arquivo</Label>
            <Input
              ref={inputRef}
              id="file"
              type="file"
              accept=".md,.txt,.pdf,.markdown"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="source">Origem (opcional)</Label>
            <Input
              id="source"
              placeholder="relatorio | contrato | pesquisa"
              value={source}
              onChange={(e) => setSource(e.target.value)}
            />
          </div>
          <Button className="w-full" onClick={handleUpload} disabled={loading}>
            {loading ? "Enviando…" : "Enviar e processar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
