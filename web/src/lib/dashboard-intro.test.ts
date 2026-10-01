import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { INTRO_DATA_NOTE, INTRO_SUMMARY, INTRO_TITLE, TOUR_STEPS } from "./dashboard-intro";

const allCopy = [
  INTRO_TITLE,
  INTRO_SUMMARY,
  INTRO_DATA_NOTE,
  ...TOUR_STEPS.flatMap((step) => [step.label, step.detail]),
];

describe("dashboard intro", () => {
  it("says what the app is and that the data is synthetic", () => {
    expect(INTRO_TITLE).toMatch(/RecruitIQ/);
    expect(INTRO_SUMMARY).toMatch(/recruit/i);
    expect(INTRO_DATA_NOTE).toMatch(/synthetic/i);
  });

  it("only links the tour to screens that are in the nav", () => {
    // A tour step pointing at a route the nav dropped would be a dead end on
    // the first page a visitor sees.
    const nav = readFileSync(resolve(__dirname, "../components/nav.tsx"), "utf8");
    expect(TOUR_STEPS.length).toBeGreaterThanOrEqual(3);
    for (const step of TOUR_STEPS) {
      expect(nav).toContain(`href: "${step.href}"`);
    }
    expect(new Set(TOUR_STEPS.map((s) => s.href)).size).toBe(TOUR_STEPS.length);
  });

  it("uses no em or en dashes in visible copy", () => {
    for (const line of allCopy) {
      expect(line).not.toMatch(/[–—―]/);
    }
  });
});
