import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { SessionRefresher } from "@/components/session-refresher";
import { Sidebar } from "@/components/layout/sidebar";
import { REFRESH_TOKEN_COOKIE, TOKEN_COOKIE } from "@/lib/api";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const hasAccess = Boolean(cookieStore.get(TOKEN_COOKIE));
  const hasRefresh = Boolean(cookieStore.get(REFRESH_TOKEN_COOKIE));
  // Stale sessions (pre-refresh-flow) carry only the access token and cannot
  // self-heal — send them to /login instead of showing an error page.
  if (!hasAccess || !hasRefresh) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-full flex-1">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-background px-8 py-6">{children}</main>
      <SessionRefresher />
    </div>
  );
}
