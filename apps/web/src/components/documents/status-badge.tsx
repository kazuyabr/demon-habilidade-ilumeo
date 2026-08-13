"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

import { STATUS_COLORS } from "@/lib/types";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
      <span className={`h-2 w-2 rounded-full ${STATUS_COLORS[status] ?? "bg-zinc-400"}`} />
      {status}
    </span>
  );
}

export function DeleteButton({ id, title }: { id: string; title: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleDelete() {
    if (!confirm(`Excluir "${title}"?`)) return;
    setLoading(true);
    const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
    if (!res.ok) {
      toast.error("Falha ao excluir");
      setLoading(false);
      return;
    }
    toast.success("Documento excluído");
    router.refresh();
  }

  return (
    <button
      onClick={handleDelete}
      disabled={loading}
      className="text-muted-foreground transition-colors hover:text-destructive"
      aria-label="Excluir"
    >
      <Trash2 className="h-4 w-4" />
    </button>
  );
}
