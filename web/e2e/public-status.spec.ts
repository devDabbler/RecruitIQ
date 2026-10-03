import { expect, test } from "@playwright/test";

/**
 * A status link must render without the app shell and must not mint the
 * demo session that every other first visit gets (ATS Phase E).
 */
test("a status link never mints a session and shows no navigation", async ({ page, context }) => {
  await page.goto("/c/not-a-real-token-000000");
  await expect(page.getByRole("heading", { name: "This link is not active" })).toBeVisible();
  const cookies = await context.cookies();
  expect(cookies.find((cookie) => cookie.name === "recruitiq_session")).toBeUndefined();
  await expect(page.getByRole("link", { name: "Candidates" })).toHaveCount(0);
});
