/** Real-Redis regression; run in CI or with a local Redis test instance. */
import assert from "node:assert/strict";
import { createConnection, createServer, type Server, type Socket } from "node:net";
import test from "node:test";
import { createClient } from "redis";

import {
  createSessionId, RedisSessionRegistry, sessionReconnectDelay,
} from "./session-registry.ts";

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


interface TcpProxy {
  server: Server;
  sockets: Set<Socket>;
  port: number;
}

/** The proxy creates a deterministic network outage without killing CI Redis. */
async function startTcpProxy(port = 0): Promise<TcpProxy> {
  const sockets = new Set<Socket>();
  const server = createServer((browserSocket) => {
    const redisSocket = createConnection({ host: "127.0.0.1", port: 6379 });
    for (const socket of [browserSocket, redisSocket]) {
      sockets.add(socket);
      socket.on("close", () => { sockets.delete(socket); });
      socket.on("error", () => {});
    }
    browserSocket.pipe(redisSocket);
    redisSocket.pipe(browserSocket);
    browserSocket.on("close", () => redisSocket.destroy());
    redisSocket.on("close", () => browserSocket.destroy());
  });
  await new Promise<void>((resolve, reject) => {
    const onError = (error: Error) => reject(error);
    server.once("error", onError);
    server.listen(port, "127.0.0.1", () => {
      server.off("error", onError);
      resolve();
    });
  });
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("No proxy port assigned");
  return { server, sockets, port: address.port };
}

async function stopTcpProxy(proxy: TcpProxy): Promise<void> {
  for (const socket of proxy.sockets) socket.destroy();
  await new Promise<void>((resolve, reject) =>
    proxy.server.close((error) => error ? reject(error) : resolve()));
}

test("a live registry fails closed during a long Redis outage and recovers without restart", async () => {
  let proxy = await startTcpProxy();
  const port = proxy.port;
  const client = createClient({
    url: "redis://127.0.0.1:" + port,
    disableOfflineQueue: true,
    socket: { connectTimeout: 300, reconnectStrategy: sessionReconnectDelay },
  });
  client.on("error", () => {});
  try {
    await client.connect();
    const registry = new RedisSessionRegistry(client);
    const sid = createSessionId();
    await registry.register(sid, 90);
    assert.equal(await registry.isActive(sid), true);

    await stopTcpProxy(proxy);
    // This exceeds the former three-attempt retry limit.
    await new Promise((resolve) => setTimeout(resolve, 2700));
    assert.equal(client.isReady, false);
    await assert.rejects(registry.isActive(sid));

    proxy = await startTcpProxy(port);
    const deadline = Date.now() + 15000;
    let recovered = false;
    while (Date.now() < deadline) {
      try {
        if (await registry.isActive(sid)) {
          recovered = true;
          break;
        }
      } catch {
        // The connection remains unavailable; no stale authorization is allowed.
      }
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    assert.equal(recovered, true, "Registry must recover without a Next.js restart");
    await registry.revoke(sid);
    assert.equal(await registry.isActive(sid), false);
  } finally {
    client.destroy();
    if (proxy.server.listening) await stopTcpProxy(proxy);
  }
});
