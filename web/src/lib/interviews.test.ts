import { describe, expect, it } from "vitest";

import { INTERVIEW_STATE_LABELS, RECOMMENDATIONS, RECOMMENDATION_LABELS, memberName } from "./interviews";

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
