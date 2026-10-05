import { describe, expect, it } from "vitest";

import type { JobPipeline } from "./domain";
import {
  MAX_BULK_FILES,
  applicationsByCandidate,
  bulkSummary,
  candidateNameFromParse,
  dataExportHref,
  describeError,
  exportHref,
  normalizeTag,
  queueFiles,
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
    const files = Array.from({ length: MAX_BULK_FILES + 2 }, (_, i) => ({ name: `${i}.pdf`, size: 1 }));
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
