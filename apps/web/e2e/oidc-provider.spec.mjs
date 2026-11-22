/** Real-browser E2E against an already-deployed disposable OIDC staging stack.
 *
 * This suite does NOT mock OIDC. The app must use a real provider issuing
 * JWT access tokens for its configured API audience. Keep all credentials in
 * GitHub Environment secrets; the test does not print or persist them.
 */
import { test, expect } from "@playwright/test";

const origin = process.env.EVIDENCEOS_E2E_ORIGIN;
const userA = process.env.EVIDENCEOS_E2E_USER_A;
const passwordA = process.env.EVIDENCEOS_E2E_PASSWORD_A;
const userB = process.env.EVIDENCEOS_E2E_USER_B;
const passwordB = process.env.EVIDENCEOS_E2E_PASSWORD_B;

function assertStagingConfiguration() {
  for (const [name, value] of Object.entries({
    EVIDENCEOS_E2E_ORIGIN: origin,
    EVIDENCEOS_E2E_USER_A: userA,
    EVIDENCEOS_E2E_PASSWORD_A: passwordA,
    EVIDENCEOS_E2E_USER_B: userB,
    EVIDENCEOS_E2E_PASSWORD_B: passwordB,
  })) {
    if (!value) throw new Error(name + " is required for the gated OIDC staging test.");
  }
  const url = new URL(origin);
  // HTTP is permitted ONLY for the pinned isolated loopback Docker staging
  // app. The actual Keycloak issuer remains HTTPS with a trusted certificate.
  const explicitLocal = process.env.EVIDENCEOS_E2E_ALLOW_LOCAL_HTTP === "1" &&
    origin === "http://127.0.0.1:3101";
  if ((!explicitLocal && url.protocol !== "https:") ||
      url.origin !== origin || url.pathname !== "/" ||
      url.search || url.hash || userA === userB) {
    throw new Error("Use an exact HTTPS staging origin or explicit 127.0.0.1 local test.");
  }
}

async function authenticate(context, username, password) {
  const page = await context.newPage();
  await page.goto(origin + "/signin");
  await expect(page.getByRole("link", { name: "Sign in securely" })).toBeVisible();
  await page.getByRole("link", { name: "Sign in securely" }).click();

  // Ordinary IdP login form; use two dedicated test identities without MFA.
  // Customize these selectors only for the organization's *test* provider.
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[type="password"]').fill(password);
  await page.locator('input[type="submit"], button[type="submit"]').first().click();

  await page.waitForURL((url) => url.origin === origin && url.pathname === "/", {
    timeout: 45000,
  });
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  const response = await context.request.get(origin + "/api/identity");
  expect(response.status()).toBe(200);
  const identity = await response.json();
  expect(identity).toMatchObject({ kind: "oidc_user" });
  expect(identity.principal_key).toMatch(/^[a-f0-9]{64}$/);
  return { page, key: identity.principal_key };
}

async function listProjects(context) {
  const response = await context.request.get(origin + "/api/projects");
  expect(response.status()).toBe(200);
  return response.json();
}

test("real IdP PKCE, two users, RBAC, CSRF, logout and stolen-cookie replay", async ({ browser }) => {
  assertStagingConfiguration();
  const ownerContext = await browser.newContext();
  const memberContext = await browser.newContext();
  let replayContext;
  try {
    // The actual IdP handles authorization, PKCE exchange, nonce, JWT signing.
    const owner = await authenticate(ownerContext, userA, passwordA);
    const member = await authenticate(memberContext, userB, passwordB);
    expect(member.key).not.toBe(owner.key);

    // Project creation is deliberately performed only on a disposable staging DB.
    const projectResponse = await ownerContext.request.post(origin + "/api/projects", {
      headers: { Origin: origin },
      data: {
        title: "OIDC E2E isolation " + Date.now(),
        domain: "academic",
      },
    });
    expect(projectResponse.status()).toBe(201);
    const project = await projectResponse.json();
    expect(project.id).toMatch(/^[a-f0-9-]{36}$/i);
    const library = origin + "/api/projects/" + project.id + "/library";
    const members = origin + "/api/projects/" + project.id + "/memberships";
    const memberAssignment = members + "/" + member.key;

    const ownerProjects = await listProjects(ownerContext);
    expect(ownerProjects.some((p) => p.id === project.id)).toBe(true);
    expect((await ownerContext.request.get(library)).status()).toBe(200);
    expect((await memberContext.request.get(library)).status()).toBe(404);
    expect((await memberContext.request.get(members)).status()).toBe(404);
    expect((await memberContext.request.put(memberAssignment, {
      headers: { Origin: origin }, data: { role: "editor" },
    })).status()).toBe(404);

    // SameSite cookies are not the only CSRF barrier.
    expect((await ownerContext.request.put(memberAssignment, {
      headers: { Origin: "https://attacker.invalid" }, data: { role: "viewer" },
    })).status()).toBe(403);
    expect((await memberContext.request.get(library)).status()).toBe(404);

    const grant = await ownerContext.request.put(memberAssignment, {
      headers: { Origin: origin }, data: { role: "viewer" },
    });
    expect(grant.status()).toBe(200);
    expect((await grant.json()).role).toBe("viewer");
    expect((await memberContext.request.get(library)).status()).toBe(200);
    expect((await memberContext.request.get(members)).status()).toBe(404);
    expect((await memberContext.request.delete(memberAssignment, {
      headers: { Origin: origin },
    })).status()).toBe(404);

    const ownerMutation = await ownerContext.request.put(members + "/" + owner.key, {
      headers: { Origin: origin }, data: { role: "viewer" },
    });
    expect(ownerMutation.status()).toBe(409);

    const revoke = await ownerContext.request.delete(memberAssignment, {
      headers: { Origin: origin },
    });
    expect(revoke.status()).toBe(204);
    expect((await memberContext.request.get(library)).status()).toBe(404);
    expect((await listProjects(memberContext)).some((p) => p.id === project.id)).toBe(false);

    // Browser logout must revoke the Redis allowlist entry, not just clear
    // the user's local browser cookie. Replaying a copied cookie must fail.
    const cookie = (await ownerContext.cookies(origin)).find((c) => c.name === "eos_session");
    expect(cookie).toBeDefined();
    expect(cookie.httpOnly).toBe(true);
    await owner.page.getByRole("button", { name: "Sign out" }).click();
    await owner.page.waitForURL((url) => url.origin === origin && url.pathname === "/signin");
    expect((await ownerContext.request.get(origin + "/api/identity")).status()).toBe(401);

    replayContext = await browser.newContext();
    await replayContext.addCookies([cookie]);
    expect((await replayContext.request.get(origin + "/api/identity")).status()).toBe(401);

    // Member remains logged in; logout revokes a single browser session,
    // not other users' sessions.
    expect((await memberContext.request.get(origin + "/api/identity")).status()).toBe(200);
    await member.page.getByRole("button", { name: "Sign out" }).click();
    await member.page.waitForURL((url) => url.origin === origin && url.pathname === "/signin");
    expect((await memberContext.request.get(origin + "/api/identity")).status()).toBe(401);
  } finally {
    if (replayContext) await replayContext.close();
    await ownerContext.close();
    await memberContext.close();
  }
});
