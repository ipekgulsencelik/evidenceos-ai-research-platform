/** Single-operator HTTP Basic protection for localhost-only protected mode.
 * This is not an identity provider, RBAC, or a secure public deployment.
 */
import { createHash, timingSafeEqual } from "node:crypto";

export function securityEnabled(
  appEnv: string | undefined,
  securityMode: string | undefined,
): boolean {
  return appEnv === "production" || securityMode === "service_token" || securityMode === "oidc";
}

export function validSecurityConfiguration(
  username: string | undefined,
  password: string | undefined,
  serviceToken: string | undefined,
): boolean {
  return Boolean(
    username && !username.includes(":") && username.length <= 128
    && password && password.length >= 20
    && serviceToken && serviceToken.length >= 32,
  );
}

function sameSecret(left: string, right: string): boolean {
  const lhs = createHash("sha256").update(left, "utf8").digest();
  const rhs = createHash("sha256").update(right, "utf8").digest();
  return timingSafeEqual(lhs, rhs);
}

export function isAuthorizedBasicHeader(
  authorization: string | null,
  username: string,
  password: string,
): boolean {
  if (!authorization || authorization.length > 4096
      || !authorization.startsWith("Basic ")) return false;
  const raw = authorization.slice("Basic ".length);
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(raw)) return false;
  const decoded = Buffer.from(raw, "base64").toString("utf8");
  const separator = decoded.indexOf(":");
  if (separator < 1) return false;
  const suppliedUser = decoded.slice(0, separator);
  const suppliedPassword = decoded.slice(separator + 1);
  return sameSecret(suppliedUser, username)
    && sameSecret(suppliedPassword, password);
}
