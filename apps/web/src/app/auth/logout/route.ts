/** POST-only, same-origin sign out. No cross-site GET can clear a session. */
import { NextRequest, NextResponse } from "next/server";

import { browserOidcSettings, discoverProvider } from "@/lib/oidc-client";
import { providerLogoutUrl } from "@/lib/provider-logout";
import { isAuthorizedLogoutRequest } from "@/lib/logout-request";
import { FLOW_COOKIE, SESSION_COOKIE, cookieOptions, readSession } from "@/lib/oidc-session";
import { getSessionRegistry } from "@/lib/session-registry";

export const runtime = "nodejs";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const settings = browserOidcSettings();
  if (!settings) return new NextResponse("OIDC login is not configured.", { status: 503 });
  if (!isAuthorizedLogoutRequest(request.headers, settings.origin)) {
    return new NextResponse("Forbidden", {
      status: 403, headers: { "Cache-Control": "no-store" },
    });
  }
  const session = readSession(request.cookies.get(SESSION_COOKIE)?.value);
  if (session) {
    try {
      // Central deletion invalidates *every* copy of this browser cookie.
      await (await getSessionRegistry()).revoke(session.sid);
    } catch {
      // Do not claim logout succeeded while revocation is unconfirmed.
      return new NextResponse("Session revocation temporarily unavailable.", {
        status: 503, headers: { "Cache-Control": "no-store", "Retry-After": "5" },
      });
    }
  }
  // Revoke our browser session *before* talking to the external provider.
  // If discovery is unavailable, never resurrect local access and never
  // misreport provider logout as completed.
  let next = "/signin";
  if (session) {
    try {
      const discovered = await discoverProvider(settings);
      next = providerLogoutUrl(discovered, settings) ||
        "/signin?notice=provider-logout-unavailable";
    } catch {
      next = "/signin?notice=provider-logout-unavailable";
    }
  }

  // A JSON response lets the same-origin fetch complete before the browser
  // makes a top-level cross-origin navigation. Following the IdP redirect
  // inside fetch would fail CORS and leave the user on the current page.
  const response = NextResponse.json({ next }, {
    status: 200, headers: { "Cache-Control": "no-store" },
  });
  for (const name of [FLOW_COOKIE, SESSION_COOKIE]) {
    response.cookies.set(name, "", {
      ...cookieOptions(settings.secureCookies, 0), expires: new Date(0),
    });
  }
  return response;
}
