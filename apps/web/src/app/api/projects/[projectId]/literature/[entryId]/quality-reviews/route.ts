import { NextRequest, NextResponse } from "next/server";

import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";
import {
  DIMENSIONS, hasUnverifiedJudgment,
} from "@/lib/quality";
import type { QualityDraft } from "@/lib/quality";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string; entryId: string }> }

async function pathFor(context: Context): Promise<string | null> {
  const { projectId, entryId } = await context.params;
  return isUuid(projectId) && isUuid(entryId)
    ? "/api/v1/projects/" + projectId + "/literature/" + entryId + "/quality-reviews"
    : null;
}

export async function GET(_request: Request, context: Context): Promise<NextResponse> {
  const path = await pathFor(context);
  if (!path) return NextResponse.json({ detail: "Invalid identifier." }, { status: 422 });
  const result = await callBackend(path + "?limit=100");
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}

export async function POST(request: NextRequest, context: Context): Promise<NextResponse> {
  const path = await pathFor(context);
  if (!path) return NextResponse.json({ detail: "Invalid identifier." }, { status: 422 });
  const input: unknown = await request.json().catch(() => null);
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return NextResponse.json({ detail: "Invalid review." }, { status: 400 });
  }
  const body = input as Record<string, unknown>;
  if (!DIMENSIONS.includes(body.dimension as (typeof DIMENSIONS)[number])
      || !["not_assessed", "reported_in_full_text", "unclear_after_review",
        "not_reported_in_full_text", "not_applicable"].includes(String(body.reporting))
      || !["not_assessed", "potential_concern", "no_concern_identified"]
        .includes(String(body.concern))
      || typeof body.checked_original !== "boolean"
      || typeof body.note !== "string" || body.note.length > 1000) {
    return NextResponse.json({ detail: "Invalid review fields." }, { status: 422 });
  }
  const draft = body as unknown as QualityDraft;
  if (hasUnverifiedJudgment(draft)) {
    return NextResponse.json({
      detail: "Verify the original full text before entering reporting or concern judgments.",
    }, { status: 422 });
  }
  const result = await callBackend(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
