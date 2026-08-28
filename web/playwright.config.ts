import { defineConfig, devices } from "@playwright/test";

// Port 3100, not 3000: a `next dev` is usually already sitting on 3000, and the
// suite should never quietly test whatever happens to be running there.
const PORT = process.env.E2E_PORT ?? "3100";
const BASE_URL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${PORT}`;

/**
 * The journey runs against a live stack: Next on :3000, FastAPI on :8010, and a
 * database seeded by `scripts/seed_demo.py`. It asserts real rows render, so it
 * cannot be pointed at an empty database.
 *
 * Not wired into CI. The suite there has Postgres but no seed run and no model
 * credentials, and the Matching screen calls a real provider — a run would fail
 * for reasons unrelated to the code under test.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // The journey crosses two model-backed screens; 30s is not enough for one
  // pass through all eight.
  timeout: 180_000,
  expect: { timeout: 15_000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    // Nav labels are `hidden lg:inline`, so anything narrower than the lg
    // breakpoint (1024px) leaves getByRole("link", {name}) matching nothing.
    viewport: { width: 1440, height: 900 },
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: {
    // A production build, not `next dev`. Two reasons: it is what actually
    // ships, and the dev server's Turbopack cache can rot after a long session
    // into serving 403s for its own chunks — which leaves every page rendering
    // correctly from SSR while nothing hydrates, so the interactive assertions
    // below fail for a reason that has nothing to do with the code.
    command: `npm run build && node scripts/start-standalone.mjs ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
