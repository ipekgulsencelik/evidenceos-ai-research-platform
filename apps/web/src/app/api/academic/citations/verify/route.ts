import { NextRequest, NextResponse } from "next/server";

import { parseCitationBody } from "@/lib/academic";
import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const parsed = parseCitationBody(await request.json().catch(() => null));
  if (!parsed.ok) {
    return NextResponse.json({ detail: parsed.detail }, { status: parsed.status });
  }

  const result = await callBackend("/api/v1/academic/citations/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      doi: parsed.doi,
      expected_title: parsed.expected_title,
    }),
  });
  return NextResponse.json(result.body, { status: result.status, headers: gatewayResponseHeaders(result) });
}
