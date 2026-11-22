/** OIDC provider configuration is pinned server-side; never derive endpoints
 * or the redirect origin from incoming Host / X-Forwarded-* request headers.
 */
import * as oidc from "openid-client";
import { sessionKeyConfigured } from "./oidc-session";
import { sessionRegistryConfigured } from "./session-registry";

export interface BrowserOidcSettings {
  issuer: string;
  clientId: string;
  clientSecret: string;
  origin: string;
  callbackUrl: string;
  apiAudience: string;
  secureCookies: boolean;
}

export function browserOidcSettings(): BrowserOidcSettings | null {
  if (process.env.EVIDENCEOS_SECURITY_MODE !== "oidc") return null;
  const issuer = process.env.EVIDENCEOS_OIDC_ISSUER || "";
  const clientId = process.env.EVIDENCEOS_OIDC_WEB_CLIENT_ID || "";
  const clientSecret = process.env.EVIDENCEOS_OIDC_WEB_CLIENT_SECRET || "";
  const origin = process.env.EVIDENCEOS_WEB_ORIGIN || "";
  const apiAudience = process.env.EVIDENCEOS_OIDC_AUDIENCE || "";

  if (!sessionKeyConfigured() || !sessionRegistryConfigured() || !issuer || clientId.length < 1 ||
      clientId.length > 256 || clientSecret.length < 20 ||
      clientSecret.length > 2048 || !apiAudience || apiAudience.length > 256 ||
      apiAudience === clientId) return null;
  try {
    const server = new URL(issuer);
    const browser = new URL(origin);
    const local = browser.hostname === "localhost" || browser.hostname === "127.0.0.1";
    const insecureLocal = browser.protocol === "http:" &&
      local && process.env.EVIDENCEOS_APP_ENV !== "production";
    if (server.protocol !== "https:" || server.username || server.password ||
        server.search || server.hash || issuer.length > 2048 ||
        !((browser.protocol === "https:") || insecureLocal) ||
        browser.username || browser.password || browser.pathname !== "/" ||
        browser.search || browser.hash || browser.origin !== origin) return null;

    return {
      issuer,
      clientId,
      clientSecret,
      origin,
      callbackUrl: origin + "/auth/callback",
      apiAudience,
      secureCookies: !insecureLocal,
    };
  } catch {
    return null;
  }
}

export async function discoverProvider(settings: BrowserOidcSettings): Promise<oidc.Configuration> {
  // The provider SDK checks issuer identity and PKCE/ID token correctness.
  return oidc.discovery(
    new URL(settings.issuer),
    settings.clientId,
    settings.clientSecret,
    oidc.ClientSecretPost(settings.clientSecret),
    { timeout: 5000 },
  );
}
