/** POST-only, same-origin sign out. No cross-site GET can clear a session. */
import { NextRequest, NextResponse } from "next/server";

import { browserOidcSettings } from "@/lib/oidc-client";
import { FLOW_COOKIE, SESSION_COOKIE, cookieOptions } from "@/lib/oidc-session";

export const runtime = "nodejs";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const settings = browserOidcSettings();
  if (!settings) return new NextResponse("OIDC login is not configured.", { status: 503 });
  if (request.headers.get("origin") !== settings.origin) {
    return new NextResponse("Forbidden", { status: 403 });
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
