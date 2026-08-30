import { describe, expect, it } from "vitest";

import { parseChatMarkdown } from "./chat-markdown";

describe("parseChatMarkdown", () => {
  it("passes plain text through untouched", () => {
    expect(parseChatMarkdown("No candidates in Boise right now.")).toEqual([
      { kind: "text", text: "No candidates in Boise right now." },
    ]);
  });

  it("turns candidate profile links into link segments", () => {
    const segments = parseChatMarkdown(
      "Top match: [Ava Chen](/candidates/a1b2-c3) with 92%.",
    );
    expect(segments).toEqual([
      { kind: "text", text: "Top match: " },
      { kind: "link", text: "Ava Chen", href: "/candidates/a1b2-c3" },
      { kind: "text", text: " with 92%." },
    ]);
  });

  it("accepts job links", () => {
    expect(parseChatMarkdown("[Data Engineer](/jobs/24)")).toEqual([
      { kind: "link", text: "Data Engineer", href: "/jobs/24" },
    ]);
  });

  it("demotes external and unknown targets to plain text", () => {
    expect(parseChatMarkdown("[click](https://evil.example)")).toEqual([
      { kind: "text", text: "click" },
    ]);
    expect(parseChatMarkdown("[admin](/admin/users)")).toEqual([
      { kind: "text", text: "admin" },
    ]);
    expect(parseChatMarkdown("[nested](/candidates/x/resume)")).toEqual([
      { kind: "text", text: "nested" },
    ]);
  });

  it("parses bold spans", () => {
    expect(parseChatMarkdown("Score: **92%** overall")).toEqual([
      { kind: "text", text: "Score: " },
      { kind: "bold", text: "92%" },
      { kind: "text", text: " overall" },
    ]);
  });

  it("handles multiple tokens across lines", () => {
    const segments = parseChatMarkdown(
      "1. [Ava Chen](/candidates/a1) **88%**\n2. [Bo Diaz](/candidates/b2) **81%**",
    );
    expect(segments.filter((s) => s.kind === "link")).toHaveLength(2);
    expect(segments.filter((s) => s.kind === "bold")).toHaveLength(2);
  });
});
