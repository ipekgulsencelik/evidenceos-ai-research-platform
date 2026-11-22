import assert from "node:assert/strict";
import test from "node:test";

import {
  isAssignableRole, isMemberKey, isOidcIdentity, isProjectMember,
} from "./memberships.ts";

const key = "a".repeat(64);

test("only issuer-scoped 64-character lowercase hashes can be used as member keys", () => {
  assert.equal(isMemberKey(key), true);
  assert.equal(isMemberKey(key.toUpperCase()), false);
  assert.equal(isMemberKey("attacker@example.com"), false);
  assert.equal(isMemberKey("x".repeat(64)), false);
  assert.equal(isMemberKey(key + "/../"), false);
  assert.equal(isMemberKey(null), false);
});

test("UI forbids assigning owner and refuses malformed membership responses", () => {
  assert.equal(isAssignableRole("owner"), false);
  for (const role of ["editor", "reviewer", "viewer"]) {
    assert.equal(isAssignableRole(role), true);
    assert.equal(isProjectMember({ principal_key: key, role, created_at: "2026-11-22" }), true);
  }
  assert.equal(isAssignableRole("admin"), false);
  assert.equal(isProjectMember({ principal_key: key, role: "administrator" }), false);
  assert.equal(isProjectMember({ principal_key: "alice", role: "owner" }), false);
  assert.equal(isProjectMember({ principal_key: key, role: "owner", created_at: "now" }), true);
});

test("local and service operators are not treated as verified OIDC end users", () => {
  assert.equal(isOidcIdentity(null), false);
  assert.equal(isOidcIdentity({ principal_key: key, kind: "local_operator" }), false);
  assert.equal(isOidcIdentity({ principal_key: key, kind: "service_operator" }), false);
  assert.equal(isOidcIdentity({ principal_key: "invalid", kind: "oidc_user" }), false);
  assert.equal(isOidcIdentity({ principal_key: key, kind: "oidc_user" }), true);
});
