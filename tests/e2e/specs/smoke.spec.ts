import { expect, test } from "@playwright/test";

/**
 * Minimal post-deploy smoke suite.
 *
 * Kept separate from the full flow so `make smoke ENV=staging` can run it
 * against a real environment without depending on fixture data or on the agent
 * producing any particular itinerary.
 */

test.describe("Smoke", () => {
  test("the home page loads", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBeLessThan(400);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("the page is responsive", async ({ page }) => {
    await page.goto("/");
    await page.setViewportSize({ width: 375, height: 812 });

    // Nothing should overflow horizontally on a phone.
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(overflows).toBe(false);
  });

  test("the app renders without console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Dev-server HMR websocket noise is not an application error.
    const real = errors.filter((text) => !/hmr|websocket|Lit is in dev mode/i.test(text));
    expect(real).toEqual([]);
  });
});
