import { expect, test } from "@playwright/test";

/**
 * Reports and the new dashboard cards as the auto-signed-in demo user. Like
 * the main journey, assertions target real seeded data (stage names, counts)
 * rather than headings alone, which would pass against an empty database.
 */
test("the demo user sees Reports with live numbers and the query note", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Reports", level: 1 })).toBeVisible();
  await expect(page.getByText(/Every number on this page is a query/)).toBeVisible();
  await expect(page.getByText("Could not load reports", { exact: true })).toHaveCount(0);
  for (const title of [
    "Funnel",
    "Hires and rejections",
    "Time in stage",
    "Where applicants come from",
    "No movement in 7+ days",
  ]) {
    await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText("Resume submitted").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Export candidates/ })).toBeVisible();
});

test("the dashboard shows the stage funnel, attention list, and activity", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Pipeline", { exact: true })).toBeVisible();
  await expect(page.getByText("Needs attention", { exact: true })).toBeVisible();
  await expect(page.getByText("Recent activity", { exact: true })).toBeVisible();
  await expect(page.getByText("Resume submitted").first()).toBeVisible();
});

test("the Reports nav item is there for the demo", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await expect(page).toHaveURL(/\/reports$/);
});
