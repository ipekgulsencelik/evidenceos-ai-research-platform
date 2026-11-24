import { NextRequest, NextResponse } from "next/server";

import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";
import { validateProjectTitle } from "@/lib/workspace";

export async function GET(): Promise<NextResponse> {
  const result = await callBackend("/api/v1/projects");
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const value: unknown = await request.json().catch(() => null);
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return NextResponse.json({ detail: "Invalid project request." }, { status: 400 });
  }
  const form = value as Record<string, unknown>;
  if (typeof form.title !== "string" || form.domain !== "academic") {
    return NextResponse.json({ detail: "An academic project title is required." }, { status: 422 });
  }
  const issue = validateProjectTitle(form.title);
  if (issue) return NextResponse.json({ detail: issue }, { status: 422 });
  const result = await callBackend("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: form.title.trim(), domain: "academic" }),
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
