import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SESSION_COOKIE } from "./config";

const cookieStore = { get: vi.fn() };
vi.mock("next/headers", () => ({ cookies: async () => cookieStore }));

const { canWrite, getToken, getUser } = await import("./session");

function setCookie(value: string | undefined) {
  cookieStore.get.mockImplementation((name: string) =>
    name === SESSION_COOKIE && value !== undefined ? { name, value } : undefined,
  );
}

const DEMO_USER = {
  id: "b8f2c0e4-0000-4000-8000-000000000001",
  email: "demo@recruitiq.dev",
  role: "demo" as const,
  created_at: "2026-08-27T00:00:00Z",
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  cookieStore.get.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getToken", () => {
  it("returns the JWT from the session cookie", async () => {
    setCookie("jwt-abc");
    await expect(getToken()).resolves.toBe("jwt-abc");
  });

  it("returns null when the request carried no session cookie", async () => {
    setCookie(undefined);
    await expect(getToken()).resolves.toBeNull();
  });
});

describe("getUser", () => {
  it("asks the API rather than decoding the token locally", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(DEMO_USER)));

    await expect(getUser()).resolves.toEqual(DEMO_USER);

    // An unverified local decode is not an authentication check, so /auth/me
    // being called is the behaviour under test, not an implementation detail.
    const [url, init] = vi.mocked(fetch).mock.calls.at(-1)!;
    expect(String(url)).toMatch(/\/auth\/me$/);
    expect(new Headers((init as RequestInit).headers).get("authorization")).toBe("Bearer jwt-abc");
  });

  it("returns null without calling the API when there is no token", async () => {
    setCookie(undefined);
    await expect(getUser()).resolves.toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("treats an expired or rejected token as signed out", async () => {
    setCookie("expired");
    vi.mocked(fetch).mockResolvedValue(
      new Response('{"detail":"Token has expired"}', { status: 401 }),
    );
    // Throwing here would 500 the page; proxy.ts mints a fresh demo token on
    // the next request, so signed-out is the correct render.
    await expect(getUser()).resolves.toBeNull();
  });

  it("treats an unreachable API as signed out", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockRejectedValue(new TypeError("fetch failed"));
    await expect(getUser()).resolves.toBeNull();
  });
});

describe("canWrite", () => {
  it("is false for the demo role", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(DEMO_USER)));
    await expect(canWrite()).resolves.toBe(false);
  });

  it("is true for an admin", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ...DEMO_USER, role: "admin" })),
    );
    await expect(canWrite()).resolves.toBe(true);
  });

  it("is false when signed out", async () => {
    setCookie(undefined);
    await expect(canWrite()).resolves.toBe(false);
  });
});
