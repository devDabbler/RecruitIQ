import { describe, expect, it } from "vitest";

import {
  CANDIDATE_EXPORT_PATH,
  activityPredicate,
  canViewReports,
  daysLabel,
  exportHref,
  formatDays,
  formatShare,
  funnelWidth,
} from "./reports";

describe("formatDays", () => {
  it("says so when nothing has finished", () => {
    expect(formatDays(null)).toBe("No completed stages yet");
    expect(formatDays(undefined)).toBe("No completed stages yet");
  });

  it("rounds short medians to a tenth and long ones to whole days", () => {
    expect(formatDays(0.4)).toBe("Under a day");
    expect(formatDays(1)).toBe("1 day");
    expect(formatDays(2.46)).toBe("2.5 days");
    expect(formatDays(12.6)).toBe("13 days");
  });
});

describe("small formatters", () => {
  it("formats shares, day counts, and bar widths", () => {
    expect(formatShare(0.5)).toBe("50%");
    expect(formatShare(0)).toBe("0%");
    expect(daysLabel(1)).toBe("1 day");
    expect(daysLabel(16)).toBe("16 days");
    expect(funnelWidth(5, 10)).toBe("50%");
    expect(funnelWidth(3, 0)).toBe("0%");
  });
});

describe("exportHref", () => {
  it("passes the job filter through to the CSV export", () => {
    expect(exportHref()).toBe(CANDIDATE_EXPORT_PATH);
    expect(exportHref(7)).toBe(`${CANDIDATE_EXPORT_PATH}?job_id=7`);
  });
});

describe("activityPredicate", () => {
  const base = { job_title: "Data Engineer", stage_name: "HR screen" };

  it("reads as plain English for every kind", () => {
    expect(activityPredicate({ ...base, kind: "applied", stage_name: null })).toBe(
      "applied to Data Engineer",
    );
    expect(activityPredicate({ ...base, kind: "passed" })).toBe("passed HR screen for Data Engineer");
    expect(activityPredicate({ ...base, kind: "skipped" })).toBe(
      "skipped HR screen for Data Engineer",
    );
    expect(activityPredicate({ ...base, kind: "rejected" })).toBe(
      "was rejected at HR screen for Data Engineer",
    );
    expect(activityPredicate({ ...base, kind: "hired" })).toBe("was hired as Data Engineer");
    expect(activityPredicate({ ...base, kind: "declined" })).toBe(
      "declined the offer for Data Engineer",
    );
  });
});

describe("canViewReports", () => {
  it("lets the demo and the hiring roles in, and keeps interviewers out", () => {
    expect(canViewReports("demo")).toBe(true);
    expect(canViewReports("admin")).toBe(true);
    expect(canViewReports("hiring_manager")).toBe(true);
    expect(canViewReports("hiring_team")).toBe(true);
    expect(canViewReports("interviewer")).toBe(false);
    expect(canViewReports(null)).toBe(false);
  });
});
