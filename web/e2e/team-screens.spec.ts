import { expect, test } from "@playwright/test";

/**
 * The three ATS Phase B screens render for the auto-signed-in demo user
 * (spec section 10: the demo must keep working on every screen).
 */
for (const [path, heading] of [
  ["/interviews", "Interviews"],
  ["/team", "Team"],
  ["/settings", "Settings"],
  ["/feedback-templates", "Feedback templates"],
] as const) {
  test(`${path} renders for the demo account`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await expect(page.getByText(/^Could not load/)).toHaveCount(0);
  });
}

test("the demo never sees a team member's email", async ({ page }) => {
  await page.goto("/team");
  await expect(page.getByRole("heading", { name: "Team", level: 1 })).toBeVisible();
  await expect(page.locator("main")).not.toContainText("@");
});
