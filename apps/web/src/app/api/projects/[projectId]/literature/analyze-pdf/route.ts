import { NextRequest, NextResponse } from "next/server";

import { MAX_PDF_BYTES } from "@/lib/document";
import { validateLiteratureUpload } from "@/lib/literature";
import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";
import { isUuid } from "@/lib/workspace";

export const runtime = "nodejs";

interface Context { params: Promise<{ projectId: string }> }

export async function POST(request: NextRequest, context: Context): Promise<NextResponse> {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json({ detail: "Invalid project ID." }, { status: 422 });
  }
  const length = Number(request.headers.get("content-length"));
  if (Number.isFinite(length) && length > MAX_PDF_BYTES + 16384) {
    return NextResponse.json({ detail: "PDF exceeds the 8 MiB limit." }, { status: 413 });
  }
  const form = await request.formData().catch(() => null);
  if (!form) {
    return NextResponse.json({ detail: "Invalid multipart form." }, { status: 400 });
  }
  const file = form.get("file");
  const consent = form.get("share_excerpts_with_ai") === "true";
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "PDF file is required." }, { status: 422 });
  }
  const issue = validateLiteratureUpload(file, consent);
  if (issue) {
    return NextResponse.json({ detail: issue }, {
      status: file.size > MAX_PDF_BYTES ? 413 : 422,
    });
  }
  const outgoing = new FormData();
  outgoing.append("file", file, file.name);
  outgoing.append("share_excerpts_with_ai", "true");
  const result = await callBackend(
    "/api/v1/projects/" + projectId + "/literature/analyze-pdf",
    { method: "POST", body: outgoing },
  );
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
