import { describe, expect, it } from "vitest";

import {
  anonymousAction,
  dashboardDataNote,
  footerNote,
  loginIntro,
  loginPath,
  loginTitle,
  parseDeploymentMode,
  signedOutLabel,
} from "./deployment";

describe("parseDeploymentMode", () => {
  it("defaults to public so recruitiq.io needs no new setting", () => {
    expect(parseDeploymentMode(undefined)).toBe("public");
    expect(parseDeploymentMode("")).toBe("public");
    expect(parseDeploymentMode("public")).toBe("public");
  });

  it("accepts internal in any case", () => {
    expect(parseDeploymentMode("internal")).toBe("internal");
    expect(parseDeploymentMode(" Internal ")).toBe("internal");
  });

  it("refuses a typo instead of silently running public", () => {
    expect(() => parseDeploymentMode("internl")).toThrow(/DEPLOYMENT_MODE/);
  });
});

describe("anonymousAction", () => {
  it("mints a demo session for every app page in public mode", () => {
    expect(anonymousAction("/", "public")).toBe("mint-demo");
    expect(anonymousAction("/candidates", "public")).toBe("mint-demo");
    expect(anonymousAction("/login", "public")).toBe("mint-demo");
  });

  it("sends a signed-out visitor to sign in on an internal install", () => {
    expect(anonymousAction("/", "internal")).toBe("login");
    expect(anonymousAction("/candidates/abc", "internal")).toBe("login");
    expect(anonymousAction("/transparency", "internal")).toBe("login");
    expect(anonymousAction("/docs", "internal")).toBe("login");
    expect(anonymousAction("/api/candidates", "internal")).toBe("login");
  });

  it("keeps the sign-in page and its route handlers reachable when internal", () => {
    expect(anonymousAction("/login", "internal")).toBe("pass");
    expect(anonymousAction("/api/auth/login", "internal")).toBe("pass");
    expect(anonymousAction("/api/auth/logout", "internal")).toBe("pass");
  });

  it("never touches a candidate status link in either mode", () => {
    expect(anonymousAction("/c/sometoken", "public")).toBe("pass");
    expect(anonymousAction("/c/sometoken", "internal")).toBe("pass");
  });
});

describe("loginPath", () => {
  it("remembers where the visitor was going", () => {
    expect(loginPath("/candidates/abc", "?tab=notes")).toBe(
      "/login?next=%2Fcandidates%2Fabc%3Ftab%3Dnotes",
    );
  });

  it("drops a pointless next for the home page", () => {
    expect(loginPath("/")).toBe("/login");
  });
});

describe("mode-specific copy", () => {
  const copy = (mode: "public" | "internal") => [
    footerNote(mode),
    loginTitle(mode),
    loginIntro(mode),
    dashboardDataNote(mode),
    signedOutLabel(mode),
  ];

  it("talks about the demo only in public mode", () => {
    expect(copy("public").join(" ")).toMatch(/demo/i);
    expect(copy("internal").join(" ")).not.toMatch(/demo/i);
  });

  it("carries no em dashes", () => {
    for (const line of [...copy("public"), ...copy("internal")]) {
      expect(line).not.toContain("—");
    }
  });
});
