import { NextResponse } from "next/server";

import { BACKEND_URL, TOKEN_COOKIE } from "@/lib/api";

export async function POST(req: Request) {
  const { email, password } = await req.json();
  const body = new URLSearchParams({ username: email, password });

  const res = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
  });

  const payload = await res.json();
  if (!res.ok) {
    return NextResponse.json(payload, { status: res.status });
  }

  const response = NextResponse.json(payload);
  response.cookies.set({
    name: TOKEN_COOKIE,
    value: payload.access_token,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 12,
  });
  return response;
}
