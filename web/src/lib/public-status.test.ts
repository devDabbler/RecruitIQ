import { describe, expect, it } from "vitest";

import type { PublicStatus } from "./domain";
import { PUBLIC_STATE_LABELS, currentStageName, greeting, looksLikeToken } from "./public-status";

const STATUS: PublicStatus = {
  first_name: "Mira",
  job_title: "Platform Engineer",
  department: "Engineering",
  status: "In progress",
  stages: [
    { name: "Resume submitted", description: null, state: "done" },
    { name: "Hiring manager review", description: "Review.", state: "current" },
  ],
};

describe("public status helpers", () => {
  it("greets by first name, or politely without one", () => {
    expect(greeting("Mira")).toBe("Hi Mira,");
    expect(greeting("  ")).toBe("Hello,");
    expect(greeting(null)).toBe("Hello,");
  });

  it("finds the current stage", () => {
    expect(currentStageName(STATUS)).toBe("Hiring manager review");
    expect(currentStageName({ ...STATUS, stages: [] })).toBeNull();
  });

  it("only calls the API for token-shaped values", () => {
    expect(looksLikeToken("abcdefghijklmnopqrstuvwxyz012345")).toBe(true);
    expect(looksLikeToken("short")).toBe(false);
    expect(looksLikeToken("../../etc/passwd-xxxxxxxxxxxx")).toBe(false);
  });

  it("labels every state in plain English", () => {
    expect(PUBLIC_STATE_LABELS.current).toBe("In progress");
    expect(PUBLIC_STATE_LABELS.closed).toBe("Closed");
  });
});
