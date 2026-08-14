"use client";

import { useEffect } from "react";

// Keeps the httpOnly session cookies fresh: access tokens last 30 min, so
// periodically call the refresh route handler (which rotates both cookies on
// the real browser response). No-op when there is no refresh cookie.
export function SessionRefresher() {
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        await fetch("/api/auth/refresh", { method: "POST" });
      } catch {
        /* ignore transient errors */
      }
    };
    void refresh();
    const id = setInterval(() => {
      if (active) void refresh();
    }, 4 * 60 * 1000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);
  return null;
}
