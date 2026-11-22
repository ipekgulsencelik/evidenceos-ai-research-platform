import { NextResponse } from "next/server";

import { callBackend } from "@/lib/server-proxy";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const response = await callBackend("/api/v1/identity");
  return NextResponse.json(response.body, {
    status: response.status, headers: { "Cache-Control": "no-store" },
  });
}
