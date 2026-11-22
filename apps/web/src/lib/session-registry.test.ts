import assert from "node:assert/strict";
import test from "node:test";

import {
  createSessionId, RedisSessionRegistry, sessionReconnectDelay, sessionReconnectStrategy,
  sessionRegistryConfigured, sessionRegistryKey,
} from "./session-registry.ts";

type Store = ConstructorParameters<typeof RedisSessionRegistry>[0];

function fakeStorage() {
  const data = new Map<string, string>();
  const mock = {
    async set(key: string, value: string, options: { NX: true; EX: number }) {
      if (!options.EX || data.has(key)) return null;
      data.set(key, value);
      return "OK";
    },
    async exists(key: string) { return data.has(key) ? 1 : 0; },
    async del(key: string) { return Number(data.delete(key)); },
  };
  return { data, registry: new RedisSessionRegistry(mock as unknown as Store) };
}

test("session identifiers are random and Redis keys never expose them", () => {
  const first = createSessionId();
  const second = createSessionId();
  assert.notEqual(first, second);
  assert.match(first, /^[A-Za-z0-9_-]{43}$/);
  assert.match(sessionRegistryKey(first), /^evidenceos:session:v1:[a-f0-9]{64}$/);
  assert.ok(!sessionRegistryKey(first).includes(first));
  assert.throws(() => sessionRegistryKey("not-a-session"), /Invalid session ID/);
});

test("registration is single-use, and revocation rejects copied cookies", async () => {
  const { registry } = fakeStorage();
  const sid = createSessionId();
  assert.equal(await registry.isActive(sid), false);
  await registry.register(sid, 120);
  assert.equal(await registry.isActive(sid), true);
  await assert.rejects(registry.register(sid, 120), /collision/);
  await registry.revoke(sid);
  assert.equal(await registry.isActive(sid), false);
  await registry.revoke(sid); // idempotent
  assert.equal(await registry.isActive(sid), false);
});

test("invalid TTL and storage outages never allow a session", async () => {
  const sid = createSessionId();
  const { registry } = fakeStorage();
  await assert.rejects(registry.register(sid, 0), /Invalid session TTL/);
  await assert.rejects(registry.register(sid, 601), /Invalid session TTL/);
  await assert.rejects(registry.register(sid, 1.2), /Invalid session TTL/);
  const unavailable = new RedisSessionRegistry({
    exists: async () => { throw new Error("redis offline"); },
    set: async () => { throw new Error("redis offline"); },
    del: async () => { throw new Error("redis offline"); },
  } as unknown as Store);
  await assert.rejects(unavailable.isActive(sid), /redis offline/);
  await assert.rejects(unavailable.register(sid, 100), /redis offline/);
  await assert.rejects(unavailable.revoke(sid), /redis offline/);
});

test("OIDC store requires strong password and secure production transport", () => {
  const oldUrl = process.env.EVIDENCEOS_SESSION_REDIS_URL;
  const oldPassword = process.env.EVIDENCEOS_SESSION_REDIS_PASSWORD;
  const oldEnv = process.env.EVIDENCEOS_APP_ENV;
  try {
    process.env.EVIDENCEOS_APP_ENV = "development";
    process.env.EVIDENCEOS_SESSION_REDIS_URL = "redis://redis:6379";
    process.env.EVIDENCEOS_SESSION_REDIS_PASSWORD = "strong-local-redis-password-0123456789";
    assert.equal(sessionRegistryConfigured(), true);
    process.env.EVIDENCEOS_APP_ENV = "production";
    assert.equal(sessionRegistryConfigured(), false);
    process.env.EVIDENCEOS_SESSION_REDIS_URL = "rediss://redis.example:6379";
    assert.equal(sessionRegistryConfigured(), true);
    process.env.EVIDENCEOS_SESSION_REDIS_PASSWORD = "weak";
    assert.equal(sessionRegistryConfigured(), false);
  } finally {
    if (oldUrl === undefined) delete process.env.EVIDENCEOS_SESSION_REDIS_URL;
    else process.env.EVIDENCEOS_SESSION_REDIS_URL = oldUrl;
    if (oldPassword === undefined) delete process.env.EVIDENCEOS_SESSION_REDIS_PASSWORD;
    else process.env.EVIDENCEOS_SESSION_REDIS_PASSWORD = oldPassword;
    if (oldEnv === undefined) delete process.env.EVIDENCEOS_APP_ENV;
    else process.env.EVIDENCEOS_APP_ENV = oldEnv;
  }
});

test("reconnect delay never abandons recovery, even after long Redis outages", () => {
  assert.equal(sessionReconnectDelay(0), 250);
  assert.equal(sessionReconnectDelay(1), 500);
  assert.equal(sessionReconnectDelay(2), 1000);
  assert.equal(sessionReconnectDelay(3), 2000);
  assert.equal(sessionReconnectDelay(4), 4000);
  assert.equal(sessionReconnectDelay(5), 8000);
  assert.equal(sessionReconnectDelay(1000), 8000);
  assert.equal(typeof sessionReconnectDelay(1000), "number");
});

test("initial Redis connection fails promptly, but established sessions keep retrying", () => {
  assert.equal(sessionReconnectStrategy(0, false), 250);
  assert.equal(sessionReconnectStrategy(2, false), 1000);
  assert.ok(sessionReconnectStrategy(3, false) instanceof Error);
  assert.ok(sessionReconnectStrategy(100, false) instanceof Error);
  assert.equal(sessionReconnectStrategy(3, true), 2000);
  assert.equal(sessionReconnectStrategy(100, true), 8000);
});
