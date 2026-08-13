import { notFound } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ExtractionView } from "@/components/documents/extraction-view";
import { StatusBadge } from "@/components/documents/status-badge";
import { backendFetch } from "@/lib/api";
import type { DocumentItem, Extraction } from "@/lib/types";

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let doc: DocumentItem;
  try {
    doc = await backendFetch<DocumentItem>(`/documents/${id}`);
  } catch {
    notFound();
  }

  let extraction: Extraction | null = null;
  try {
    extraction = await backendFetch<Extraction>(`/extractions/document/${id}`);
  } catch {
    extraction = null;
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{doc.title}</h1>
          <StatusBadge status={doc.status} />
        </div>
        <p className="text-sm text-muted-foreground">
          {doc.filename} · {doc.content_type} · {(doc.size_bytes / 1024).toFixed(1)} KB
        </p>
      </div>

      {doc.status === "failed" && (
        <Card className="border-destructive">
          <CardHeader><CardTitle className="text-sm text-destructive">Falha no processamento</CardTitle></CardHeader>
          <CardContent><p className="text-sm">{doc.error_message}</p></CardContent>
        </Card>
      )}

      {doc.status === "pending" || doc.status === "processing" ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500" />
            {" "}Documento em processamento pelo worker…
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-medium">Extração estruturada</h2>
            {extraction?.status === "completed" && (
              <Badge variant="outline">schema: {extraction.schema_name}</Badge>
            )}
          </div>
          <ExtractionView data={extraction?.data ?? null} />
        </div>
      )}
    </div>
  );
}
