import { describe, expect, it } from "vitest";

import type { FeedbackTemplate } from "./domain";
import { applyTemplate, badgeText, draftSavedLabel, feedbackShortcut, templatesForJob } from "./feedback";

function template(id: number, job_id: number | null): FeedbackTemplate {
  return { id, name: `T${id}`, body: "", job_id, updated_at: "2026-10-06T10:00:00" };
}

describe("templatesForJob", () => {
  it("puts the job's own templates first, then global, and drops other jobs'", () => {
    const all = [template(1, null), template(2, 7), template(3, 8), template(4, null), template(5, 7)];
    expect(templatesForJob(all, 7).map((t) => t.id)).toEqual([2, 5, 1, 4]);
    expect(templatesForJob(all, 9).map((t) => t.id)).toEqual([1, 4]);
  });
});

describe("applyTemplate", () => {
  it("fills an empty box and appends below existing notes", () => {
    expect(applyTemplate("", "Strengths:")).toBe("Strengths:");
    expect(applyTemplate("   ", "Strengths:")).toBe("Strengths:");
    expect(applyTemplate("Good call.\n", "Strengths:")).toBe("Good call.\n\nStrengths:");
  });
});

describe("feedbackShortcut", () => {
  const key = (k: string, extra: Partial<Parameters<typeof feedbackShortcut>[0]> = {}) =>
    feedbackShortcut({ key: k, ctrlKey: false, metaKey: false, inTextField: false, ...extra });

  it("maps 1-5 to a rating outside text fields only", () => {
    expect(key("3")).toEqual({ kind: "rating", value: 3 });
    expect(key("5")).toEqual({ kind: "rating", value: 5 });
    expect(key("6")).toBeNull();
    expect(key("0")).toBeNull();
    expect(key("3", { inTextField: true })).toBeNull();
    expect(key("3", { ctrlKey: true })).toBeNull();
  });

  it("submits on Ctrl or Cmd + Enter, even while typing", () => {
    expect(key("Enter", { ctrlKey: true, inTextField: true })).toEqual({ kind: "submit" });
    expect(key("Enter", { metaKey: true })).toEqual({ kind: "submit" });
    expect(key("Enter", { inTextField: true })).toBeNull();
  });
});

describe("badgeText", () => {
  it("hides at zero and caps at 9+", () => {
    expect(badgeText(0)).toBeNull();
    expect(badgeText(-1)).toBeNull();
    expect(badgeText(Number.NaN)).toBeNull();
    expect(badgeText(3)).toBe("3");
    expect(badgeText(12)).toBe("9+");
  });
});

describe("draftSavedLabel", () => {
  it("falls back when the time is unreadable", () => {
    expect(draftSavedLabel("nonsense")).toBe("Draft saved");
    expect(draftSavedLabel("2026-10-06T14:41:00")).toMatch(/^Draft saved \d/);
  });

  it("reads a zone-less API timestamp as UTC", () => {
    expect(draftSavedLabel("2026-10-06T14:41:00.123456")).toBe(
      draftSavedLabel(new Date(Date.UTC(2026, 9, 6, 14, 41))),
    );
    expect(draftSavedLabel("2026-10-06T14:41:00Z")).toBe(draftSavedLabel("2026-10-06T14:41:00"));
  });
});
