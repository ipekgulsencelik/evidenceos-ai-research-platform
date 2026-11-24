import { NextRequest, NextResponse } from "next/server";

import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string }> }

export async function POST(request: NextRequest, context: Context): Promise<NextResponse> {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ detail: "Invalid project ID." }, { status: 422 });
  }
  const value: unknown = await request.json().catch(() => null);
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return NextResponse.json({ detail: "Invalid semantic comparison request." }, { status: 400 });
  }
  const payload = value as Record<string, unknown>;
  const ids = payload.entry_ids;
  if (!Array.isArray(ids) || ids.length < 2 || ids.length > 10
      || !ids.every((id) => typeof id === "string" && isUuid(id))
      || new Set(ids).size !== ids.length
      || payload.consent_to_share_quotes !== true) {
    return NextResponse.json({
      detail: "Select 2–10 different analyses and explicitly consent to sharing quotes with Groq.",
    }, { status: 422 });
  }
  const result = await callBackend("/api/v1/projects/" + projectId + "/semantic-gaps", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      entry_ids: ids,
      consent_to_share_quotes: true,
    }),
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
