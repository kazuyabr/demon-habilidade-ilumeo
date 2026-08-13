import { NextResponse } from "next/server";

import { TOKEN_COOKIE } from "@/lib/api";

export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: TOKEN_COOKIE,
    value: "",
    httpOnly: true,
    path: "/",
    maxAge: 0,
  });
  return response;
}
