import { NextResponse } from "next/server";

import { callBackend } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string; entryId: string }> }

export async function GET(_request: Request, context: Context): Promise<NextResponse> {
  const { projectId, entryId } = await context.params;
  if (!isUuid(projectId) || !isUuid(entryId)) {
    return NextResponse.json({ detail: "Invalid identifier." }, { status: 422 });
  }
  const result = await callBackend(
    "/api/v1/projects/" + projectId + "/literature/" + entryId + "/quality-checklist",
  );
  return NextResponse.json(result.body, {
    status: result.status, headers: { "Cache-Control": "no-store" },
  });
}
