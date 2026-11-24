import { NextRequest, NextResponse } from "next/server";

import { MAX_PDF_BYTES } from "@/lib/document";
import { validateLiteratureUpload } from "@/lib/literature";
import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";

export const runtime = "nodejs";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const length = Number(request.headers.get("content-length"));
  if (Number.isFinite(length) && length > MAX_PDF_BYTES + 16384) {
    return NextResponse.json({ detail: "PDF exceeds the 8 MiB limit." }, { status: 413 });
  }
  const form = await request.formData().catch(() => null);
  if (!form) return NextResponse.json({ detail: "Invalid multipart form." }, { status: 400 });

  const upload = form.get("file");
  const consent = form.get("share_excerpts_with_ai") === "true";
  if (!(upload instanceof File)) {
    return NextResponse.json({ detail: "PDF file is required." }, { status: 422 });
  }
  const error = validateLiteratureUpload(upload, consent);
  if (error) {
    return NextResponse.json({ detail: error }, {
      status: upload.size > MAX_PDF_BYTES ? 413 : 422,
    });
  }
  const outgoing = new FormData();
  outgoing.append("file", upload, upload.name);
  outgoing.append("share_excerpts_with_ai", "true");
  const result = await callBackend("/api/v1/literature/analyze-pdf", {
    method: "POST", body: outgoing,
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
