// Server-side API client: reads the httpOnly session cookies and calls the
// backend. Used by Server Components and Route Handlers — the JWT never
// touches the browser bundle.
//
// Access tokens are short-lived (30 min). On a 401 the client transparently
// refreshes the session (refresh token cookie → new access token) and retries
// once, so SSR pages and route handlers self-heal when the access token
// expires without forcing the user to log in again.

import { cookies } from "next/headers";

export const BACKEND_URL =
  process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8010";

export const TOKEN_COOKIE = "risklens_token";
export const REFRESH_TOKEN_COOKIE = "risklens_refresh_token";

const AUTH_COOKIE_MAX_AGE = 60 * 60 * 12; // matches API refresh token window

async function readCookie(name: string): Promise<string | null> {
  const store = await cookies();
  return store.get(name)?.value ?? null;
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = await readCookie(REFRESH_TOKEN_COOKIE);
  if (!refresh) return null;
  try {
    const res = await fetch(
      `${BACKEND_URL}/api/v1/auth/refresh?refresh_token=${encodeURIComponent(refresh)}`,
      { method: "POST", cache: "no-store" },
    );
    if (!res.ok) return null;
    const payload = await res.json();
    return payload.access_token ?? null;
  } catch {
    return null;
  }
}

/**
 * Fetch from the backend with the session token; on 401 refreshes the access
 * token (refresh cookie) and retries once. Returns the raw Response.
 */
export async function serverFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = await readCookie(TOKEN_COOKIE);
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const doFetch = (authHeader: string | null) => {
    const h = new Headers(headers);
    if (authHeader) h.set("Authorization", authHeader);
    return fetch(`${BACKEND_URL}/api/v1${path}`, { ...init, headers: h, cache: "no-store" });
  };

  let res = await doFetch(token ? `Bearer ${token}` : null);
  if (res.status === 401) {
    const fresh = await refreshAccessToken();
    if (fresh) {
      res = await doFetch(`Bearer ${fresh}`);
    }
  }
  return res;
}

export async function backendFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await serverFetch(path, init);
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

export function authCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: AUTH_COOKIE_MAX_AGE,
  };
}
