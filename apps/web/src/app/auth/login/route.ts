/** Begin server-side OAuth2 Authorization Code + PKCE. No credential enters JS. */
import * as oidc from "openid-client";
import { NextRequest, NextResponse } from "next/server";

import { browserOidcSettings, discoverProvider } from "@/lib/oidc-client";
import {
  FLOW_COOKIE, FLOW_MAX_SECONDS, SESSION_COOKIE, cookieOptions, readSession, sealCookie,
} from "@/lib/oidc-session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const settings = browserOidcSettings();
  if (!settings) return new NextResponse("OIDC login is not configured.", { status: 503 });
  // An attacker-controlled top-level navigation to this public GET endpoint
  // cannot invalidate an already authenticated user session.
  if (readSession(request.cookies.get(SESSION_COOKIE)?.value)) {
    const response = NextResponse.redirect(new URL("/", settings.origin), { status: 303 });
    response.headers.set("Cache-Control", "no-store");
    return response;
  }
  try {
    const config = await discoverProvider(settings);
    const verifier = oidc.randomPKCECodeVerifier();
    const challenge = await oidc.calculatePKCECodeChallenge(verifier);
    const state = oidc.randomState();
    const nonce = oidc.randomNonce();
    const redirectTo = oidc.buildAuthorizationUrl(config, {
      redirect_uri: settings.callbackUrl,
      scope: "openid",
      code_challenge: challenge,
      code_challenge_method: "S256",
      state,
      nonce,
    });

    const response = NextResponse.redirect(redirectTo, { status: 302 });
    response.headers.set("Cache-Control", "no-store");
    response.cookies.set(
      FLOW_COOKIE,
      sealCookie(FLOW_COOKIE, {
        verifier, state, nonce, expiresAt: Math.floor(Date.now() / 1000) + FLOW_MAX_SECONDS,
      }),
      cookieOptions(settings.secureCookies, FLOW_MAX_SECONDS),
    );
    return response;
  } catch {
    return new NextResponse("Identity provider is temporarily unavailable.", {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
  }
}
