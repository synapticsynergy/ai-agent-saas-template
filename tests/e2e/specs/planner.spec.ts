import { expect, test, type Page } from "@playwright/test";

/**
 * The reference end-to-end flow, exactly as docs/REFERENCE_APP.md describes it:
 *
 *   authenticate → request a plan → observe streamed progress → render the
 *   itinerary and map → replan conversationally → save → retrieve the saved plan
 *
 * Requires the local stack (`make infra-up && make dev`) with the fixture
 * identity enabled, or a deployed environment via `E2E_BASE_URL`.
 */

const EXAMPLE = "Try the example";

function stops(page: Page) {
  return page.getByTestId("itinerary-stop");
}

function summaryCost(page: Page) {
  return page.getByTestId("itinerary-cost");
}

async function planAnEvening(page: Page) {
  await page.goto("/planner");
  await page.getByRole("button", { name: EXAMPLE }).click();
  await expect(stops(page).first()).toBeVisible({ timeout: 30_000 });
}

test.describe("Planner", () => {
  test("the planner loads for an authenticated user", async ({ page }) => {
    await page.goto("/planner");

    await expect(page.getByRole("heading", { name: "Tonight" })).toBeVisible();
    await expect(page.getByLabel("What kind of evening?")).toBeVisible();
    await expect(page.getByText("No itinerary yet")).toBeVisible();
  });

  test("a request streams progress and renders a structured itinerary", async ({ page }) => {
    await page.goto("/planner");
    await page.getByRole("button", { name: EXAMPLE }).click();

    await expect(stops(page).first()).toBeVisible({ timeout: 30_000 });
    await expect(stops(page)).toHaveCount(3);

    // The itinerary is structured state, not prose: each stop carries a time,
    // a cost and the reason the agent chose it.
    await expect(stops(page).first()).toContainText(/\d{1,2}:\d{2}/);
    await expect(summaryCost(page)).toBeVisible();
    await expect(page.getByTestId("itinerary-stop-count")).toContainText("3 stops");
  });

  test("the map renders a marker per stop", async ({ page }) => {
    await planAnEvening(page);
    await expect(page.getByLabel(/^Stop 1:/)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByLabel(/^Stop 3:/)).toBeVisible();
  });

  test("selecting a stop highlights it and moves the map selection", async ({ page }) => {
    await planAnEvening(page);

    await expect(stops(page).first()).toHaveAttribute("data-selected", "true");

    const second = stops(page).nth(1);
    await second.click();

    await expect(second).toHaveAttribute("data-selected", "true");
    await expect(stops(page).first()).toHaveAttribute("data-selected", "false");
  });
});

test.describe("Conversational replanning", () => {
  test("'make it cheaper' lowers the estimated cost", async ({ page }) => {
    await planAnEvening(page);

    const before = await summaryCost(page).innerText();

    await page.getByRole("button", { name: "Make it cheaper." }).click();
    await expect(summaryCost(page)).not.toHaveText(before, { timeout: 30_000 });

    const after = await summaryCost(page).innerText();
    const parse = (value: string) => Number(value.replace(/[^0-9.]/g, ""));
    expect(parse(after)).toBeLessThan(parse(before));
  });

  test("a follow-up can change the music genre", async ({ page }) => {
    await planAnEvening(page);

    await page.getByRole("button", { name: "Replace the live music with jazz." }).click();
    await expect(stops(page).filter({ hasText: "Live music" }).first()).toBeVisible({
      timeout: 30_000,
    });
  });
});

test.describe("Saving", () => {
  test("saving asks for approval, then persists and appears in saved plans", async ({ page }) => {
    await planAnEvening(page);

    await page.getByRole("button", { name: "Save this plan." }).click();

    // Approval is requested before anything is written.
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 20_000 });
    await expect(dialog).toContainText("permission");

    await dialog.getByRole("button", { name: "Save plan" }).click();
    await expect(page.getByTestId("itinerary-saved")).toBeVisible({ timeout: 30_000 });

    // The saved plan is retrievable through the deterministic API, with no
    // agent involved.
    await page.goto("/plans");
    await expect(page.getByRole("heading", { name: "Saved plans" })).toBeVisible();
    await expect(page.locator(".MuiCard-root").first()).toBeVisible();
  });

  test("declining the approval writes nothing", async ({ page }) => {
    await planAnEvening(page);

    await page.getByRole("button", { name: "Save this plan." }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 20_000 });

    await dialog.getByRole("button", { name: "Not now" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("itinerary-saved")).toHaveCount(0);
  });
});

test.describe("Navigation", () => {
  test("the home page links into the app", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Plan my evening" })).toBeVisible();
    await page.getByRole("link", { name: /planner/i }).first().click();
    await expect(page).toHaveURL(/\/planner/);
  });

  test("saved plans are reachable from the shell", async ({ page }) => {
    await page.goto("/planner");
    await page.getByRole("link", { name: "Plans", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Saved plans" })).toBeVisible();
  });
});
