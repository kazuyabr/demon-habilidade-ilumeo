import { BACKEND_URL, TOKEN_COOKIE } from "@/lib/api";
import { cookies } from "next/headers";

// Proxies the backend SSE stream (Redis pub/sub → live agent trace).
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const cookieStore = await cookies();
  const token = cookieStore.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return new Response("não autenticado", { status: 401 });
  }

  const backend = await fetch(`${BACKEND_URL}/api/v1/agents/runs/${id}/stream`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  return new Response(backend.body, {
    status: backend.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
