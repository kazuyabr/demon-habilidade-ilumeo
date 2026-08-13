import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { Sidebar } from "@/components/layout/sidebar";
import { TOKEN_COOKIE } from "@/lib/api";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.get(TOKEN_COOKIE)) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-full flex-1">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-background px-8 py-6">{children}</main>
    </div>
  );
}
