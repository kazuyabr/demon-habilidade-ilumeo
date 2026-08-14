import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const res = await serverFetch(`/documents/${id}`, { method: "DELETE" });
  return new NextResponse(null, { status: res.status });
}
