import { NextRequest, NextResponse } from "next/server";

import { isAssignableRole, isMemberKey } from "@/lib/memberships";
import { callBackend } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string; memberKey: string }> }

function target(projectId: string, memberKey: string): string | null {
  if (!isUuid(projectId) || !isMemberKey(memberKey)) return null;
  return "/api/v1/projects/" + projectId + "/memberships/" + memberKey;
}

export async function PUT(request: NextRequest, context: Context): Promise<NextResponse> {
  const { projectId, memberKey } = await context.params;
  const path = target(projectId, memberKey);
  if (!path) return NextResponse.json({ detail: "Invalid member identifier." }, { status: 422 });
  const payload: unknown = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object" || Array.isArray(payload) ||
      Object.keys(payload).length !== 1 ||
      !isAssignableRole((payload as Record<string, unknown>).role)) {
    return NextResponse.json({ detail: "Choose editor, reviewer or viewer role." }, {
      status: 422, headers: { "Cache-Control": "no-store" },
    });
  }
  const role = (payload as { role: string }).role;
  const result = await callBackend(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: { "Cache-Control": "no-store" },
  });
}

export async function DELETE(_request: NextRequest, context: Context): Promise<NextResponse> {
  const { projectId, memberKey } = await context.params;
  const path = target(projectId, memberKey);
  if (!path) return NextResponse.json({ detail: "Invalid member identifier." }, { status: 422 });
  const result = await callBackend(path, { method: "DELETE" });
  // FastAPI returns an empty 204, which the generic JSON transport treats as
  // invalid content. The bridge should preserve a successful empty response.
  if (result.status === 204) return new NextResponse(null, { status: 204 });
  return NextResponse.json(result.body, {
    status: result.status, headers: { "Cache-Control": "no-store" },
  });
}
