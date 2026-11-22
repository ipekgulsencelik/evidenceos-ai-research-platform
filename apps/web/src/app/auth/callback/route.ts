/** Complete PKCE exchange. OIDC token and API JWT are validated independently. */
import * as oidc from "openid-client";
import { NextRequest, NextResponse } from "next/server";

import { browserOidcSettings, discoverProvider } from "@/lib/oidc-client";
import {
  FLOW_COOKIE, SESSION_COOKIE, SESSION_MAX_SECONDS, cookieOptions, readFlow, readSession,
  sealCookie,
} from "@/lib/oidc-session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function unsuccessful(origin: string, secure: boolean, hasSession: boolean): NextResponse {
  // Public callbacks cannot sign out a user: a malformed or cross-site GET
  // must never clear the authenticated browser session.
  const destination = hasSession ? "/" : "/signin?error=auth";
  const response = NextResponse.redirect(new URL(destination, origin), { status: 303 });
  response.headers.set("Cache-Control", "no-store");
  response.cookies.set(FLOW_COOKIE, "", { ...cookieOptions(secure, 0), expires: new Date(0) });
  return response;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const settings = browserOidcSettings();
  if (!settings) return new NextResponse("OIDC login is not configured.", { status: 503 });

  const flow = readFlow(request.cookies.get(FLOW_COOKIE)?.value);
  const hasSession = readSession(request.cookies.get(SESSION_COOKIE)?.value) !== null;
  const callback = new URL(settings.callbackUrl);
  const incoming = request.nextUrl.searchParams;
  const state = incoming.getAll("state");
  const code = incoming.getAll("code");

  if (!flow || state.length !== 1 || code.length !== 1 ||
      state[0] !== flow.state || !code[0] || code[0].length > 4096 ||
      incoming.has("error") || incoming.has("response")) {
    return unsuccessful(settings.origin, settings.secureCookies, hasSession);
  }

  // Only configured origin and callback are sent to the SDK; Host is untrusted.
  callback.search = incoming.toString();
  try {
    const config = await discoverProvider(settings);
    const tokens = await oidc.authorizationCodeGrant(config, callback, {
      pkceCodeVerifier: flow.verifier,
      expectedState: flow.state,
      expectedNonce: flow.nonce,
      idTokenExpected: true,
    });
    if (!tokens.claims()?.sub || typeof tokens.access_token !== "string" ||
        tokens.access_token.length < 1 || tokens.access_token.length > 8192 ||
        tokens.token_type?.toLowerCase() !== "bearer" ||
        typeof tokens.expires_in !== "number" ||
        !Number.isFinite(tokens.expires_in) || tokens.expires_in < 60) {
      return unsuccessful(settings.origin, settings.secureCookies, hasSession);
    }

    // Do not create a browser session until the resource server has validated
    // signature, issuer, API audience and token expiry. No provider-only trust.
    const backendUrl = new URL(
      "/api/v1/projects", process.env.BACKEND_API_URL || "http://127.0.0.1:8001",
    );
    const check = await fetch(backendUrl, {
      method: "GET",
      headers: { Authorization: "Bearer " + tokens.access_token, Accept: "application/json" },
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(5000),
    });
    if (check.status !== 200) return unsuccessful(settings.origin, settings.secureCookies, hasSession);

    const lifetime = Math.min(SESSION_MAX_SECONDS, Math.floor(tokens.expires_in) - 30);
    if (lifetime < 30) return unsuccessful(settings.origin, settings.secureCookies, hasSession);
    const response = NextResponse.redirect(new URL("/", settings.origin), { status: 303 });
    response.headers.set("Cache-Control", "no-store");
    response.cookies.set(
      SESSION_COOKIE,
      sealCookie(SESSION_COOKIE, {
        accessToken: tokens.access_token,
        expiresAt: Math.floor(Date.now() / 1000) + lifetime,
      }),
      cookieOptions(settings.secureCookies, lifetime),
    );
    response.cookies.set(FLOW_COOKIE, "", {
      ...cookieOptions(settings.secureCookies, 0), expires: new Date(0),
    });
    return response;
  } catch {
    return unsuccessful(settings.origin, settings.secureCookies, hasSession);
  }
}
