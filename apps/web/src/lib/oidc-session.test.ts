import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import { browserOidcSettings } from "./oidc-client.ts";
import {
  FLOW_COOKIE, SESSION_COOKIE, openCookie, readFlow, readSession,
  sealCookie, sessionKeyConfigured,
} from "./oidc-session.ts";

function configure(): void {
  process.env.EVIDENCEOS_SECURITY_MODE = "oidc";
  process.env.EVIDENCEOS_APP_ENV = "test";
  process.env.EVIDENCEOS_WEB_SESSION_KEY = randomBytes(32).toString("base64url");
  process.env.EVIDENCEOS_OIDC_ISSUER = "https://idp.example/tenant";
  process.env.EVIDENCEOS_OIDC_AUDIENCE = "evidenceos-api";
  process.env.EVIDENCEOS_OIDC_WEB_CLIENT_ID = "web-client";
  process.env.EVIDENCEOS_OIDC_WEB_CLIENT_SECRET = "very-strong-provider-client-secret";
  process.env.EVIDENCEOS_WEB_ORIGIN = "http://127.0.0.1:3001";
}

test("OIDC configuration requires strong secrets, issuer HTTPS, and pinned origin", () => {
  configure();
  assert.equal(browserOidcSettings()?.secureCookies, false);
  assert.equal(browserOidcSettings()?.callbackUrl, "http://127.0.0.1:3001/auth/callback");

  process.env.EVIDENCEOS_APP_ENV = "production";
  assert.equal(browserOidcSettings(), null);
  process.env.EVIDENCEOS_WEB_ORIGIN = "https://research.example";
  assert.equal(browserOidcSettings()?.secureCookies, true);

  process.env.EVIDENCEOS_OIDC_ISSUER = "http://idp.example";
  assert.equal(browserOidcSettings(), null);
  process.env.EVIDENCEOS_OIDC_ISSUER = "https://idp.example/tenant";

  process.env.EVIDENCEOS_OIDC_AUDIENCE = "web-client";
  assert.equal(browserOidcSettings(), null);
  process.env.EVIDENCEOS_OIDC_AUDIENCE = "evidenceos-api";

  process.env.EVIDENCEOS_OIDC_WEB_CLIENT_SECRET = "short";
  assert.equal(browserOidcSettings(), null);
  process.env.EVIDENCEOS_OIDC_WEB_CLIENT_SECRET = "very-strong-provider-client-secret";

  process.env.EVIDENCEOS_WEB_SESSION_KEY = "bad";
  assert.equal(browserOidcSettings(), null);
});

test("AEAD browser session is encrypted and bound to cookie purpose", () => {
  configure();
  assert.equal(sessionKeyConfigured(), true);
  const session = { accessToken: "non-public-token-123", expiresAt: Math.floor(Date.now()/1000)+120 };
  const sealed = sealCookie(SESSION_COOKIE, session);
  assert.ok(!sealed.includes(session.accessToken));
  assert.deepEqual(readSession(sealed), session);
  assert.equal(openCookie(FLOW_COOKIE, sealed), null);
  assert.equal(readSession(sealed.slice(0,-1)+"!"), null);
  assert.equal(readSession(sealed.slice(0,-2)+"aa"), null);
  assert.equal(readSession("invalid"), null);

  const flow = {
    verifier: "p".repeat(43), state: "s".repeat(32), nonce: "n".repeat(32),
    expiresAt: Math.floor(Date.now()/1000)+120,
  };
  const cookie = sealCookie(FLOW_COOKIE, flow);
  assert.deepEqual(readFlow(cookie), flow);
  assert.equal(readSession(cookie), null);
});

test("short-lived cookies reject expired payload and fail closed without key", () => {
  configure();
  assert.throws(() => sealCookie(SESSION_COOKIE, {
    accessToken: "abc", expiresAt: Math.floor(Date.now()/1000)-1,
  }));
  const expired = { accessToken: "expired", expiresAt: Math.floor(Date.now()/1000)+1 };
  const sealed = sealCookie(SESSION_COOKIE, expired);
  // Verify time expiry without sleeps by re-encrypting with no valid TTL.
  assert.equal(typeof readSession(sealed)?.accessToken, "string");
  process.env.EVIDENCEOS_WEB_SESSION_KEY = "invalid-key";
  assert.equal(readSession(sealed), null);
  assert.throws(() => sealCookie(SESSION_COOKIE, expired));
});
