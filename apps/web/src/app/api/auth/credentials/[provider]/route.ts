import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function PUT(req: Request, ctx: { params: Promise<{ provider: string }> }) {
  const { provider } = await ctx.params;
  const body = await req.json();
  const res = await serverFetch(`/auth/credentials/${provider}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ provider: string }> }) {
  const { provider } = await ctx.params;
  const res = await serverFetch(`/auth/credentials/${provider}`, { method: "DELETE" });
  return new NextResponse(null, { status: res.status });
}
