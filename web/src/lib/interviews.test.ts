import { describe, expect, it } from "vitest";

import {
  INTERVIEW_STATE_LABELS,
  RECOMMENDATIONS,
  RECOMMENDATION_LABELS,
  canSummarizeFeedback,
  memberName,
  summaryStamp,
} from "./interviews";

describe("interview vocabulary", () => {
  it("has plain English for every recommendation and state", () => {
    for (const key of RECOMMENDATIONS) expect(RECOMMENDATION_LABELS[key]).toBeTruthy();
    expect(RECOMMENDATION_LABELS.strong_no_hire).toBe("Strong no hire");
    for (const state of ["upcoming", "waiting", "submitted", "skipped"]) {
      expect(INTERVIEW_STATE_LABELS[state]).toBeTruthy();
    }
  });

  it("names a person without ever showing an email", () => {
    expect(memberName({ name: "Priya Raman", role: "hiring_manager" })).toBe("Priya Raman");
    expect(memberName({ name: null, role: "admin" })).toBe("Admin");
  });
});

describe("feedback summary", () => {
  const submitted = { state: "submitted", feedback_hidden: false };

  it("is offered once two readable forms are in", () => {
    expect(canSummarizeFeedback([submitted], "hiring_manager")).toBe(false);
    expect(canSummarizeFeedback([submitted, { state: "waiting" }], "admin")).toBe(false);
    expect(canSummarizeFeedback([submitted, submitted], "hiring_manager")).toBe(true);
    expect(canSummarizeFeedback([submitted, submitted], "demo")).toBe(true);
  });

  it("is never offered to interviewers or over feedback the viewer cannot read", () => {
    expect(canSummarizeFeedback([submitted, submitted], "interviewer")).toBe(false);
    expect(canSummarizeFeedback([submitted, submitted], null)).toBe(false);
    expect(
      canSummarizeFeedback([submitted, submitted, { state: "submitted", feedback_hidden: true }], "admin"),
    ).toBe(false);
  });

  it("labels the summary as AI-generated, unsaved, and when", () => {
    const stamp = summaryStamp(3, "2026-10-06T15:04:00", "UTC");
    expect(stamp).toBe(
      "AI-generated from 3 submitted feedback forms on Oct 6, 3:04 PM. Not saved. Check it against the forms before you act on it.",
    );
    expect(stamp).not.toMatch(/—/);
    expect(summaryStamp(2, "garbage")).toMatch(/^AI-generated from 2 submitted feedback forms\. /);
  });
});
