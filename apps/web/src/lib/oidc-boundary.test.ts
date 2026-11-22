import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import { NextRequest } from "next/server";

import { POST as logout } from "../app/auth/logout/route.ts";
import { proxy } from "../proxy.ts";

function configure() {
  const origin = "http://127.0.0.1:3001";
  process.env.EVIDENCEOS_SECURITY_MODE = "oidc";
  process.env.EVIDENCEOS_APP_ENV = "test";
  process.env.EVIDENCEOS_WEB_SESSION_KEY = randomBytes(32).toString("base64url");
  process.env.EVIDENCEOS_WEB_ORIGIN = origin;
  process.env.EVIDENCEOS_OIDC_ISSUER = "https://idp.example/tenant";
  process.env.EVIDENCEOS_OIDC_AUDIENCE = "evidenceos-api";
  process.env.EVIDENCEOS_OIDC_WEB_CLIENT_ID = "web-client";
  process.env.EVIDENCEOS_OIDC_WEB_CLIENT_SECRET = "test-confidential-client-secret-strong";
  process.env.EVIDENCEOS_SESSION_REDIS_URL = "redis://127.0.0.1:1";
  process.env.EVIDENCEOS_SESSION_REDIS_PASSWORD = "test-only-long-secret-for-redis-12345";
  return origin;
}

test("anonymous OIDC browser navigation redirects, but APIs return 401", async () => {
  const origin = configure();
  const page = await proxy(new NextRequest(origin + "/projects"));
  assert.equal(page.status, 307);
  assert.equal(page.headers.get("location"), origin + "/signin");
  assert.equal(page.headers.get("cache-control"), "no-store");

  const api = await proxy(new NextRequest(origin + "/api/identity"));
  assert.equal(api.status, 401);
  assert.equal(api.headers.get("cache-control"), "no-store");

  const free = await proxy(new NextRequest(origin + "/signin"));
  assert.equal(free.status, 200);
});

test("forged origin cannot invoke the public POST-only logout endpoint", async () => {
  const origin = configure();
  const forged = await logout(new NextRequest(origin + "/auth/logout", {
    method: "POST",
    headers: { Origin: "https://attacker.invalid" },
  }));
  assert.equal(forged.status, 403);
  assert.equal(forged.headers.get("set-cookie"), null);
});

test("incomplete OIDC secret configuration rejects protected navigation", async () => {
  const origin = configure();
  delete process.env.EVIDENCEOS_OIDC_WEB_CLIENT_SECRET;
  const response = await proxy(new NextRequest(origin + "/projects"));
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("cache-control"), "no-store");
});
