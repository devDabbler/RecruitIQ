import { describe, expect, it } from "vitest";

import { ASSISTANT_CAN, ASSISTANT_LIMITS } from "./assistant-guide";

const allCopy = [
  ...ASSISTANT_CAN.flatMap((item) => [item.title, item.example]),
  ...ASSISTANT_LIMITS,
];

describe("assistant guide", () => {
  it("lists both what the assistant does and where it stops", () => {
    expect(ASSISTANT_CAN.length).toBeGreaterThanOrEqual(4);
    expect(ASSISTANT_LIMITS.length).toBeGreaterThanOrEqual(3);
  });

  it("states that the assistant is read-only and limited to this database", () => {
    const limits = ASSISTANT_LIMITS.join(" ");
    expect(limits).toMatch(/read-only/i);
    expect(limits).toMatch(/demo database/);
  });

  it("uses no em or en dashes in visible copy", () => {
    for (const line of allCopy) {
      expect(line).not.toMatch(/[–—―]/);
    }
  });
});
