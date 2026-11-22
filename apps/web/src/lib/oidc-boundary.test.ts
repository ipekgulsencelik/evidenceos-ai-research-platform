import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import { NextRequest } from "next/server";

import { POST as logout } from "../app/auth/logout/route.ts";
import { LOGOUT_REQUEST_HEADER } from "./logout-request.ts";
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

test("logout rejects forged Origin even with a custom header and fake same-origin metadata", async () => {
  const origin = configure();
  for (const suppliedOrigin of ["https://attacker.invalid", "null", "http://localhost:3001"]) {
    const forged = await logout(new NextRequest(origin + "/auth/logout", {
      method: "POST",
      headers: {
        Origin: suppliedOrigin,
        [LOGOUT_REQUEST_HEADER]: "1",
        "Sec-Fetch-Site": "same-origin",
      },
    }));
    assert.equal(forged.status, 403);
    assert.equal(forged.headers.get("set-cookie"), null);
  }
});

test("logout rejects cross-origin and headerless form submissions even without a session", async () => {
  const origin = configure();
  for (const headers of [
    { Origin: origin },
    { "Sec-Fetch-Site": "cross-site", [LOGOUT_REQUEST_HEADER]: "1" },
    { "Sec-Fetch-Site": "same-site", [LOGOUT_REQUEST_HEADER]: "1" },
    { [LOGOUT_REQUEST_HEADER]: "1" },
  ]) {
    const forbidden = await logout(new NextRequest(origin + "/auth/logout", {
      method: "POST", headers,
    }));
    assert.equal(forbidden.status, 403);
    assert.equal(forbidden.headers.get("set-cookie"), null);
  }
});

test("same-origin browser fetch logs out and clears cookies even without a session", async () => {
  const origin = configure();
  const response = await logout(new NextRequest(origin + "/auth/logout", {
    method: "POST",
    headers: { Origin: origin, [LOGOUT_REQUEST_HEADER]: "1" },
  }));
  assert.equal(response.status, 303);
  assert.equal(response.headers.get("location"), origin + "/signin");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.match(response.headers.get("set-cookie") || "", /eos_session=;/);
});

test("browsers omitting Origin can logout only with same-origin Fetch Metadata", async () => {
  const origin = configure();
  const response = await logout(new NextRequest(origin + "/auth/logout", {
    method: "POST",
    headers: { "Sec-Fetch-Site": "same-origin", [LOGOUT_REQUEST_HEADER]: "1" },
  }));
  assert.equal(response.status, 303);
  assert.equal(response.headers.get("location"), origin + "/signin");
});

test("incomplete OIDC secret configuration rejects protected navigation", async () => {
  const origin = configure();
  delete process.env.EVIDENCEOS_OIDC_WEB_CLIENT_SECRET;
  const response = await proxy(new NextRequest(origin + "/projects"));
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("cache-control"), "no-store");
});
