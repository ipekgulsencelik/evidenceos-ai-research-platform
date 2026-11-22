/** Real-Redis regression; run in CI or with a local Redis test instance. */
import assert from "node:assert/strict";
import test from "node:test";
import { createClient } from "redis";

import { createSessionId, RedisSessionRegistry } from "./session-registry.ts";

test("Redis shares live session decisions across replicas and revokes immediately", async () => {
  const url = process.env.EVIDENCEOS_REDIS_TEST_URL || "redis://127.0.0.1:6379";
  const first = createClient({ url, socket: { connectTimeout: 2000 } });
  const second = createClient({ url, socket: { connectTimeout: 2000 } });
  first.on("error", () => {});
  second.on("error", () => {});
  await first.connect();
  try {
    await second.connect();
    const owner = new RedisSessionRegistry(first);
    const replica = new RedisSessionRegistry(second);
    const sid = createSessionId();
    try {
      assert.equal(await replica.isActive(sid), false);
      await owner.register(sid, 90);
      assert.equal(await replica.isActive(sid), true);
      await replica.revoke(sid);
      assert.equal(await owner.isActive(sid), false);
    } finally {
      await owner.revoke(sid);
    }
    const shortLived = createSessionId();
    await owner.register(shortLived, 1);
    assert.equal(await replica.isActive(shortLived), true);
    await new Promise((resolve) => setTimeout(resolve, 1250));
    assert.equal(await replica.isActive(shortLived), false);
  } finally {
    await Promise.allSettled([first.quit(), second.quit()]);
  }
});
