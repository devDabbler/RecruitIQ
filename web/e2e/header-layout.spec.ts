import { expect, test } from "@playwright/test";

/**
 * The header must fit every common screen width without sideways scroll.
 *
 * Until 2026-09-30 the labelled nav and the session badge shared one row at
 * every width, which pushed phones to 616px of page width and tablets and
 * small laptops to 1202px, with "Sign in" off screen. Widths cover a small
 * phone, a common phone, a tablet, and both sides of the lg and xl
 * breakpoints where the layout changes shape.
 *
 * Since ATS Phase B the navigation is a sidebar (an icon rail below lg), so
 * the header holds only the logo and the account badge; the check still
 * guards against sideways scroll at every width.
 */
const WIDTHS = [360, 390, 768, 1024, 1279, 1280, 1366];

for (const width of WIDTHS) {
  test(`header fits at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/candidates");

    const signIn = page.getByRole("link", { name: "Sign in" });
    await expect(signIn).toBeVisible();

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(width);

    const box = await signIn.boundingBox();
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);

    // Below lg the sidebar is an icon rail, so each link needs its own
    // accessible name; getByRole would not find it otherwise.
    const nav = page.getByRole("navigation", { name: "Main" });
    for (const name of ["Dashboard", "Candidates", "Interviews", "Matching", "Assistant", "Transparency", "Settings"]) {
      await expect(nav.getByRole("link", { name })).toBeVisible();
    }
  });
}
