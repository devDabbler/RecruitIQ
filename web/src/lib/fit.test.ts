import { describe, expect, it } from "vitest";

import { FIT_HIDDEN_TITLE, byFit, capReason, fitDisplay, fitQuery, fitSortFrom } from "./fit";

describe("fitDisplay", () => {
  it("shows a dash, never a number, while the score is hidden", () => {
    const shown = fitDisplay({ score: null, hidden: true, capped: false, missing: [] });
    expect(shown.text).toBe("-");
    expect(shown.title).toBe(FIT_HIDDEN_TITLE);
    expect(fitDisplay(null).title).toBe("Not scored");
  });

  it("rounds and bands the score", () => {
    expect(fitDisplay({ score: 82.4, hidden: false, capped: false, missing: [] })).toMatchObject({
      text: "82",
      tone: "strong",
    });
    expect(fitDisplay({ score: 55, hidden: false, capped: false, missing: [] }).tone).toBe(
      "moderate",
    );
    expect(fitDisplay({ score: 12.6, hidden: false, capped: false, missing: [] }).tone).toBe(
      "weak",
    );
  });

  it("says why a score was capped", () => {
    const shown = fitDisplay({
      score: 70,
      hidden: false,
      capped: true,
      missing: ["must-have skill Rust", "must-have skill Go"],
    });
    expect(shown.capped).toBe(true);
    expect(shown.title).toBe(
      "Fit 70 out of 100. Capped because they are missing must-have skill Rust and must-have skill Go.",
    );
  });

  it("mentions a missing requirement that did not need to cap", () => {
    const shown = fitDisplay({
      score: 40,
      hidden: false,
      capped: false,
      missing: ["must-have skill Rust"],
    });
    expect(shown.capped).toBe(false);
    expect(shown.title).toBe("Fit 40 out of 100. Missing must-have skill Rust.");
  });
});

describe("capReason", () => {
  it("names what is missing in a few words", () => {
    expect(capReason(["must-have skill Docker"])).toBe("missing Docker");
    expect(capReason(["must-have skill Python", "at least 5 years of experience"])).toBe(
      "missing Python, at least 5 years of experience",
    );
    expect(capReason([])).toBe("a requirement is missing");
  });
});

describe("byFit", () => {
  it("ranks best first and keeps unscored and hidden rows last in their order", () => {
    const rows = [
      { id: "hidden", fit: { score: null, hidden: true, capped: false, missing: [] } },
      { id: "low", fit: { score: 20, hidden: false, capped: false, missing: [] } },
      { id: "none", fit: null },
      { id: "high", fit: { score: 90, hidden: false, capped: false, missing: [] } },
    ];
    expect(byFit(rows, (r) => r.fit).map((r) => r.id)).toEqual(["high", "low", "hidden", "none"]);
  });
});

describe("fit sort", () => {
  it("defaults to best first", () => {
    expect(fitSortFrom(undefined)).toBe("best");
    expect(fitSortFrom("nonsense")).toBe("best");
    expect(fitQuery(fitSortFrom("worst"))).toEqual({ sortBy: "fit", sortOrder: "asc" });
    expect(fitQuery("best")).toEqual({ sortBy: "fit", sortOrder: "desc" });
  });
});
