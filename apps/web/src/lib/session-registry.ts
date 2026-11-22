/** Centralized OIDC session allowlist, backed by Redis with bounded TTL.
 *
 * The encrypted HttpOnly browser cookie carries a random session identifier.
 * Authorization also requires a live server-side record; logout revokes it
 * atomically across Next.js replicas. Missing Redis never grants access.
 */
import { createHash, randomBytes } from "node:crypto";
import { createClient } from "redis";

import { SESSION_MAX_SECONDS } from "./oidc-session";

type SessionRedisCommands = Pick<ReturnType<typeof createClient>, "set" | "exists" | "del">;

const SESSION_ID_PATTERN = /^[A-Za-z0-9_-]{43}$/;
const SESSION_NAMESPACE = "evidenceos:session:v1:";

export function createSessionId(): string {
  return randomBytes(32).toString("base64url");
}

export function sessionRegistryKey(sessionId: string): string {
  if (!SESSION_ID_PATTERN.test(sessionId)) throw new Error("Invalid session ID");
  // Never persist or log the session bearer identifier as a Redis key.
  return SESSION_NAMESPACE + createHash("sha256").update(sessionId).digest("hex");
}

export class RedisSessionRegistry {
  constructor(private readonly redis: SessionRedisCommands) {}

  async register(sessionId: string, ttlSeconds: number): Promise<void> {
    if (!Number.isInteger(ttlSeconds) || ttlSeconds < 1 || ttlSeconds > SESSION_MAX_SECONDS) {
      throw new Error("Invalid session TTL");
    }
    // NX prevents accidental replacement if a random ID somehow collided.
    const result = await this.redis.set(sessionRegistryKey(sessionId), "1", {
      EX: ttlSeconds, NX: true,
    });
    if (result !== "OK") throw new Error("Session ID collision");
  }

  async isActive(sessionId: string): Promise<boolean> {
    return (await this.redis.exists(sessionRegistryKey(sessionId))) === 1;
  }

  async revoke(sessionId: string): Promise<void> {
    // Deletion takes effect for every replica. A missing record is idempotent.
    await this.redis.del(sessionRegistryKey(sessionId));
  }
}

/** Reject insecure/missing Redis configuration before starting OIDC login. */
export function sessionRegistryConfigured(): boolean {
  const url = process.env.EVIDENCEOS_SESSION_REDIS_URL || "";
  const password = process.env.EVIDENCEOS_SESSION_REDIS_PASSWORD || "";
  if (password.length < 32 || password.length > 512) return false;
  try {
    const parsed = new URL(url);
    return ["redis:", "rediss:"].includes(parsed.protocol) &&
      Boolean(parsed.hostname) && !parsed.username && !parsed.password &&
      !parsed.search && !parsed.hash && ["", "/"].includes(parsed.pathname) &&
      url.length <= 2048 &&
      !(process.env.EVIDENCEOS_APP_ENV === "production" && parsed.protocol !== "rediss:");
  } catch {
    return false;
  }
}

/** Keep retrying with a bounded delay. With disableOfflineQueue enabled,
 * individual authorization commands fail closed while Redis is offline,
 * but an eventually recovered service reconnects without a process restart.
 */
export function sessionReconnectDelay(retries: number): number {
  return Math.min(250 * 2 ** Math.min(Math.max(retries, 0), 5), 8000);
}

let registryPromise: Promise<RedisSessionRegistry> | undefined;
let registryClient: ReturnType<typeof createClient> | undefined;

/** Reuse the connection across requests; missing/failed storage fails closed. */
export async function getSessionRegistry(): Promise<RedisSessionRegistry> {
  const url = process.env.EVIDENCEOS_SESSION_REDIS_URL || "";
  const password = process.env.EVIDENCEOS_SESSION_REDIS_PASSWORD || "";
  if (process.env.EVIDENCEOS_SECURITY_MODE !== "oidc" || !sessionRegistryConfigured()) {
    throw new Error("Central OIDC session registry is not configured");
  }

  // A socket which was explicitly/permanently closed cannot reconnect.
  // Drop the cached instance so the next request can establish a new one.
  if (registryClient && !registryClient.isOpen) {
    registryPromise = undefined;
    registryClient = undefined;
  }
  if (!registryPromise) {
    registryPromise = (async () => {
      const client = createClient({
        url,
        password,
        disableOfflineQueue: true,
        socket: {
          connectTimeout: 1500,
          reconnectStrategy: sessionReconnectDelay,
        },
      });
      // Redis requires an error listener; requests surface operation errors.
      client.on("error", () => {});
      await client.connect();
      registryClient = client;
      return new RedisSessionRegistry(client);
    })().catch((cause: unknown) => {
      registryPromise = undefined;
      registryClient = undefined;
      throw cause;
    });
  }
  return registryPromise;
}
