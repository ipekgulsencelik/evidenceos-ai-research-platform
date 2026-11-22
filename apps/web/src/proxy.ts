/** Next.js 16 request boundary for the protected local single-operator workspace.
 *
 * Never use HTTP Basic over unencrypted public internet connections.
 * Use an external identity provider with TLS for any deployed multi-user system.
 */
import { NextRequest, NextResponse } from "next/server";

import {
  isAuthorizedBasicHeader, securityEnabled, validSecurityConfiguration,
} from "./lib/security";

export function proxy(request: NextRequest): NextResponse {
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

  // Credentials are kept on the server; the browser receives only a Basic challenge.
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
