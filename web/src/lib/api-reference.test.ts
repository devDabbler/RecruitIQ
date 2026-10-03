import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import rootSpec from "../../../openapi.json";
import committedSpec from "./openapi.json";
import {
  buildGroups,
  inlineCode,
  METHODS,
  paragraphs,
  plainText,
  schemaFields,
  typeLabel,
  UNTAGGED,
  type OpenApiSpec,
} from "./api-reference";

const realSpec = committedSpec as unknown as OpenApiSpec;

const spec: OpenApiSpec = {
  paths: {
    "/health": { get: { summary: "Health", responses: { "200": { description: "OK" } } } },
    "/api/jobs/{job_id}": {
      get: {
        summary: "Get Job",
        tags: ["jobs"],
        parameters: [
          { name: "job_id", in: "path", required: true, schema: { type: "integer" } },
          {
            name: "verbose",
            in: "query",
            schema: { anyOf: [{ type: "boolean" }, { type: "null" }] },
          },
        ],
        responses: {
          "200": {
            description: "Successful Response",
            content: { "application/json": { schema: { $ref: "#/components/schemas/JobOut" } } },
          },
          "422": {
            description: "Validation Error",
            content: {
              "application/json": { schema: { $ref: "#/components/schemas/HTTPValidationError" } },
            },
          },
        },
      },
      put: {
        summary: "Update Job",
        tags: ["jobs"],
        requestBody: {
          required: true,
          content: { "application/json": { schema: { $ref: "#/components/schemas/JobOut" } } },
        },
      },
    },
    "/api/cache/clear": { post: { summary: "Clear", tags: ["cache"] } },
    "/auth/login": { post: { summary: "Login", tags: ["auth"] } },
  },
  components: {
    schemas: {
      JobOut: {
        type: "object",
        required: ["id"],
        properties: {
          id: { type: "integer" },
          title: { type: "string", description: "Shown on the board — keep it short" },
          posted_at: { type: "string", format: "date-time" },
        },
      },
      HTTPValidationError: { type: "object", properties: { detail: { type: "array" } } },
    },
  },
};

describe("typeLabel", () => {
  it("names refs, unions, arrays, maps, and enums the way a developer writes them", () => {
    expect(typeLabel({ $ref: "#/components/schemas/JobOut" })).toBe("JobOut");
    expect(typeLabel({ anyOf: [{ type: "string" }, { type: "null" }] })).toBe("string | null");
    expect(typeLabel({ type: "array", items: { $ref: "#/x/Tag" } })).toBe("Tag[]");
    expect(
      typeLabel({ type: "array", items: { anyOf: [{ type: "string" }, { type: "integer" }] } }),
    ).toBe("(string | integer)[]");
    expect(typeLabel({ type: "object", additionalProperties: { type: "number" } })).toBe(
      "map of number",
    );
    expect(typeLabel({ type: "string", enum: ["a", "b"] })).toBe('"a" | "b"');
    expect(typeLabel({ type: "string", format: "binary" })).toBe("string (binary)");
    expect(typeLabel(undefined)).toBe("any");
  });
});

describe("text helpers", () => {
  it("rewraps hard-wrapped docstrings into paragraphs", () => {
    expect(paragraphs("One line\nwrapped here.\n\nSecond   para.")).toEqual([
      "One line wrapped here.",
      "Second para.",
    ]);
    expect(paragraphs(undefined)).toEqual([]);
  });

  it("never shows an em or en dash", () => {
    expect(plainText("a — b–c")).toBe("a - b - c");
  });

  it("splits inline code out of a sentence", () => {
    expect(inlineCode("route's `{id}` would win")).toEqual([
      { code: false, text: "route's " },
      { code: true, text: "{id}" },
      { code: false, text: " would win" },
    ]);
  });
});

describe("buildGroups", () => {
  const groups = buildGroups(spec);

  it("puts product groups first and operational ones after, untagged last alphabetically", () => {
    expect(groups.map((g) => g.tag)).toEqual(["auth", "jobs", "cache", UNTAGGED]);
    expect(groups.find((g) => g.tag === "jobs")?.label).toBe("Jobs");
  });

  it("describes parameters, request bodies, and success response fields", () => {
    const [get, put] = groups.find((g) => g.tag === "jobs")!.endpoints;
    expect(get.method).toBe("get");
    expect(get.id).toBe("get-api-jobs-job_id");
    expect(get.parameters).toEqual([
      { name: "job_id", location: "path", type: "integer", required: true, description: "" },
      {
        name: "verbose",
        location: "query",
        type: "boolean | null",
        required: false,
        description: "",
      },
    ]);
    const ok = get.responses.find((r) => r.status === "200")!;
    expect(ok.type).toBe("JobOut");
    expect(ok.fields.map((f) => `${f.name}:${f.type}:${f.required}`)).toEqual([
      "id:integer:true",
      "title:string:false",
      "posted_at:string (date-time):false",
    ]);
    expect(ok.fields[1].description).toBe("Shown on the board - keep it short");
    // Error bodies are named, not expanded.
    expect(get.responses.find((r) => r.status === "422")).toMatchObject({
      type: "HTTPValidationError",
      fields: [],
    });
    expect(put.body).toMatchObject({ contentType: "application/json", type: "JobOut" });
    expect(put.body?.fields).toHaveLength(3);
  });

  it("returns no fields for a schema that is not an object", () => {
    expect(schemaFields({ type: "string" }, spec)).toEqual([]);
  });
});

describe("the committed openapi.json", () => {
  const groups = buildGroups(realSpec);

  // The bundler cannot reach files outside web/, so /docs reads a copy.
  it("matches the backend's schema at the repo root (run `npm run types:api`)", () => {
    expect(committedSpec).toEqual(rootSpec);
  });
  const endpoints = groups.flatMap((g) => g.endpoints);

  it("documents every operation exactly once", () => {
    const expected = Object.values(realSpec.paths).reduce(
      (n, item) =>
        n + Object.keys(item).filter((k) => (METHODS as readonly string[]).includes(k)).length,
      0,
    );
    expect(
      Object.values(realSpec.paths)
        .flatMap(Object.keys)
        .every((k) => (METHODS as readonly string[]).includes(k)),
    ).toBe(true);
    expect(endpoints).toHaveLength(expected);
    expect(new Set(endpoints.map((e) => e.id)).size).toBe(expected);
  });

  it("starts with sign-in and the core hiring routes", () => {
    expect(groups.slice(0, 3).map((g) => g.tag)).toEqual(["auth", "jobs", "candidates"]);
  });

  it("puts no em or en dash anywhere on the page", () => {
    const text = JSON.stringify(
      groups.map((g) => ({
        ...g,
        endpoints: g.endpoints.map((e) => ({ ...e, description: paragraphs(e.description) })),
      })),
    );
    expect(text).not.toMatch(/[—–]/);
  });
});

describe("the footer API docs link", () => {
  it("points at a page that exists", () => {
    const appDir = fileURLToPath(new URL("../app/(app)/", import.meta.url));
    const layout = readFileSync(`${appDir}layout.tsx`, "utf8");
    expect(layout).toMatch(/href="\/docs"/);
    expect(existsSync(`${appDir}docs/page.tsx`)).toBe(true);
  });
});
