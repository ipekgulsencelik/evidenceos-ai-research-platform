import { NextRequest, NextResponse } from "next/server";

import { validateSearch } from "@/lib/academic";
import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const query = request.nextUrl.searchParams.get("query")?.trim() || "";
  const rawLimit = request.nextUrl.searchParams.get("limit") || "10";
  const limit = Number(rawLimit);
  const issue = validateSearch(query, limit);
  if (issue) return NextResponse.json({ detail: issue }, { status: 422 });

  const search = new URLSearchParams({ query, limit: String(limit) });
  const result = await callBackend(`/api/v1/academic/works?${search.toString()}`);
  return NextResponse.json(result.body, { status: result.status, headers: gatewayResponseHeaders(result) });
}
