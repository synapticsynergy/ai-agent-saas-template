import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end configuration.
 *
 * Runs against a stack that is already up (`make infra-up && make dev`), or
 * against a deployed environment via `E2E_BASE_URL`. It does not start the
 * services itself: the reference flow spans four processes plus Postgres, and
 * a webServer block that only starts one of them would give a misleading
 * "passing" run.
 */

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./specs",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  timeout: 60_000,
  expect: { timeout: 15_000 },

  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // The reference UI must work on a phone: the whole premise is planning an
    // evening while out.
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
