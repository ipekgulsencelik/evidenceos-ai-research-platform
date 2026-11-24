import assert from "node:assert/strict";
import test from "node:test";

import { callBackend, gatewayResponseHeaders } from "./server-proxy.ts";

const original = globalThis.fetch;
const previousURL = process.env.BACKEND_API_URL;

test.after(() => {
  globalThis.fetch = original;
  if (previousURL === undefined) delete process.env.BACKEND_API_URL;
  else process.env.BACKEND_API_URL = previousURL;
});

test("returns upstream JSON while hiding upstream URL from clients", async () => {
  process.env.BACKEND_API_URL = "http://api:8000";
  let requested = "";
  globalThis.fetch = async (input) => {
    requested = String(input);
    return new Response(JSON.stringify([{ title: "Verified work" }]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const result = await callBackend("/api/v1/academic/works?query=research");
  assert.equal(requested, "http://api:8000/api/v1/academic/works?query=research");
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, [{ title: "Verified work" }]);
});

test("preserves expected error status and detail", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "OpenAlex API key is not configured" }), { status: 503 });
  const result = await callBackend("/api/v1/academic/works?query=research");
  assert.equal(result.status, 503);
  assert.deepEqual(result.body, { detail: "OpenAlex API key is not configured" });
});

test("maps network failures and invalid responses to 502", async () => {
  globalThis.fetch = async () => { throw new Error("network disconnected"); };
  assert.equal((await callBackend("/api/v1/academic/works")).status, 502);
  globalThis.fetch = async () => new Response("upstream html error", { status: 200 });
  assert.equal((await callBackend("/api/v1/academic/works")).status, 502);
});

test("forwards only validated Retry-After for rate limiting or temporary outages", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Too many requests" }), {
    status: 429,
    headers: { "Retry-After": "37", "X-Internal-Secret": "do-not-forward" },
  });
  const quota = await callBackend("/api/v1/projects");
  assert.equal(quota.status, 429);
  assert.equal(quota.retryAfterSeconds, 37);
  assert.deepEqual(gatewayResponseHeaders(quota), {
    "Cache-Control": "no-store",
    "Retry-After": "37",
  });

  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Temporarily unavailable" }), {
    status: 503, headers: { "Retry-After": "5" },
  });
  const unavailable = await callBackend("/api/v1/projects");
  assert.equal(unavailable.retryAfterSeconds, 5);
  assert.equal(gatewayResponseHeaders(unavailable)["Retry-After"], "5");
});

test("invalid or out-of-range retry hints are never reflected to browser clients", async () => {
  for (const bad of ["0", "-1", "86401", "12.5", "Mon, 01 Jan 2030 00:00:00 GMT", "999999"]) {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Too many requests" }), {
      status: 429, headers: { "Retry-After": bad },
    });
    const result = await callBackend("/api/v1/projects");
    assert.equal(gatewayResponseHeaders(result)["Retry-After"], undefined);
  }
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "OK" }), {
    status: 200, headers: { "Retry-After": "42" },
  });
  const success = await callBackend("/api/v1/projects");
  assert.equal(success.retryAfterSeconds, undefined);
  assert.equal(gatewayResponseHeaders(success)["Retry-After"], undefined);
});
