import { NextResponse } from "next/server";

import { BACKEND_URL, TOKEN_COOKIE } from "@/lib/api";
import { cookies } from "next/headers";

export async function POST(req: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }

  const form = await req.formData();
  const res = await fetch(`${BACKEND_URL}/api/v1/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    cache: "no-store",
  });
  const payload = await res.json();
  return NextResponse.json(payload, { status: res.status });
}
