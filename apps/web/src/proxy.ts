/** Next.js 16 HTTP boundary: Basic localhost mode or verified OIDC session. */
import { NextRequest, NextResponse } from "next/server";

import { browserOidcSettings } from "./lib/oidc-client";
import { SESSION_COOKIE, readSession } from "./lib/oidc-session";
import { getSessionRegistry } from "./lib/session-registry";
import {
  isAuthorizedBasicHeader, securityEnabled, validSecurityConfiguration,
} from "./lib/security";

export async function proxy(request: NextRequest): Promise<NextResponse> {
  if (process.env.EVIDENCEOS_SECURITY_MODE === "oidc") {
    const settings = browserOidcSettings();
    if (!settings) return new NextResponse("OIDC browser sign-in is not configured.", {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
    const path = request.nextUrl.pathname;
    const publicRoutes = ["/signin", "/auth/login", "/auth/callback", "/auth/health"];
    if (publicRoutes.includes(path)) return NextResponse.next();

    // Logout is POST-only and checks Origin in its route handler.
    if (path === "/auth/logout") return NextResponse.next();

    const session = readSession(request.cookies.get(SESSION_COOKIE)?.value);
    let authorized = false;
    if (session) {
      try {
        authorized = await (await getSessionRegistry()).isActive(session.sid);
      } catch {
        return new NextResponse("Session verification temporarily unavailable.", {
          status: 503, headers: { "Cache-Control": "no-store", "Retry-After": "5" },
        });
      }
    }
    if (!authorized) {
      if (path.startsWith("/api/")) return NextResponse.json(
        { detail: "Authentication required" },
        { status: 401, headers: { "Cache-Control": "no-store" } },
      );
      const response = NextResponse.redirect(new URL("/signin", settings.origin));
      response.headers.set("Cache-Control", "no-store");
      return response;
    }

    // SameSite cookies alone do not protect against all cross-origin or
    // same-site attackers. Mutations require a same-origin browser request.
    if (path.startsWith("/api/") && !["GET", "HEAD", "OPTIONS"].includes(request.method) &&
        request.headers.get("origin") !== settings.origin) {
      return NextResponse.json(
        { detail: "Cross-origin mutation denied" },
        { status: 403, headers: { "Cache-Control": "no-store" } },
      );
    }
    const response = NextResponse.next();
    response.headers.set("Cache-Control", "no-store");
    response.headers.set("X-Frame-Options", "DENY");
    response.headers.set("Referrer-Policy", "no-referrer");
    response.headers.set("X-Content-Type-Options", "nosniff");
    return response;
  }

  if (!securityEnabled(process.env.EVIDENCEOS_APP_ENV, process.env.EVIDENCEOS_SECURITY_MODE)) {
    return NextResponse.next();
  }

  const username = process.env.EVIDENCEOS_WEB_USERNAME;
  const password = process.env.EVIDENCEOS_WEB_PASSWORD;
  const serviceToken = process.env.EVIDENCEOS_API_SERVICE_TOKEN;
  if (!validSecurityConfiguration(username, password, serviceToken)) {
    return new NextResponse("Protected workspace is not configured.", {
      status: 503,
      headers: { "Cache-Control": "no-store" },
    });
  }

  // Legacy localhost Basic mode remains unchanged. Never use over public HTTP.
  if (!isAuthorizedBasicHeader(request.headers.get("authorization"), username!, password!)) {
    return new NextResponse("Authentication required.", {
      status: 401,
      headers: {
        "WWW-Authenticate": 'Basic realm="EvidenceOS", charset="UTF-8"',
        "Cache-Control": "no-store",
      },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
