import assert from "node:assert/strict";
import test from "node:test";

import { callBackend } from "./server-proxy.ts";

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
