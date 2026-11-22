/** Executed only by the gated OIDC staging workflow. Not a simulated IdP. */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "oidc-provider.spec.mjs",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "test-results/oidc-staging",
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
