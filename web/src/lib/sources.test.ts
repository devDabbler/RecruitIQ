import { describe, expect, it } from "vitest";

import openapi from "./openapi.json";
import { DEFAULT_SOURCE, SOURCE_OPTIONS, sourceLabel } from "./sources";

describe("application sources", () => {
  it("lists exactly the API's ApplicationSource values", () => {
    const schemas = (openapi as { components: { schemas: Record<string, { enum?: string[] }> } })
      .components.schemas;
    const fromApi = [...(schemas.ApplicationSource.enum ?? [])].sort();
    expect(SOURCE_OPTIONS.map((option) => option.value).sort()).toEqual(fromApi);
  });

  it("defaults to applied directly", () => {
    expect(SOURCE_OPTIONS.some((option) => option.value === DEFAULT_SOURCE)).toBe(true);
  });

  it("labels known, unknown, and missing sources", () => {
    expect(sourceLabel("company_website")).toBe("Company website");
    expect(sourceLabel("internal")).toBe("Internal");
    expect(sourceLabel(null)).toBe("Not recorded");
    expect(sourceLabel("unknown")).toBe("Not recorded");
    expect(sourceLabel("billboard")).toBe("Other");
  });
});
