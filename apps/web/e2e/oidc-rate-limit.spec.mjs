/** Opt-in real Keycloak + Redis rate-limit acceptance, with a FRESH browser.
 *
 * Run only against the isolated localhost OIDC staging stack with the
 * compose.oidc-rate-limit-test.yaml API override. Credentials come from the
 * untracked test environment; never print or persist them.
 */
import { test, expect } from "@playwright/test";

const origin = process.env.EVIDENCEOS_E2E_ORIGIN;
const username = process.env.EVIDENCEOS_E2E_USER_A;
const password = process.env.EVIDENCEOS_E2E_PASSWORD_A;

test("fresh OIDC session reaches Redis 429 and forwards Retry-After", async ({ browser }) => {
  if (process.env.EVIDENCEOS_E2E_ALLOW_LOCAL_HTTP !== "1" ||
      origin !== "http://127.0.0.1:3101" || !username || !password) {
    throw new Error("This rate-limit test requires isolated local Keycloak staging credentials.");
  }
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.goto(origin + "/signin");
    await page.getByRole("link", { name: "Sign in securely" }).click();
    await page.locator('input[name="username"]').fill(username);
    await page.locator('input[type="password"]').fill(password);
    await page.locator('input[type="submit"], button[type="submit"]').first().click();
    await page.waitForURL((url) => url.origin === origin && url.pathname === "/", {
      timeout: 45000,
    });
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();

    // This succeeds only if the callback has validated a signed access token
    // against the real FastAPI OIDC verifier and registered the Redis session.
    const responses = [];
    for (let i = 0; i < 12; i++) {
      const response = await context.request.get(origin + "/api/projects", {
        failOnStatusCode: false,
        timeout: 10000,
      });
      const status = response.status();
      const retry = response.headers()["retry-after"] ?? null;
      responses.push(status);
      if (status === 401) {
        throw new Error("401: OIDC session rejected. Check cookie/Redis expiry, then rerun fresh.");
      }
      if (status !== 200 && status !== 429) {
        throw new Error("Unexpected API status " + status + "; verify staging API and IdP.");
      }
      if (status === 429) {
        expect(retry, "The BFF must forward a numeric Retry-After on 429").toMatch(/^[1-9][0-9]*$/);
        expect(Number(retry)).toBeLessThanOrEqual(60);
      }
    }
    // Existing quota usage from this same test account can reduce the
    // number of 200s. Login itself guarantees a fresh successful API
    // validation in its callback before any browser session is issued.
    expect(responses, "Enable the opt-in Compose rate-limit override first").toContain(429);
    console.log("Authenticated rate-limit statuses:", responses.join(", "));
  } finally {
    await context.close();
  }
});
