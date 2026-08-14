import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function GET() {
  const res = await serverFetch("/admin/settings");
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function PUT(req: Request) {
  const body = await req.json();
  const res = await serverFetch("/admin/settings", {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
