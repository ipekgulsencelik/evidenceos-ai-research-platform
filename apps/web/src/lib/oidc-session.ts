/** Server-only, authenticated encryption for short-lived OIDC browser cookies.
 * An encrypted client-side session is NOT centrally revocable. Expiry is capped;
 * refresh tokens are never stored or returned to the browser.
 */
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

export const SESSION_COOKIE = "eos_session";
export const FLOW_COOKIE = "eos_oauth_flow";
export const SESSION_MAX_SECONDS = 600;
export const FLOW_MAX_SECONDS = 300;

export interface BrowserSession {
  accessToken: string;
  expiresAt: number;
}

export interface OAuthFlow {
  verifier: string;
  state: string;
  nonce: string;
  expiresAt: number;
}

export function cookieOptions(secure: boolean, maxAge: number) {
  return {
    httpOnly: true as const,
    secure,
    sameSite: "lax" as const,
    path: "/",
    maxAge,
    priority: "high" as const,
  };
}

function key(): Buffer | null {
  const secret = process.env.EVIDENCEOS_WEB_SESSION_KEY;
  if (!secret || !/^[A-Za-z0-9_-]{43}$/.test(secret)) return null;
  const decoded = Buffer.from(secret, "base64url");
  return decoded.length === 32 ? decoded : null;
}

export function sessionKeyConfigured(): boolean {
  return key() !== null;
}

export function sealCookie(name: string, value: BrowserSession | OAuthFlow): string {
  const aesKey = key();
  if (!aesKey) throw new Error("OIDC session key is not configured");
  if (!Number.isSafeInteger(value.expiresAt) || value.expiresAt <= Date.now() / 1000) {
    throw new Error("Invalid session expiry");
  }
  const json = Buffer.from(JSON.stringify(value), "utf8");
  if (json.length > 3000) throw new Error("OIDC cookie exceeds safe length");
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", aesKey, iv);
  cipher.setAAD(Buffer.from("evidenceos:" + name + ":v1"));
  const encrypted = Buffer.concat([cipher.update(json), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), encrypted]).toString("base64url");
}

export function openCookie<T>(name: string, data: string | undefined): T | null {
  const aesKey = key();
  if (!aesKey || !data || data.length > 4096 || !/^[A-Za-z0-9_-]+$/.test(data)) return null;
  try {
    const bytes = Buffer.from(data, "base64url");
    if (bytes.length < 29) return null;
    const decipher = createDecipheriv("aes-256-gcm", aesKey, bytes.subarray(0, 12));
    decipher.setAAD(Buffer.from("evidenceos:" + name + ":v1"));
    decipher.setAuthTag(bytes.subarray(12, 28));
    const value: unknown = JSON.parse(
      Buffer.concat([decipher.update(bytes.subarray(28)), decipher.final()]).toString("utf8"),
    );
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const expiry = (value as Record<string, unknown>).expiresAt;
    if (typeof expiry !== "number" || !Number.isSafeInteger(expiry) ||
        expiry <= Math.floor(Date.now() / 1000)) return null;
    return value as T;
  } catch {
    return null;
  }
}

export function readSession(value: string | undefined): BrowserSession | null {
  const session = openCookie<BrowserSession>(SESSION_COOKIE, value);
  if (!session || typeof session.accessToken !== "string" ||
      session.accessToken.length < 1 || session.accessToken.length > 8192) return null;
  return session;
}

export function readFlow(value: string | undefined): OAuthFlow | null {
  const flow = openCookie<OAuthFlow>(FLOW_COOKIE, value);
  if (!flow || typeof flow.verifier !== "string" || typeof flow.state !== "string" ||
      typeof flow.nonce !== "string" || flow.verifier.length < 43 ||
      flow.state.length < 16 || flow.nonce.length < 16) return null;
  return flow;
}
