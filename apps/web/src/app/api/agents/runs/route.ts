import { NextResponse } from "next/server";

import { BACKEND_URL, TOKEN_COOKIE } from "@/lib/api";
import { cookies } from "next/headers";

export async function POST(req: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }
  const body = await req.json();
  const res = await fetch(`${BACKEND_URL}/api/v1/agents/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }
  const res = await fetch(`${BACKEND_URL}/api/v1/agents/runs`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
