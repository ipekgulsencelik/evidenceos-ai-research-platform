import { NextRequest, NextResponse } from "next/server";

import { validateEvidenceRequest } from "@/lib/evidence";
import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const body: unknown = await request.json().catch(() => null);
  const issue = validateEvidenceRequest(body);
  if (issue) return NextResponse.json({ detail: issue }, { status: 422 });

  const response = await callBackend("/api/v1/evidence/assess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return NextResponse.json(response.body, {
    status: response.status, headers: gatewayResponseHeaders(response),
  });
}
