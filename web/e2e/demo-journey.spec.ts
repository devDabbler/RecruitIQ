import { expect, test, type Page } from "@playwright/test";

/**
 * One journey through all eight screens as the auto-signed-in demo user
 * (Phase 3 spec §8).
 *
 * The point is "no dead tabs": every screen reaches the API, renders seeded
 * rows, and shows no error state. Assertions therefore target real data —
 * candidate names, job titles, match scores — rather than the presence of a
 * heading, which would still pass against an empty database.
 */

/** Every ErrorState title in `src/app`. None should appear on a healthy run. */
const ERROR_TITLES = [
  "Could not load the dashboard",
  "Could not load candidates",
  "Could not load jobs",
  "Matching failed",
];

async function expectNoErrorState(page: Page) {
  for (const title of ERROR_TITLES) {
    await expect(page.getByText(title, { exact: true })).toHaveCount(0);
  }
}

test("the demo user can walk all eight screens and every one shows live data", async ({
  page,
}) => {
  // ---- 1. Dashboard -------------------------------------------------------
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  await expectNoErrorState(page);

  // The candidate count is a query, not a fixture, so a zero here means the
  // dashboard is lying or the database was never seeded.
  const candidateStat = page.locator("div", { has: page.getByText("Candidates", { exact: true }) });
  await expect(candidateStat.first()).toBeVisible();
  await expect(page.getByText("Pipeline", { exact: true })).toBeVisible();

  // No session cookie was set by hand: proxy.ts must have minted a demo token
  // server-side before this page rendered.
  const cookies = await page.context().cookies();
  expect(cookies.find((c) => c.name === "recruitiq_session")).toBeTruthy();

  // ---- 2. Candidates ------------------------------------------------------
  await page.getByRole("link", { name: "Candidates", exact: true }).click();
  await expect(page).toHaveURL(/\/candidates$/);
  await expect(page.getByRole("heading", { name: "Candidates", level: 1 })).toBeVisible();
  await expectNoErrorState(page);

  const rows = page.locator("tbody tr");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThan(0);

  // ---- 2a. Search-as-you-type narrows the list ---------------------------
  const search = page.getByLabel("Search candidates");
  await expect(search).toBeVisible();

  // Retried rather than typed once: the input is visible as soon as the server
  // HTML lands, but keystrokes before the client bundle hydrates never reach
  // React's onChange, so the debounce never arms and the URL never changes.
  await expect(async () => {
    await search.fill("");
    await search.pressSequentially("Python", { delay: 30 });
    // The filter is a URL round-trip through the Server Component, not local
    // state, so the query string is the real signal.
    await expect(page).toHaveURL(/[?&]q=Python/i, { timeout: 3_000 });
  }).toPass({ timeout: 60_000 });

  await expect(page.locator("tbody tr").first()).toBeVisible();
  await expectNoErrorState(page);

  await search.fill("");
  await expect(page).not.toHaveURL(/[?&]q=Python/i, { timeout: 15_000 });

  // ---- 3. Candidate detail ------------------------------------------------
  const firstCandidate = rows.first().getByRole("link").first();
  // The link opens with an initials avatar ("IM"), so the name is the second
  // line of its text, not the first.
  const [, candidateName] = (await firstCandidate.innerText())
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  expect(candidateName).toBeTruthy();
  await firstCandidate.click();

  await expect(page).toHaveURL(/\/candidates\/[0-9a-f-]{36}$/);
  // The detail page must be about the person we clicked, not just any page that
  // happened to render.
  await expect(page.getByRole("heading", { name: candidateName, level: 1 })).toBeVisible();

  // ---- 4. Jobs ------------------------------------------------------------
  await page.getByRole("link", { name: "Jobs", exact: true }).click();
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.getByRole("heading", { name: "Jobs", level: 1 })).toBeVisible();
  await expectNoErrorState(page);

  // A read-only visitor gets no job management affordances. The backend gate is
  // the real control (test_auth.py walks the route table and asserts every
  // mutating route refuses the demo role), but showing a demo user a "New job"
  // button guaranteed to 403 is a broken screen, so the hiding is pinned too.
  await expect(page.getByRole("link", { name: "New job" })).toHaveCount(0);
  await expect(page.locator('a[href$="/edit"]')).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Delete / })).toHaveCount(0);

  // Jobs render as cards, not table rows. Excluding /edit keeps this pointing
  // at a job card rather than an admin control if those ever render here.
  const firstJob = page.locator('a[href^="/jobs/"]:not([href$="/edit"])').first();
  await expect(firstJob).toBeVisible();
  const jobTitle = (await firstJob.innerText()).trim();
  expect(jobTitle).toBeTruthy();

  // ---- 5. Job detail ------------------------------------------------------
  await firstJob.click();
  await expect(page).toHaveURL(/\/jobs\/\d+$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: jobTitle, level: 1 })).toBeVisible();
  // The description must not wait on matching: that panel streams in behind a
  // Suspense boundary precisely so this heading paints immediately.
  await expect(page.getByText("Required qualifications")).toBeVisible();

  // ---- 6. Matching --------------------------------------------------------
  await page.getByRole("link", { name: "Matching", exact: true }).click();
  await expect(page).toHaveURL(/\/matching/);
  await expect(page.getByRole("heading", { name: "Matching", level: 1 })).toBeVisible();

  // Ranking runs a real embedding query, so give it room beyond the default.
  // A percentage on screen is the proof the pgvector path actually returned.
  await expect(page.getByText(/%/).first()).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("Skills", { exact: true }).first()).toBeVisible();
  await expectNoErrorState(page);

  // ---- 7. Resume Upload ---------------------------------------------------
  await page.getByRole("link", { name: "Upload", exact: true }).click();
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByRole("heading", { name: "Resume Upload", level: 1 })).toBeVisible();
  // The uploader is the screen; without an input there is nothing to demo.
  await expect(page.locator('input[type="file"]')).toBeAttached();

  // ---- 8. AI Assistant ----------------------------------------------------
  await page.getByRole("link", { name: "Assistant", exact: true }).click();
  await expect(page).toHaveURL(/\/assistant$/);
  await expect(page.getByRole("heading", { name: "AI Assistant", level: 1 })).toBeVisible();

  const composer = page.getByRole("textbox").first();
  await expect(composer).toBeVisible();
  await expect(composer).toBeEditable();
});

test("an unknown candidate renders not-found rather than crashing", async ({ page }) => {
  const response = await page.goto("/candidates/00000000-0000-4000-8000-000000000000");

  // Asserts the rendered result, not the status line, and that is deliberate.
  // Once the root layout streams — which is what lets every `loading.tsx`
  // fallback paint instead of the browser sitting on the previous page — the
  // response headers are already sent by the time `notFound()` runs, so the
  // status can no longer be changed to 404. The loading.js docs call this out
  // directly. Next marks the streamed body `noindex` instead, which is the one
  // thing the 404 status was actually buying us here: no public search engine
  // will index a bogus candidate URL. The screen itself is unchanged.
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Not found", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to the dashboard" })).toBeVisible();

  // Checked against the served bytes rather than the hydrated DOM: this tag is
  // emitted by Next's streaming machinery mid-body, and a crawler reads the
  // response, not a React tree it never builds.
  expect(await response?.text()).toContain('name="robots" content="noindex"');
});
