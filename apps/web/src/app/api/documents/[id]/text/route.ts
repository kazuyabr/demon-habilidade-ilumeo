import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const res = await serverFetch(`/documents/${id}/text`);
  return NextResponse.json(await res.json(), { status: res.status });
}