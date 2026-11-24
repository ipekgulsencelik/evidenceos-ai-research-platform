import { NextRequest, NextResponse } from "next/server";

import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string; entryId: string }> }

export async function POST(request: NextRequest, context: Context): Promise<NextResponse> {
  const { projectId, entryId } = await context.params;
  if (!isUuid(projectId) || !isUuid(entryId)) {
    return NextResponse.json({ detail: "Invalid project or analysis ID." }, { status: 422 });
  }
  const value: unknown = await request.json().catch(() => null);
  if (!value || typeof value !== "object" || Array.isArray(value)
    || (value as Record<string, unknown>).consent_to_share_quotes !== true) {
    return NextResponse.json({
      detail: "Explicit consent to share selected excerpts with Groq is required.",
    }, { status: 422 });
  }
  const result = await callBackend(
    "/api/v1/projects/" + projectId + "/literature/" + entryId + "/methodology-review",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ consent_to_share_quotes: true }),
    },
  );
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
