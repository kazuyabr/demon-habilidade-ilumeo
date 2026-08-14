import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/api";

export async function POST(req: Request) {
  const form = await req.formData();
  const res = await serverFetch("/documents/upload", { method: "POST", body: form });
  return NextResponse.json(await res.json(), { status: res.status });
}
