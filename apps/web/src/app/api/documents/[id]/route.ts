import { NextResponse } from "next/server";

import { BACKEND_URL, TOKEN_COOKIE } from "@/lib/api";
import { cookies } from "next/headers";

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const cookieStore = await cookies();
  const token = cookieStore.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }

  const res = await fetch(`${BACKEND_URL}/api/v1/documents/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return new NextResponse(null, { status: res.status });
}
