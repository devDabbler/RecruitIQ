import { describe, expect, it } from "vitest";

import { NAV_GROUPS, isActive, visibleGroups } from "./nav";
import type { Role } from "./permissions";

const labels = (role: Role | null) => visibleGroups(role).flatMap((g) => g.items.map((i) => i.label));
const all = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.label));

describe("visibleGroups", () => {
  it("shows the demo every screen", () => {
    expect(labels("demo")).toEqual(all);
    expect(all).toHaveLength(12);
    expect(all).toContain("Reports");
    expect(all).toContain("Email templates");
  });

  it("gives interviewers only what they can use", () => {
    expect(labels("interviewer")).toEqual(["Jobs", "Candidates", "Interviews", "Transparency", "Settings"]);
  });

  it("shows everything while the session is still resolving", () => {
    expect(labels(null)).toEqual(all);
  });

  it("groups in the spec's order", () => {
    expect(NAV_GROUPS.map((g) => g.label)).toEqual(["Hiring", "Intelligence", "Admin"]);
  });
});

describe("isActive", () => {
  it("does not light Dashboard on every page", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/", "/jobs")).toBe(false);
  });

  it("covers a section's detail pages and nothing that merely shares a prefix", () => {
    expect(isActive("/jobs", "/jobs/12")).toBe(true);
    expect(isActive("/jobs", "/jobsboard")).toBe(false);
  });
});
