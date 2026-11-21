import { NextRequest, NextResponse } from "next/server";

import { validateCitation } from "@/lib/academic";
import { callBackend } from "@/lib/server-proxy";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const value: unknown = await request.json().catch(() => null);
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return NextResponse.json({ detail: "Invalid JSON request." }, { status: 400 });
  }
  const body = value as Record<string, unknown>;
  if (typeof body.doi !== "string" || (body.expected_title !== undefined && typeof body.expected_title !== "string")) {
    return NextResponse.json({ detail: "DOI and expected title must be strings." }, { status: 422 });
  }
  const doi = body.doi.trim();
  const expected_title = typeof body.expected_title === "string" ? body.expected_title.trim() : "";
  const issue = validateCitation(doi, expected_title);
  if (issue) return NextResponse.json({ detail: issue }, { status: 422 });

  const result = await callBackend("/api/v1/academic/citations/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doi, expected_title: expected_title || null }),
  });
  return NextResponse.json(result.body, { status: result.status, headers: { "Cache-Control": "no-store" } });
}
