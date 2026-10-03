import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE } from "./config";

const cookieStore = { get: vi.fn() };
vi.mock("next/headers", () => ({ cookies: async () => cookieStore }));

const { forwardWrite } = await import("./forward");

function setCookie(value: string | undefined) {
  cookieStore.get.mockImplementation((name: string) =>
    name === SESSION_COOKIE && value !== undefined ? { name, value } : undefined,
  );
}

function request(body?: unknown): NextRequest {
  return new Request("http://localhost/api/x", {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  }) as unknown as NextRequest;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  cookieStore.get.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("forwardWrite", () => {
  it("refuses without a session and never calls the API", async () => {
    setCookie(undefined);
    const response = await forwardWrite(request({}), "/api/team/users", "POST");
    expect(response.status).toBe(401);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("attaches the bearer token and passes the API's status and body through", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(new Response('{"detail":"Your role cannot do this."}', { status: 403 }));
    const response = await forwardWrite(request({ role: "admin" }), "/api/team/users", "POST");
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ detail: "Your role cannot do this." });
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toMatch(/\/api\/team\/users$/);
    expect(new Headers((init as RequestInit).headers).get("authorization")).toBe("Bearer jwt-abc");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ role: "admin" });
  });

  it("sends no body on DELETE", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(new Response('{"message":"ok"}', { status: 200 }));
    await forwardWrite(request(), "/api/interviews/3", "DELETE");
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init as RequestInit).body).toBeUndefined();
  });

  it("reports an unreachable API as 503", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockRejectedValue(new TypeError("fetch failed"));
    const response = await forwardWrite(request({}), "/api/team/me", "PUT");
    expect(response.status).toBe(503);
  });
});
