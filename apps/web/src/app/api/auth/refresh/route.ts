import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { BACKEND_URL, REFRESH_TOKEN_COOKIE, TOKEN_COOKIE, authCookieOptions } from "@/lib/api";

// Refreshes the session: accepts a refresh token in the body (server-side
// retry from backendFetch) or falls back to the refresh cookie (browser).
// Rotates both cookies on the response.
export async function POST(req: Request) {
  let refreshToken: string | null = null;
  try {
    const body = await req.json();
    refreshToken = body?.refresh_token ?? null;
  } catch {
    /* no body */
  }
  if (!refreshToken) {
    const store = await cookies();
    refreshToken = store.get(REFRESH_TOKEN_COOKIE)?.value ?? null;
  }
  if (!refreshToken) {
    return NextResponse.json({ detail: "Sessão expirada" }, { status: 401 });
  }

  const res = await fetch(
    `${BACKEND_URL}/api/v1/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`,
    { method: "POST", cache: "no-store" },
  );
  const payload = await res.json();
  if (!res.ok) {
    return NextResponse.json(payload, { status: res.status });
  }

  const response = NextResponse.json(payload);
  const opts = authCookieOptions();
  response.cookies.set({ ...opts, name: TOKEN_COOKIE, value: payload.access_token });
  response.cookies.set({ ...opts, name: REFRESH_TOKEN_COOKIE, value: payload.refresh_token });
  return response;
}
