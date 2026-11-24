import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import { NextRequest, NextResponse } from "next/server";

import { proxy } from "../proxy.ts";
import { contentSecurityPolicy, freshCspNonce, secureResponse } from "./http-security.ts";

function withEnvironment(values: Record<string, string>, run: () => Promise<void>): Promise<void> {
  const original = new Map(Object.keys(values).map((key) => [key, process.env[key]]));
  for (const [key, value] of Object.entries(values)) process.env[key] = value;
  return run().finally(() => {
    for (const [key, value] of original) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });
}

const staging = {
  EVIDENCEOS_APP_ENV: "test",
  EVIDENCEOS_SECURITY_MODE: "oidc",
  EVIDENCEOS_OIDC_ISSUER: "https://idp.example/tenant",
  EVIDENCEOS_OIDC_AUDIENCE: "evidenceos-api",
  EVIDENCEOS_OIDC_WEB_CLIENT_ID: "web-client",
  EVIDENCEOS_OIDC_WEB_CLIENT_SECRET: "strong-test-secret-for-confidential-client",
  EVIDENCEOS_WEB_ORIGIN: "http://127.0.0.1:3001",
  EVIDENCEOS_SESSION_REDIS_URL: "redis://127.0.0.1:6379",
  EVIDENCEOS_SESSION_REDIS_PASSWORD: "independent-redis-secret-longer-than-32-chars",
};

test("CSP nonces are fresh and never permit unsafe-inline scripts", () => {
  const first = freshCspNonce();
  const second = freshCspNonce();
  assert.match(first, /^[A-Za-z0-9+/]{22}==$/);
  assert.notEqual(first, second);
  const production = contentSecurityPolicy(first, false);
  // CSP base64 nonces may contain regex metacharacters such as '+'.
  assert.ok(production.includes("'nonce-" + first + "'"));
  assert.match(production, /script-src 'self' 'nonce-[^']+' 'strict-dynamic'/);
  assert.ok(!production.includes("'unsafe-eval'"));
  assert.ok(!production.split("; ").find((s) => s.startsWith("script-src"))?.includes("'unsafe-inline'"));
  assert.ok(production.includes("frame-ancestors 'none'"));
  assert.ok(production.includes("object-src 'none'"));
  assert.ok(production.includes("style-src 'self' 'unsafe-inline'"));
  assert.ok(contentSecurityPolicy(first, true).includes("'unsafe-eval'"));
});

test("all web responses have security headers; HSTS is production-only", async () => {
  await withEnvironment({ EVIDENCEOS_APP_ENV: "test" }, async () => {
    const response = secureResponse(NextResponse.next(), freshCspNonce());
    assert.equal(response.headers.get("strict-transport-security"), null);
    assert.equal(response.headers.get("x-frame-options"), "DENY");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(response.headers.get("referrer-policy"), "no-referrer");
    assert.equal(response.headers.get("permissions-policy"), "camera=(), microphone=(), geolocation=()");
  });
  await withEnvironment({ EVIDENCEOS_APP_ENV: "production" }, async () => {
    const response = secureResponse(NextResponse.next(), freshCspNonce());
    assert.equal(response.headers.get("strict-transport-security"), "max-age=31536000");
    assert.ok(!response.headers.get("strict-transport-security")?.includes("includeSubDomains"));
  });
});

test("public OIDC pages receive nonce on request and response; untrusted incoming CSP is overwritten", async () => {
  await withEnvironment({
    ...staging,
    EVIDENCEOS_WEB_SESSION_KEY: randomBytes(32).toString("base64url"),
  }, async () => {
    const response = await proxy(new NextRequest("http://127.0.0.1:3001/signed-out", {
      headers: {
        "Content-Security-Policy": "script-src 'unsafe-inline'",
        "x-nonce": "injected-nonce",
      },
    }));
    const csp = response.headers.get("content-security-policy");
    assert.equal(response.status, 200);
    assert.ok(csp);
    const nonce = csp.match(/'nonce-([^']+)'/)?.[1];
    assert.ok(nonce);
    assert.notEqual(nonce, "injected-nonce");
    assert.equal(response.headers.get("x-middleware-request-content-security-policy"), csp);
    assert.equal(response.headers.get("x-middleware-request-x-nonce"), nonce);
    assert.equal(response.headers.get("strict-transport-security"), null);
  });
});

test("anonymous OIDC redirect carries no-store and security headers without trusting browser input", async () => {
  await withEnvironment({
    ...staging,
    EVIDENCEOS_WEB_SESSION_KEY: randomBytes(32).toString("base64url"),
  }, async () => {
    const response = await proxy(new NextRequest("http://127.0.0.1:3001/projects"));
    assert.equal(response.status, 307);
    assert.equal(response.headers.get("location"), "http://127.0.0.1:3001/signin");
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("x-frame-options"), "DENY");
    assert.match(response.headers.get("content-security-policy") || "", /script-src/);
  });
});

test("misconfigured production protection still responds with hardened headers", async () => {
  await withEnvironment({
    EVIDENCEOS_APP_ENV: "production",
    EVIDENCEOS_SECURITY_MODE: "service_token",
    EVIDENCEOS_WEB_USERNAME: "",
    EVIDENCEOS_WEB_PASSWORD: "",
    EVIDENCEOS_API_SERVICE_TOKEN: "",
  }, async () => {
    const response = await proxy(new NextRequest("https://research.example.invalid/"));
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("strict-transport-security"), "max-age=31536000");
    assert.match(response.headers.get("content-security-policy") || "", /frame-ancestors 'none'/);
  });
});
