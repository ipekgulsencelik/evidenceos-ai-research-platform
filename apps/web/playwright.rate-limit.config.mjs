/** Only the opt-in, genuine Keycloak + Redis quota acceptance test. */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "oidc-rate-limit.spec.mjs",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "test-results/oidc-rate-limit",
  use: {
    headless: true,
    ignoreHTTPSErrors: false,
    trace: "off",
    screenshot: "off",
    video: "off",
    actionTimeout: 15_000,
    navigationTimeout: 45_000,
  },
});
