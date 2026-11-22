import assert from "node:assert/strict";
import test from "node:test";

import {
  isAuthorizedBasicHeader, securityEnabled, validSecurityConfiguration,
} from "./security.ts";

const username = "research-admin";
const password = "a-long-local-only-passphrase";
const token = "0123456789abcdefghijklmnopqrstuvwxyz-0123456789";

function basic(user: string, pass: string): string {
  return "Basic " + Buffer.from(user + ":" + pass, "utf8").toString("base64");
}

test("local mode retains existing workflow but production never silently disables security", () => {
  assert.equal(securityEnabled("development", "local"), false);
  assert.equal(securityEnabled("test", "local"), false);
  assert.equal(securityEnabled("development", "service_token"), true);
  assert.equal(securityEnabled("development", "oidc"), true);
  assert.equal(securityEnabled("production", "local"), true);
});

test("protected mode fails closed without strong server-side secrets", () => {
  assert.equal(validSecurityConfiguration(username, password, token), true);
  assert.equal(validSecurityConfiguration(username, "short", token), false);
  assert.equal(validSecurityConfiguration(username, password, "short"), false);
  assert.equal(validSecurityConfiguration(undefined, password, token), false);
  assert.equal(validSecurityConfiguration("invalid:name", password, token), false);
});

test("browser basic credentials must match exactly", () => {
  assert.equal(isAuthorizedBasicHeader(basic(username, password), username, password), true);
  assert.equal(isAuthorizedBasicHeader(basic(username, "wrong"), username, password), false);
  assert.equal(isAuthorizedBasicHeader(basic("different", password), username, password), false);
  assert.equal(isAuthorizedBasicHeader(null, username, password), false);
  assert.equal(isAuthorizedBasicHeader("Bearer " + token, username, password), false);
  assert.equal(isAuthorizedBasicHeader("Basic %%%", username, password), false);
  assert.equal(isAuthorizedBasicHeader("Basic " + "A".repeat(5000), username, password), false);
  assert.equal(isAuthorizedBasicHeader("Basic " + Buffer.from("nocolon").toString("base64"),
    username, password), false);
  assert.equal(isAuthorizedBasicHeader(basic(username, "wrong:password"), username, password),
    false);
});
