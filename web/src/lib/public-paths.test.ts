import { describe, expect, it } from "vitest";

import { isPublicPath } from "./public-paths";

describe("isPublicPath", () => {
  it("covers candidate status links and nothing else", () => {
    expect(isPublicPath("/c/abc123")).toBe(true);
    expect(isPublicPath("/c/abc123/extra")).toBe(true);
    expect(isPublicPath("/candidates")).toBe(false);
    expect(isPublicPath("/c")).toBe(false);
    expect(isPublicPath("/")).toBe(false);
  });
});
