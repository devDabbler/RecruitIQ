import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, apiFetchOptional } from "./api";
import { API_BASE_URL } from "./config";

/** The Request the module under test handed to `fetch`. */
function lastCall(): { url: string; init: RequestInit } {
  const mock = vi.mocked(globalThis.fetch);
  expect(mock).toHaveBeenCalled();
  const [url, init] = mock.mock.calls.at(-1)!;
  return { url: String(url), init: (init ?? {}) as RequestInit };
}

function respond(body: string, init: ResponseInit = {}): Response {
  return new Response(body, { status: 200, ...init });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch — request shaping", () => {
  it("prefixes the configured base URL", async () => {
    vi.mocked(fetch).mockResolvedValue(respond("{}"));
    await apiFetch("/api/candidates/");
    expect(lastCall().url).toBe(`${API_BASE_URL}/api/candidates/`);
  });

  it("appends query parameters and drops empty ones", async () => {
    vi.mocked(fetch).mockResolvedValue(respond("{}"));
    await apiFetch("/api/candidates/", {
      query: { q: "python", limit: 10, active: true, status: null, stage: undefined, note: "" },
    });

    const url = new URL(lastCall().url);
    expect(url.searchParams.get("q")).toBe("python");
    expect(url.searchParams.get("limit")).toBe("10");
    expect(url.searchParams.get("active")).toBe("true");
    // Dropping these matters: FastAPI validates an empty string against an enum
    // and 422s, so forwarding a blank filter would break search-as-you-type the
    // moment the user cleared the box.
    expect(url.searchParams.has("status")).toBe(false);
    expect(url.searchParams.has("stage")).toBe(false);
    expect(url.searchParams.has("note")).toBe(false);
  });

  it("sends the token as a bearer header, and omits the header without one", async () => {
    // A Response body can only be read once, so this case needs a fresh one per
    // call rather than a single shared `mockResolvedValue`.
    vi.mocked(fetch).mockImplementation(async () => respond("{}"));

    await apiFetch("/auth/me", { token: "jwt-123" });
    expect(new Headers(lastCall().init.headers).get("authorization")).toBe("Bearer jwt-123");

    await apiFetch("/auth/me", { token: null });
    expect(new Headers(lastCall().init.headers).has("authorization")).toBe(false);
  });

  it("serializes an object body as JSON and sets the content type", async () => {
    vi.mocked(fetch).mockResolvedValue(respond("{}"));
    await apiFetch("/api/assistant/chat", { method: "POST", body: { message: "hi" } });

    const { init } = lastCall();
    expect(init.body).toBe('{"message":"hi"}');
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
  });

  it("passes FormData through untouched", async () => {
    vi.mocked(fetch).mockResolvedValue(respond("{}"));
    const form = new FormData();
    form.set("file", new Blob(["résumé"]), "cv.pdf");

    await apiFetch("/api/resume/parse", { method: "POST", body: form });

    const { init } = lastCall();
    expect(init.body).toBe(form);
    // Setting it by hand would omit the multipart boundary and the upload would
    // fail to parse server-side; undici fills it in only when we stay out of it.
    expect(new Headers(init.headers).has("content-type")).toBe(false);
  });

  it("defaults to no-store so responses are never baked into the build", async () => {
    vi.mocked(fetch).mockResolvedValue(respond("{}"));
    await apiFetch("/api/candidates/");
    expect(lastCall().init.cache).toBe("no-store");
  });

  it("lets a caller override the cache mode", async () => {
    vi.mocked(fetch).mockResolvedValue(respond("{}"));
    await apiFetch("/api/jobs/", { cache: "force-cache" });
    expect(lastCall().init.cache).toBe("force-cache");
  });
});

describe("apiFetch — responses", () => {
  it("parses a JSON body", async () => {
    vi.mocked(fetch).mockResolvedValue(respond('{"total":2,"results":[]}'));
    await expect(apiFetch("/api/candidates/")).resolves.toEqual({ total: 2, results: [] });
  });

  it("returns undefined for 204 and for an empty 200", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(apiFetch("/api/candidates/1")).resolves.toBeUndefined();

    vi.mocked(fetch).mockResolvedValue(respond(""));
    await expect(apiFetch("/api/candidates/1")).resolves.toBeUndefined();
  });
});

describe("apiFetch — errors", () => {
  it("raises ApiError carrying status, detail and path", async () => {
    vi.mocked(fetch).mockResolvedValue(
      respond('{"detail":"Candidate not found"}', { status: 404 }),
    );

    const error = await apiFetch("/api/candidates/nope").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const api = error as ApiError;
    expect(api.status).toBe(404);
    expect(api.detail).toBe("Candidate not found");
    expect(api.path).toBe("/api/candidates/nope");
    expect(api.isNotFound).toBe(true);
    expect(api.isReadOnly).toBe(false);
  });

  it("flattens a 422 validation array into one readable line", async () => {
    vi.mocked(fetch).mockResolvedValue(
      respond(
        JSON.stringify({
          detail: [
            { loc: ["body", "email"], msg: "value is not a valid email address" },
            { loc: ["body", "role"], msg: "unexpected value" },
          ],
        }),
        { status: 422 },
      ),
    );

    const error = (await apiFetch("/auth/login").catch((e: unknown) => e)) as ApiError;
    // The whole point: a screen renders this string, so it must never come out
    // as "[object Object]".
    expect(error.detail).toBe(
      "body.email: value is not a valid email address; body.role: unexpected value",
    );
  });

  it("flags a 403 as the read-only gate", async () => {
    vi.mocked(fetch).mockResolvedValue(
      respond('{"detail":"This demo is read-only"}', { status: 403 }),
    );

    const error = (await apiFetch("/api/candidates/", { method: "POST" }).catch(
      (e: unknown) => e,
    )) as ApiError;
    expect(error.isReadOnly).toBe(true);
  });

  it("falls back to raw text when the error body is not JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(
      respond("<html>502 Bad Gateway</html>", { status: 502 }),
    );

    const error = (await apiFetch("/api/jobs/").catch((e: unknown) => e)) as ApiError;
    expect(error.detail).toBe("<html>502 Bad Gateway</html>");
  });

  it("falls back to the status text when the error body is empty", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("", { status: 500, statusText: "Internal Server Error" }),
    );

    const error = (await apiFetch("/api/jobs/").catch((e: unknown) => e)) as ApiError;
    expect(error.detail).toBe("Internal Server Error");
  });

  it("turns a refused connection into an actionable 503", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("fetch failed"));

    const error = (await apiFetch("/api/jobs/").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(503);
    expect(error.detail).toContain("Is uvicorn running?");
  });
});

describe("apiFetchOptional", () => {
  it("answers null for a 404", async () => {
    vi.mocked(fetch).mockResolvedValue(respond('{"detail":"gone"}', { status: 404 }));
    await expect(apiFetchOptional("/api/candidates/nope")).resolves.toBeNull();
  });

  it("still throws for any other status", async () => {
    vi.mocked(fetch).mockResolvedValue(respond('{"detail":"boom"}', { status: 500 }));
    await expect(apiFetchOptional("/api/candidates/1")).rejects.toBeInstanceOf(ApiError);
  });
});
