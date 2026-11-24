import { NextRequest, NextResponse } from "next/server";

import { MAX_PDF_BYTES, validatePdfUpload } from "@/lib/document";
import { callBackend, gatewayResponseHeaders } from "@/lib/server-proxy";

export const runtime = "nodejs";

export async function POST(request: NextRequest): Promise<NextResponse> {
  // Reject obviously oversized requests before multipart parsing.
  const length = Number(request.headers.get("content-length"));
  if (Number.isFinite(length) && length > MAX_PDF_BYTES + 16384) {
    return NextResponse.json({ detail: "PDF exceeds the 8 MiB limit." }, { status: 413 });
  }
  const form = await request.formData().catch(() => null);
  if (!form) {
    return NextResponse.json({ detail: "Invalid PDF upload." }, { status: 400 });
  }
  const upload = form.get("file");
  const claim = form.get("claim");
  if (!(upload instanceof File) || typeof claim !== "string") {
    return NextResponse.json({ detail: "Provide a PDF file and a claim." }, { status: 422 });
  }
  const issue = validatePdfUpload(upload, claim);
  if (issue) {
    return NextResponse.json({ detail: issue }, {
      status: upload.size > MAX_PDF_BYTES ? 413 : 422,
    });
  }

  const data = new FormData();
  data.append("file", upload, upload.name);
  data.append("claim", claim.trim());
  const result = await callBackend("/api/v1/documents/retrieve-passages", {
    method: "POST",
    body: data,
  });
  return NextResponse.json(result.body, {
    status: result.status, headers: gatewayResponseHeaders(result),
  });
}
