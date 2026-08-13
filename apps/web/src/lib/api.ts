// Server-side API client: reads the httpOnly session cookie and calls the
// backend. Used by Server Components and Route Handlers — the JWT never
// touches the browser bundle.

import { cookies } from "next/headers";

export const BACKEND_URL =
  process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8010";

export const TOKEN_COOKIE = "risklens_token";

export async function backendFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const cookieStore = await cookies();
  const token = cookieStore.get(TOKEN_COOKIE)?.value;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BACKEND_URL}/api/v1${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, String(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
