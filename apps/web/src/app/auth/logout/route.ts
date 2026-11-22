/** POST-only, same-origin sign out. No cross-site GET can clear a session. */
import { NextRequest, NextResponse } from "next/server";

import { browserOidcSettings } from "@/lib/oidc-client";
import { FLOW_COOKIE, SESSION_COOKIE, cookieOptions, readSession } from "@/lib/oidc-session";
import { getSessionRegistry } from "@/lib/session-registry";

export const runtime = "nodejs";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const settings = browserOidcSettings();
  if (!settings) return new NextResponse("OIDC login is not configured.", { status: 503 });
  if (request.headers.get("origin") !== settings.origin) {
    return new NextResponse("Forbidden", { status: 403 });
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
  const response = NextResponse.redirect(new URL("/signin", settings.origin), { status: 303 });
  response.headers.set("Cache-Control", "no-store");
  for (const name of [FLOW_COOKIE, SESSION_COOKIE]) {
    response.cookies.set(name, "", {
      ...cookieOptions(settings.secureCookies, 0), expires: new Date(0),
    });
  }
  return response;
}
