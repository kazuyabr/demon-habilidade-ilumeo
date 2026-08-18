import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DeleteButton, StatusBadge } from "@/components/documents/status-badge";
import { UploadDialog } from "@/components/documents/upload-dialog";
import { backendFetch } from "@/lib/api";
import type { DocumentItem } from "@/lib/types";

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" });
}

export default async function DocumentsPage() {
  const docs = await backendFetch<DocumentItem[]>("/documents?limit=200");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documentos</h1>
          <p className="text-sm text-muted-foreground">
            Relatórios submetidos — a fila async (arq/Redis) processa extração e indexação.
          </p>
        </div>
        <UploadDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">{docs.length} documentos</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Título</TableHead>
                <TableHead>Origem</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Enviado</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {docs.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>
                    <Link href={`/documents/${d.id}`} className="font-medium hover:underline">
                      {d.title}
                    </Link>
                    <span className="block text-xs text-muted-foreground">{d.filename}</span>
                  </TableCell>
                  <TableCell>{d.source ? <Badge variant="outline">{d.source}</Badge> : "—"}</TableCell>
                  <TableCell>
                    <StatusBadge status={d.status} />
                    {d.error_message && (
                      <span className="block max-w-64 truncate text-xs text-destructive" title={d.error_message}>
                        {d.error_message}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{fmtDate(d.created_at)}</TableCell>
                  <TableCell>
                    <DeleteButton id={d.id} title={d.title} />
                  </TableCell>
                </TableRow>
              ))}
              {docs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                    Nenhum documento ainda. Faça upload de um relatório de exemplo da pasta{" "}
                    <span className="font-mono text-xs">samples/documents</span>.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
