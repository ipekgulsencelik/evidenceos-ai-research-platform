import assert from "node:assert/strict";
import test from "node:test";

import * as oidc from "openid-client";

import { providerLogoutUrl, validatedEndSessionEndpoint } from "./provider-logout.ts";
import type { BrowserOidcSettings } from "./oidc-client.ts";

const issuer = "https://idp.localhost:8443/realms/evidenceos-staging";
const logout = issuer + "/protocol/openid-connect/logout";
const settings: BrowserOidcSettings = {
  issuer, clientId: "evidenceos-web-staging", clientSecret: "secret-not-exposed",
  origin: "http://127.0.0.1:3101", callbackUrl: "http://127.0.0.1:3101/auth/callback",
  apiAudience: "evidenceos-api-staging", secureCookies: false,
};

test("only a trusted HTTPS end-session endpoint under the exact issuer is accepted", () => {
  assert.equal(validatedEndSessionEndpoint(issuer, logout)?.href, logout);
  for (const endpoint of [
    null, "", "http://idp.localhost:8443/realms/evidenceos-staging/logout",
    "https://evil.example/logout", "https://idp.localhost.evil.example/logout",
    "https://idp.localhost:8443/realms/other/logout",
    "https://idp.localhost:8443/realms/evidenceos-staging-evil/logout",
    "https://user@idp.localhost:8443/realms/evidenceos-staging/logout",
    logout + "?redirect=https://evil.example", logout + "#fragment",
    "//evil.example/logout", "/logout", "javascript:alert(1)",
  ]) {
    assert.equal(validatedEndSessionEndpoint(issuer, endpoint), null, String(endpoint));
  }
});

test("openid-client builds the standard client-id bound logout URL", () => {
  const config = new oidc.Configuration({
    issuer, authorization_endpoint: issuer + "/protocol/openid-connect/auth",
    token_endpoint: issuer + "/protocol/openid-connect/token",
    end_session_endpoint: logout,
  }, settings.clientId);
  const target = providerLogoutUrl(config, settings);
  assert.ok(target);
  const url = new URL(target);
  assert.equal(url.origin, "https://idp.localhost:8443");
  assert.equal(url.pathname, "/realms/evidenceos-staging/protocol/openid-connect/logout");
  assert.equal(url.searchParams.get("client_id"), settings.clientId);
  assert.equal(url.searchParams.has("id_token_hint"), false);
  assert.equal(url.searchParams.get("post_logout_redirect_uri"), settings.origin + "/signed-out");
  assert.deepEqual(url.searchParams.getAll("post_logout_redirect_uri"), [
    settings.origin + "/signed-out",
  ]);
});

test("providers without an end-session endpoint do not prevent local logout", () => {
  const config = new oidc.Configuration({
    issuer, authorization_endpoint: issuer + "/auth", token_endpoint: issuer + "/token",
  }, settings.clientId);
  assert.equal(providerLogoutUrl(config, settings), null);
});
