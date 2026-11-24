import { NextRequest, NextResponse } from "next/server";

import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string }> }

export async function GET(request: NextRequest, context: Context): Promise<NextResponse> {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ detail: "Invalid project ID." }, { status: 422 });
  }
  const query = request.nextUrl.searchParams;
  const allowed = new URLSearchParams();
  for (const key of ["query", "status", "tag"]) {
    const value = query.get(key);
    if (value) allowed.set(key, value.slice(0, 120));
  }
  allowed.set("limit", "100");
  const path = "/api/v1/projects/" + projectId + "/library?" + allowed.toString();
  const result = await callBackend(path);
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
