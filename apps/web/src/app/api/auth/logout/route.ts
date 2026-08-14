import { NextResponse } from "next/server";

import { REFRESH_TOKEN_COOKIE, TOKEN_COOKIE } from "@/lib/api";

export async function POST() {
  const response = NextResponse.json({ ok: true });
  for (const name of [TOKEN_COOKIE, REFRESH_TOKEN_COOKIE]) {
    response.cookies.set({ name, value: "", httpOnly: true, path: "/", maxAge: 0 });
  }
  return response;
}
