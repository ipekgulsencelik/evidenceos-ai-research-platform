/** Public, non-sensitive web liveness probe; no session or IdP required. */
import { NextResponse } from "next/server";

export function GET(): NextResponse {
  return NextResponse.json({ status: "ok" }, {
    headers: { "Cache-Control": "no-store" },
  });
}
