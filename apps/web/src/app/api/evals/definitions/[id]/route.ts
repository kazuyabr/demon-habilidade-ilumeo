import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const res = await serverFetch(`/evals/definitions/${id}`);
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const body = await req.json();
  const res = await serverFetch(`/evals/definitions/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const res = await serverFetch(`/evals/definitions/${id}`, { method: "DELETE" });
  return new NextResponse(null, { status: res.status });
}