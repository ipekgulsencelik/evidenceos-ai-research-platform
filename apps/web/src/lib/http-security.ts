/** Browser security policy for all Next.js application and auth responses.
 *
 * Next.js App Router requires a per-request CSP nonce on request headers
 * so its own server-rendered bootstrap scripts can be authorized. Static
 * assets are excluded by the proxy matcher and need no nonce.
 */
import { randomBytes } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

export function freshCspNonce(): string {
  return randomBytes(16).toString("base64");
}

export function contentSecurityPolicy(nonce: string, development: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    // Existing components use React inline style props. Do not permit unsafe-inline *scripts*.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self'${development ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function forwardNonce(request: NextRequest, nonce: string): NextResponse {
  const headers = new Headers(request.headers);
  // Never trust client-provided CSP or nonce headers.
  headers.set("Content-Security-Policy", contentSecurityPolicy(nonce, process.env.NODE_ENV !== "production"));
  headers.set("x-nonce", nonce);
  return NextResponse.next({ request: { headers } });
}

export function secureResponse(response: NextResponse, nonce: string): NextResponse {
  response.headers.set(
    "Content-Security-Policy",
    contentSecurityPolicy(nonce, process.env.NODE_ENV !== "production"),
  );
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  // HSTS is appropriate only on the trusted production HTTPS deployment,
  // not on the disposable localhost HTTP staging origin. Deliberately omit
  // includeSubDomains and preload until all subdomains have been audited.
  if (process.env.EVIDENCEOS_APP_ENV === "production") {
    response.headers.set("Strict-Transport-Security", "max-age=31536000");
  }
  return response;
}
