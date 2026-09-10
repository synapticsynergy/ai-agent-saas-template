import { expect, test, type Page } from "@playwright/test";

/**
 * The reference end-to-end flow, exactly as docs/REFERENCE_APP.md describes it:
 *
 *   authenticate → request a plan → observe streamed progress → render the
 *   itinerary and map → replan conversationally → save → retrieve the saved plan
 *
 * The assistant lives in CopilotKit's popup, so most interaction goes through
 * the chat. What is asserted, though, is the *itinerary* — the map and the
 * overlay cards — because that is the application state, and a passing test
 * should mean the plan is right rather than that some prose appeared.
 *
 * Requires the local stack (`make infra-up && make dev`) with the fixture
 * identity enabled, or a deployed environment via `E2E_BASE_URL`.
 */

const REFERENCE_REQUEST =
  "Plan my evening near me. I want dinner, live music, and drinks. Keep it walkable and under $100.";

const RUN_TIMEOUT = 30_000;

function stops(page: Page) {
  return page.getByTestId("itinerary-stop");
}

function summaryCost(page: Page) {
  return page.getByTestId("itinerary-cost");
}

function markers(page: Page) {
  return page.locator(".itinerary-marker");
}

/** The chat popup is also a dialog, so match the approval on its name. */
function approvalDialog(page: Page) {
  return page.getByRole("dialog", { name: "Save this plan?" });
}

function chatInput(page: Page) {
  return page.getByPlaceholder("Describe your evening…");
}

async function openAssistant(page: Page) {
  const input = chatInput(page);
  if (await input.isVisible().catch(() => false)) return input;

  await page.getByTestId("copilot-chat-toggle").click();
  await expect(input).toBeVisible();
  return input;
}

/**
 * Close the assistant from the panel's own header.
 *
 * Not the corner toggle: below `md` the popup is fullscreen and covers it, so
 * the toggle is unclickable exactly when the panel is open. The header button
 * works on every viewport.
 */
async function closeAssistant(page: Page) {
  await page.getByRole("button", { name: "Close", exact: true }).first().click();
  await expect(chatInput(page)).toBeHidden();
}

/**
 * Send a message, then step out of the way.
 *
 * On a phone the panel covers the whole screen, so a person reads the result
 * by closing it — and so does the suite, which keeps assertions about the
 * itinerary identical on both viewports.
 *
 * Pass `thenClose: false` when the message is expected to raise the approval
 * dialog: that modal renders above the chat and blocks pointer events, so
 * closing the panel afterwards is both impossible and unnecessary.
 */
async function ask(page: Page, message: string, { thenClose = true } = {}) {
  const input = await openAssistant(page);
  await input.fill(message);
  await input.press("Enter");
  if (thenClose) await closeAssistant(page);
}

async function planAnEvening(page: Page) {
  await page.goto("/planner");
  await ask(page, REFERENCE_REQUEST);
  await expect(stops(page).first()).toBeVisible({ timeout: RUN_TIMEOUT });
}

test.describe("Planner", () => {
  test("the map and the empty state load for an authenticated user", async ({ page }) => {
    await page.goto("/planner");

    // The map is the page, not a widget on it.
    await expect(page.locator(".leaflet-container")).toBeVisible();
    await expect(page.getByTestId("itinerary-header")).toBeVisible();
    await expect(page.getByText("No itinerary yet")).toBeVisible();
  });

  test("the assistant opens from the empty state and from the corner button", async ({
    page,
  }) => {
    await page.goto("/planner");

    await page.getByTestId("open-assistant").click();
    await expect(chatInput(page)).toBeVisible();

    await closeAssistant(page);

    await page.getByTestId("copilot-chat-toggle").click();
    await expect(chatInput(page)).toBeVisible();
  });

  test("a request renders a structured itinerary over the map", async ({ page }) => {
    await page.goto("/planner");
    await ask(page, REFERENCE_REQUEST);

    await expect(stops(page).first()).toBeVisible({ timeout: RUN_TIMEOUT });
    await expect(stops(page)).toHaveCount(3);

    // Structured state, not prose: each stop carries a time and a cost.
    await expect(stops(page).first()).toContainText(/\d{1,2}:\d{2}/);
    await expect(summaryCost(page)).toBeVisible();
    await expect(page.getByTestId("itinerary-stop-count")).toContainText("3 stops");
  });

  test("the map gets a marker per stop", async ({ page }) => {
    await planAnEvening(page);
    await expect(markers(page)).toHaveCount(3);
  });

  test("selecting a stop highlights it", async ({ page }) => {
    await planAnEvening(page);

    await expect(stops(page).first()).toHaveAttribute("data-selected", "true");

    const second = stops(page).nth(1);
    await second.click();

    await expect(second).toHaveAttribute("data-selected", "true");
    await expect(stops(page).first()).toHaveAttribute("data-selected", "false");
  });

  test("the itinerary panel collapses to leave the map clear", async ({ page }) => {
    await planAnEvening(page);

    await page.getByRole("button", { name: "Hide the itinerary" }).click();
    await expect(stops(page).first()).toBeHidden();
    // The header stays, so the plan is still identifiable.
    await expect(page.getByTestId("itinerary-header")).toBeVisible();

    await page.getByRole("button", { name: "Show the itinerary" }).click();
    await expect(stops(page).first()).toBeVisible();
  });
});

test.describe("Conversational replanning", () => {
  test("'make it cheaper' lowers the estimated cost", async ({ page }) => {
    await planAnEvening(page);

    const before = await summaryCost(page).innerText();

    await ask(page, "Make it cheaper.");
    await expect(summaryCost(page)).not.toHaveText(before, { timeout: RUN_TIMEOUT });

    const parse = (value: string) => Number(value.replace(/[^0-9.]/g, ""));
    expect(parse(await summaryCost(page).innerText())).toBeLessThan(parse(before));
  });

  test("a follow-up can change the music genre", async ({ page }) => {
    await planAnEvening(page);

    await ask(page, "Replace the live music with jazz.");
    await expect(stops(page).filter({ hasText: "Live music" }).first()).toBeVisible({
      timeout: RUN_TIMEOUT,
    });
  });
});

test.describe("Saving", () => {
  test("the save button asks for approval, then persists", async ({ page }) => {
    await planAnEvening(page);

    await page.getByTestId("save-plan").click();

    // Approval is requested before anything is written. Matched on its
    // accessible name, because the chat popup is a dialog too.
    const dialog = approvalDialog(page);
    await expect(dialog).toBeVisible({ timeout: RUN_TIMEOUT });
    await expect(dialog).toContainText("permission");

    await dialog.getByRole("button", { name: "Save plan" }).click();
    await expect(page.getByTestId("itinerary-saved")).toBeVisible({ timeout: RUN_TIMEOUT });

    // The saved plan is retrievable through the deterministic API, with no
    // agent involved.
    await page.goto("/plans");
    await expect(page.getByRole("heading", { name: "Saved plans" })).toBeVisible();
    await expect(page.locator(".MuiCard-root").first()).toBeVisible();
  });

  test("declining the approval writes nothing", async ({ page }) => {
    await planAnEvening(page);

    await page.getByTestId("save-plan").click();
    const dialog = approvalDialog(page);
    await expect(dialog).toBeVisible({ timeout: RUN_TIMEOUT });

    await dialog.getByRole("button", { name: "Not now" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("itinerary-saved")).toHaveCount(0);
  });

  test("asking the assistant to save also asks for approval", async ({ page }) => {
    await planAnEvening(page);

    await ask(page, "Save this plan.", { thenClose: false });
    await expect(approvalDialog(page)).toBeVisible({ timeout: RUN_TIMEOUT });
  });
});

test.describe("Navigation", () => {
  test("the home page links into the app", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Plan my evening" })).toBeVisible();
    await page
      .getByRole("link", { name: /planner/i })
      .first()
      .click();
    await expect(page).toHaveURL(/\/planner/);
  });

  test("saved plans are reachable from the shell", async ({ page }) => {
    await page.goto("/planner");
    await page.getByRole("link", { name: "Plans", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Saved plans" })).toBeVisible();
  });
});
