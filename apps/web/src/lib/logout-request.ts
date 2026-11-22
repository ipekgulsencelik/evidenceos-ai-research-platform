/** Logout CSRF guard for browser-driven POSTs.
 *
 * X-EvidenceOS-Logout is a non-CORS-safelisted request header: an unrelated
 * origin cannot send it without a successful CORS preflight, which our app
 * does not enable. Origin wins if present (including an explicit "null");
 * when the browser omits Origin, Fetch Metadata must prove same-origin.
 * Never trust Host/X-Forwarded-* or Referer for this decision.
 */
export const LOGOUT_REQUEST_HEADER = "X-EvidenceOS-Logout";

export function isAuthorizedLogoutRequest(headers: Headers, expectedOrigin: string): boolean {
  if (headers.get(LOGOUT_REQUEST_HEADER) !== "1") return false;
  const origin = headers.get("origin");
  if (origin !== null) return origin === expectedOrigin;
  return headers.get("sec-fetch-site") === "same-origin";
}
