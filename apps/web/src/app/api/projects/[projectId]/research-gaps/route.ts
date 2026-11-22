import { NextRequest, NextResponse } from "next/server";

import { callBackend } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string }> }

export async function POST(request: NextRequest, context: Context): Promise<NextResponse> {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ detail: "Invalid project ID." }, { status: 422 });
  }
  const payload: unknown = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return NextResponse.json({ detail: "Invalid comparison request." }, { status: 400 });
  }
  const ids = (payload as { entry_ids?: unknown }).entry_ids;
  if (!Array.isArray(ids) || ids.length < 2 || ids.length > 10 ||
      !ids.every((id) => typeof id === "string" && isUuid(id)) ||
      new Set(ids).size !== ids.length) {
    return NextResponse.json({ detail: "Select 2–10 different saved analyses." }, { status: 422 });
  }
  const path = "/api/v1/projects/" + projectId + "/research-gaps";
  const result = await callBackend(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entry_ids: ids }),
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: { "Cache-Control": "no-store" },
  });
}
