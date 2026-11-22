import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import { NextRequest } from "next/server";

import { GET as callback } from "../app/auth/callback/route.ts";
import { GET as login } from "../app/auth/login/route.ts";
import { SESSION_COOKIE, sealCookie } from "./oidc-session.ts";

function configureOidc(): string {
  const origin = "http://127.0.0.1:3001";
  process.env.EVIDENCEOS_SECURITY_MODE = "oidc";
  process.env.EVIDENCEOS_APP_ENV = "test";
  process.env.EVIDENCEOS_OIDC_ISSUER = "https://idp.example/tenant";
  process.env.EVIDENCEOS_OIDC_AUDIENCE = "evidenceos-api";
  process.env.EVIDENCEOS_OIDC_WEB_CLIENT_ID = "web-client";
  process.env.EVIDENCEOS_OIDC_WEB_CLIENT_SECRET = "very-strong-provider-client-secret";
  process.env.EVIDENCEOS_WEB_ORIGIN = origin;
  process.env.EVIDENCEOS_WEB_SESSION_KEY = randomBytes(32).toString("base64url");
  return origin;
}

function activeCookie(): string {
  const encrypted = sealCookie(SESSION_COOKIE, {
    accessToken: "access-token-kept-confidential",
    expiresAt: Math.floor(Date.now() / 1000) + 300,
  });
  return SESSION_COOKIE + "=" + encrypted;
}

test("unbound callback preserves an existing authenticated browser session", async () => {
  const origin = configureOidc();
  const response = await callback(new NextRequest(origin + "/auth/callback", {
    headers: { cookie: activeCookie() },
  }));
  assert.equal(response.status, 303);
  assert.equal(response.headers.get("location"), origin + "/");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.ok(!response.headers.get("set-cookie")?.includes(SESSION_COOKIE));
});

test("unbound anonymous callback returns to sign-in without creating a session", async () => {
  const origin = configureOidc();
  const response = await callback(new NextRequest(origin + "/auth/callback"));
  assert.equal(response.status, 303);
  assert.equal(response.headers.get("location"), origin + "/signin?error=auth");
  assert.ok(!response.headers.get("set-cookie")?.includes(SESSION_COOKIE));
});

test("public GET login route does not invalidate a signed-in session", async () => {
  const origin = configureOidc();
  const response = await login(new NextRequest(origin + "/auth/login", {
    headers: { cookie: activeCookie() },
  }));
  assert.equal(response.status, 303);
  assert.equal(response.headers.get("location"), origin + "/");
  assert.ok(!response.headers.get("set-cookie")?.includes(SESSION_COOKIE));
});
