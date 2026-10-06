import { describe, expect, it } from "vitest";

import type { JobPipeline } from "./domain";
import {
  MAX_BULK_FILES,
  applicationsByCandidate,
  TAG_GUIDANCE,
  bulkSummary,
  bulkTagSummary,
  candidateNameFromParse,
  dataExportHref,
  describeError,
  exportHref,
  normalizeTag,
  queueFiles,
  rankedUploads,
  selectionLabel,
  tagFilterChips,
  toggleTag,
  updateItem,
  uploadProgress,
} from "./intake";

// Same table as backend/tests/test_notes_tags.py::TAG_CASES.
const TAG_CASES: [string, string][] = [
  ["Relocation OK", "relocation-ok"],
  ["  strong   SQL!! ", "strong-sql"],
  ["C++", "cplusplus"],
  ["C# developer", "csharp-developer"],
  ["Señor engineer", "senor-engineer"],
  ["already-kebab", "already-kebab"],
  ["--x--", "x"],
  ["a".repeat(80), "a".repeat(50)],
];

describe("normalizeTag", () => {
  it.each(TAG_CASES)("%s -> %s", (raw, expected) => {
    expect(normalizeTag(raw)).toBe(expected);
  });

  it("returns an empty string when nothing usable is left", () => {
    expect(normalizeTag("!!!")).toBe("");
  });
});

describe("describeError", () => {
  it("passes a string detail through", () => {
    expect(describeError("Job not found", 404)).toBe("Job not found");
  });

  it("flattens a 422 list into field: message", () => {
    expect(
      describeError([{ loc: ["body", "email"], msg: "value is not a valid email address" }], 422),
    ).toBe("email: value is not a valid email address");
  });

  it("falls back to the status", () => {
    expect(describeError(undefined, 500)).toBe("Request failed (500)");
  });
});

describe("exportHref", () => {
  it("passes only the filters that are set", () => {
    expect(exportHref({})).toBe("/api/candidates/export");
    expect(exportHref({ keyword: "sql", jobId: "7" })).toBe(
      "/api/candidates/export?keyword=sql&job_id=7",
    );
  });

  it("repeats every tag, since the export must match them all", () => {
    expect(exportHref({ tags: ["relocation-ok", "strong-sql"] })).toBe(
      "/api/candidates/export?tag=relocation-ok&tag=strong-sql",
    );
  });
});

describe("tag filter", () => {
  const counts = Array.from({ length: 15 }, (_, i) => ({ tag: `t${i}`, count: 15 - i }));

  it("shows the most used tags in the API's order", () => {
    expect(tagFilterChips(counts, [], 3)).toEqual([
      { tag: "t0", count: 15 },
      { tag: "t1", count: 14 },
      { tag: "t2", count: 13 },
    ]);
  });

  it("keeps a selected tag visible even when it is not in the top", () => {
    const chips = tagFilterChips(counts, ["t1", "t14", "gone"], 3);
    expect(chips.map((c) => c.tag)).toEqual(["t0", "t1", "t2", "t14", "gone"]);
    expect(chips.at(-1)).toEqual({ tag: "gone", count: null });
  });

  it("toggles one tag on and off", () => {
    expect(toggleTag([], "a")).toEqual(["a"]);
    expect(toggleTag(["a", "b"], "a")).toEqual(["b"]);
  });
});

describe("bulk tag wording", () => {
  it("counts in plain English", () => {
    expect(bulkTagSummary("relocation-ok", 1, 0)).toBe("Tagged 1 candidate relocation-ok.");
    expect(bulkTagSummary("x", 3, 1)).toBe("Tagged 3 candidates x. 1 could not be tagged.");
  });

  it("says who can be moved when some of the selection is not in the job", () => {
    expect(selectionLabel(0, 0, null)).toBe("Select candidates to tag them together.");
    expect(selectionLabel(2, 0, null)).toBe("2 selected");
    expect(selectionLabel(2, 2, "Analyst")).toBe("2 selected in Analyst");
    expect(selectionLabel(3, 1, "Analyst")).toBe("3 selected, 1 in progress in Analyst");
  });

  it("warns against tagging protected traits, without an em dash", () => {
    expect(TAG_GUIDANCE).toMatch(/protected trait/);
    expect(TAG_GUIDANCE).not.toMatch(/\u2014/);
  });
});

describe("dataExportHref", () => {
  it("points at the per-candidate download in either format", () => {
    const id = "6f1c2d3e-0000-4000-8000-000000000001";
    expect(dataExportHref(id, "json")).toBe(`/api/candidates/${id}/data-export`);
    expect(dataExportHref(id, "text")).toBe(`/api/candidates/${id}/data-export?format=text`);
  });
});

describe("applicationsByCandidate", () => {
  it("maps each in-progress candidate to their application and stage", () => {
    const pipeline = {
      job_id: 1,
      stages: [],
      outcomes: {},
      columns: [
        {
          stage_key: "resume_submitted",
          stage_name: "Resume submitted",
          applications: [{ application_id: 10, candidate_id: "a", candidate_name: "A" }],
        },
        {
          stage_key: "hm_review",
          stage_name: "Hiring manager review",
          applications: [{ application_id: 11, candidate_id: "b", candidate_name: "B" }],
        },
      ],
    } as unknown as JobPipeline;
    expect(applicationsByCandidate(pipeline)).toEqual({
      a: { applicationId: 10, stageName: "Resume submitted" },
      b: { applicationId: 11, stageName: "Hiring manager review" },
    });
  });
});

describe("bulkSummary", () => {
  it("counts in plain English", () => {
    expect(bulkSummary("advance", 1, 0)).toBe("Advanced 1 candidate.");
    expect(bulkSummary("reject", 3, 2)).toBe("Rejected 3 candidates. 2 could not be rejected.");
  });
});

describe("bulk upload queue", () => {
  it("queues valid files and explains the rest", () => {
    const files = [
      { name: "a.pdf", size: 1000 },
      { name: "empty.pdf", size: 0 },
      { name: "huge.pdf", size: 9 * 1024 * 1024 },
    ];
    const { items, skipped } = queueFiles(files);
    expect(items.map((i) => [i.fileName, i.index, i.status])).toEqual([["a.pdf", 0, "queued"]]);
    expect(skipped).toEqual(["empty.pdf: the file is empty", "huge.pdf: larger than 8 MB"]);
  });

  it("caps a batch", () => {
    const files = Array.from({ length: MAX_BULK_FILES + 2 }, (_, i) => ({
      name: `${i}.pdf`,
      size: 1,
    }));
    const { items, skipped } = queueFiles(files);
    expect(items).toHaveLength(MAX_BULK_FILES);
    expect(skipped).toHaveLength(2);
  });

  it("updates one item and reports progress", () => {
    const { items } = queueFiles([
      { name: "a.pdf", size: 1 },
      { name: "b.pdf", size: 1 },
    ]);
    const next = updateItem(updateItem(items, items[0].id, { status: "done" }), items[1].id, {
      status: "failed",
      detail: "Parsing failed",
    });
    expect(next[0].status).toBe("done");
    expect(next[1].detail).toBe("Parsing failed");
    expect(uploadProgress(next)).toEqual({ total: 2, done: 1, failed: 1, finished: true });
    expect(uploadProgress(items).finished).toBe(false);
  });
});

describe("candidateNameFromParse", () => {
  it("prefers personal_info.name, then parsed_data", () => {
    expect(candidateNameFromParse({ personal_info: { name: " Ada " } })).toBe("Ada");
    expect(candidateNameFromParse({ parsed_data: { personal_info: { name: "Grace" } } })).toBe(
      "Grace",
    );
    expect(candidateNameFromParse({})).toBeNull();
  });
});

describe("rankedUploads", () => {
  const fit = (score: number | null, hidden = false) => ({
    score,
    hidden,
    capped: false,
    missing: [],
  });

  it("puts everyone added first, best fit first, then the files not added", () => {
    const items = [
      { id: "a", index: 0, fileName: "a.pdf", status: "done" as const, fit: fit(40) },
      { id: "b", index: 1, fileName: "b.pdf", status: "failed" as const },
      { id: "c", index: 2, fileName: "c.pdf", status: "done" as const, fit: fit(88) },
      { id: "d", index: 3, fileName: "d.pdf", status: "done" as const, fit: null },
      { id: "e", index: 4, fileName: "e.pdf", status: "done" as const, fit: fit(61) },
    ];
    expect(rankedUploads(items).map((i) => i.id)).toEqual(["c", "e", "a", "d", "b"]);
  });
});
