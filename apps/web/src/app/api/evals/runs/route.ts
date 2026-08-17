import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function POST(req: Request) {
  const body = await req.json();
  const res = await serverFetch("/evals/runs", { method: "POST", body: JSON.stringify(body) });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function GET() {
  const res = await serverFetch("/evals/runs");
  return NextResponse.json(await res.json(), { status: res.status });
}