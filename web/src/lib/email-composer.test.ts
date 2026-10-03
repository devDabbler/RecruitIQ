import { describe, expect, it } from "vitest";

import {
  composeClipboardText,
  remainingPlaceholders,
  sendState,
  unknownPlaceholders,
} from "./email-composer";

describe("remainingPlaceholders", () => {
  it("lists unfilled markers once, in order", () => {
    expect(remainingPlaceholders("Hi {{a}}", "{{ b }} {{a}}")).toEqual(["a", "b"]);
    expect(remainingPlaceholders("All filled in.")).toEqual([]);
  });
});

describe("unknownPlaceholders", () => {
  it("flags markers outside the allowed list", () => {
    expect(unknownPlaceholders("{{job_title}} {{salary}}", ["job_title"])).toEqual(["salary"]);
  });
});

describe("composeClipboardText", () => {
  it("puts the subject on its own line above the body", () => {
    expect(composeClipboardText(" Hello ", "Body\n")).toBe("Subject: Hello\n\nBody\n");
  });
});

describe("sendState", () => {
  it("explains every reason sending is not available", () => {
    expect(sendState({ canSend: false, transportConfigured: true, remaining: [] }).allowed).toBe(false);
    expect(
      sendState({ canSend: true, transportConfigured: true, remaining: ["status_link"] }).reason,
    ).toBe("Fill in {{status_link}} first.");
    expect(
      sendState({ canSend: true, transportConfigured: false, remaining: [] }).reason,
    ).toMatch(/No mail server/);
    expect(sendState({ canSend: true, transportConfigured: true, remaining: [] })).toEqual({
      allowed: true,
      reason: null,
    });
  });
});
