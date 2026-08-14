import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function GET() {
  const res = await serverFetch("/admin/providers");
  return NextResponse.json(await res.json(), { status: res.status });
}
