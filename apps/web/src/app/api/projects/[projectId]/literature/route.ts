import { NextResponse } from "next/server";

import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

interface Context { params: Promise<{ projectId: string }> }

export async function GET(_request: Request, context: Context): Promise<NextResponse> {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ detail: "Invalid project ID." }, { status: 422 });
  }
  const result = await callBackend("/api/v1/projects/" + projectId + "/literature?limit=25");
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
