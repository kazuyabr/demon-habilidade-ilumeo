import { serverFetch } from "@/lib/api";

// Proxies the backend SSE stream (Redis pub/sub → live agent trace).
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const backend = await serverFetch(`/agents/runs/${id}/stream`);

  return new Response(backend.body, {
    status: backend.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
