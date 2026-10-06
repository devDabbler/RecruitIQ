import { describe, expect, it } from "vitest";

import table from "./role-permissions.json";
import {
  AUDIT_VIEW,
  CANDIDATES_ADD,
  DATA_EXPORT,
  DELETE_RECORDS,
  DEPARTMENTS_MANAGE,
  FEEDBACK_SUBMIT,
  JOBS_WRITE,
  PIPELINE_MOVE,
  PROFILE_EDIT,
  REPORTS_VIEW,
  SCORE_BEFORE_FEEDBACK,
  TEMPLATES_MANAGE,
  USERS_CHANGE_ROLE,
  USERS_INVITE,
  can,
  roleLabel,
} from "./permissions";

describe("can", () => {
  it("matches the spec matrix for the rows the screens depend on", () => {
    expect(can("hiring_manager", JOBS_WRITE)).toBe(true);
    expect(can("hiring_team", JOBS_WRITE)).toBe(false);
    expect(can("hiring_team", PIPELINE_MOVE)).toBe(true);
    expect(can("interviewer", PIPELINE_MOVE)).toBe(false);
    expect(can("interviewer", FEEDBACK_SUBMIT)).toBe(true);
    expect(can("interviewer", SCORE_BEFORE_FEEDBACK)).toBe(false);
    expect(can("hiring_manager", USERS_INVITE)).toBe(true);
    expect(can("hiring_manager", USERS_CHANGE_ROLE)).toBe(false);
    expect(can("admin", DELETE_RECORDS)).toBe(true);
    expect(can("demo", CANDIDATES_ADD)).toBe(false);
    expect(can("demo", SCORE_BEFORE_FEEDBACK)).toBe(true);
    expect(can("admin", DATA_EXPORT)).toBe(true);
    expect(can("hiring_manager", DATA_EXPORT)).toBe(false);
    expect(can("demo", DATA_EXPORT)).toBe(false);
    expect(can("admin", DEPARTMENTS_MANAGE)).toBe(true);
    expect(can("hiring_manager", DEPARTMENTS_MANAGE)).toBe(false);
  });

  it("grants nothing to a missing or unknown role", () => {
    expect(can(null, PROFILE_EDIT)).toBe(false);
    expect(can(undefined, PROFILE_EDIT)).toBe(false);
    expect(can("superuser", PROFILE_EDIT)).toBe(false);
  });

  it("declares every permission the backend exports", () => {
    const declared = [
      JOBS_WRITE,
      CANDIDATES_ADD,
      PIPELINE_MOVE,
      FEEDBACK_SUBMIT,
      USERS_INVITE,
      USERS_CHANGE_ROLE,
      DELETE_RECORDS,
      SCORE_BEFORE_FEEDBACK,
      REPORTS_VIEW,
      TEMPLATES_MANAGE,
      PROFILE_EDIT,
      AUDIT_VIEW,
      DATA_EXPORT,
      DEPARTMENTS_MANAGE,
    ];
    expect([...declared].sort()).toEqual([...table.permissions].sort());
  });
});

describe("roleLabel", () => {
  it("uses the spec's terms", () => {
    expect(roleLabel("hiring_manager")).toBe("Hiring manager");
    expect(roleLabel("hiring_team")).toBe("Hiring team");
    expect(roleLabel("demo")).toBe("Read-only demo");
    expect(roleLabel(null)).toBe("Signed out");
  });
});
