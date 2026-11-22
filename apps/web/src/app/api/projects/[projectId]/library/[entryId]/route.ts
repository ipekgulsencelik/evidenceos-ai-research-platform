import { NextRequest, NextResponse } from "next/server";

import { validateTags } from "@/lib/research-library";
import { callBackend } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string; entryId: string }> }

export async function PUT(request: NextRequest, context: Context): Promise<NextResponse> {
  const { projectId, entryId } = await context.params;
  if (!isUuid(projectId) || !isUuid(entryId)) {
    return NextResponse.json({ detail: "Invalid identifier." }, { status: 422 });
  }
  const value: unknown = await request.json().catch(() => null);
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return NextResponse.json({ detail: "Invalid catalog request." }, { status: 400 });
  }
  const body = value as Record<string, unknown>;
  if (!["to_read", "reading", "reviewed"].includes(String(body.status))
      || !Array.isArray(body.tags)
      || !body.tags.every((tag) => typeof tag === "string")) {
    return NextResponse.json({ detail: "Invalid reading status or tags." }, { status: 422 });
  }
  const issue = validateTags(body.tags as string[]);
  if (issue) return NextResponse.json({ detail: issue }, { status: 422 });
  const path = "/api/v1/projects/" + projectId + "/library/" + entryId;
  const result = await callBackend(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: body.status, tags: body.tags }),
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: { "Cache-Control": "no-store" },
  });
}
