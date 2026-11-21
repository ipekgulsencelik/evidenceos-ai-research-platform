import { NextRequest, NextResponse } from "next/server";

import { callBackend } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string; entryId: string }> }

async function pathOf(context: Context): Promise<string | null> {
  const { projectId, entryId } = await context.params;
  if (!isUuid(projectId) || !isUuid(entryId)) return null;
  return "/api/v1/projects/" + projectId + "/literature/" + entryId + "/reviews";
}

export async function GET(_request: NextRequest, context: Context): Promise<NextResponse> {
  const path = await pathOf(context);
  if (!path) return NextResponse.json({ detail: "Invalid identifier." }, { status: 422 });
  const result = await callBackend(path + "?limit=100");
  return NextResponse.json(result.body, {
    status: result.status, headers: { "Cache-Control": "no-store" },
  });
}

export async function POST(request: NextRequest, context: Context): Promise<NextResponse> {
  const path = await pathOf(context);
  if (!path) return NextResponse.json({ detail: "Invalid identifier." }, { status: 422 });
  const value: unknown = await request.json().catch(() => null);
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return NextResponse.json({ detail: "Invalid review request." }, { status: 400 });
  }
  const body = value as Record<string, unknown>;
  if (
    typeof body.facet !== "string" ||
    !["aim", "method", "sample", "instruments", "findings", "limitations"].includes(body.facet) ||
    typeof body.corrected_value !== "string" || body.corrected_value.length > 500 ||
    typeof body.note !== "string" || body.note.length > 1000 ||
    typeof body.reviewed !== "boolean"
  ) {
    return NextResponse.json({ detail: "Invalid review fields." }, { status: 422 });
  }
  const result = await callBackend(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      facet: body.facet, corrected_value: body.corrected_value,
      note: body.note, reviewed: body.reviewed,
    }),
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: { "Cache-Control": "no-store" },
  });
}
