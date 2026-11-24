/** RP-Initiated Logout is offered only at the pinned OIDC issuer.
 * Never navigate the browser to arbitrary discovered origins, callback hosts,
 * or a URL provided by a request parameter.
 */
import * as oidc from "openid-client";

import type { BrowserOidcSettings } from "./oidc-client";

export function validatedEndSessionEndpoint(issuer: string, endpoint: unknown): URL | null {
  if (typeof endpoint !== "string" || !endpoint || endpoint.length > 2048) return null;
  try {
    const issuerUrl = new URL(issuer);
    const logout = new URL(endpoint);
    const prefix = issuerUrl.pathname.replace(/\/$/, "") + "/";
    if (issuerUrl.protocol !== "https:" || logout.protocol !== "https:" ||
        logout.origin !== issuerUrl.origin || !logout.pathname.startsWith(prefix) ||
        logout.username || logout.password || logout.search || logout.hash) return null;
    return logout;
  } catch {
    return null;
  }
}

export function providerLogoutUrl(
  configuration: oidc.Configuration,
  settings: BrowserOidcSettings,
): string | null {
  const metadata = configuration.serverMetadata();
  const endpoint = validatedEndSessionEndpoint(settings.issuer, metadata.end_session_endpoint);
  if (!endpoint) return null;

  // Standard OIDC RP-Initiated Logout with client_id. Keycloak may request
  // explicit confirmation without id_token_hint; no ID token is exposed to JS.
  // The return page is fixed in server settings, never read from a request.
  // Keycloak must separately register this exact logout return URI.
  const postLogoutRedirect = settings.origin + "/signed-out";
  const url = oidc.buildEndSessionUrl(configuration, {
    post_logout_redirect_uri: postLogoutRedirect,
  });
  if (url.protocol !== "https:" || url.origin !== endpoint.origin ||
      url.pathname !== endpoint.pathname || url.username || url.password ||
      url.hash || url.searchParams.getAll("client_id").length !== 1 ||
      url.searchParams.get("client_id") !== settings.clientId ||
      url.searchParams.getAll("post_logout_redirect_uri").length !== 1 ||
      url.searchParams.get("post_logout_redirect_uri") !== postLogoutRedirect ||
      url.searchParams.has("id_token_hint")) return null;
  return url.toString();
}
