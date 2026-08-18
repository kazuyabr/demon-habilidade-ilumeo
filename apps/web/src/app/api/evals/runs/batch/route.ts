import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function POST(req: Request) {
  const body = await req.json();
  const res = await serverFetch("/evals/runs/batch", { method: "POST", body: JSON.stringify(body) });
  return NextResponse.json(await res.json(), { status: res.status });
}