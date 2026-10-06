/**
 * Pure rules for the ATS Phase C screens: tags, errors, export links, bulk
 * results, and the bulk upload queue. No React and no fetch, so every rule
 * here has a unit test.
 */
import type { JobPipeline } from "./domain";
import { type ApplicantFit, byFit } from "./fit";

export const MAX_TAGS_PER_CANDIDATE = 20;
export const MAX_BULK_FILES = 20;
export const MAX_FILE_BYTES = 8 * 1024 * 1024;

/**
 * Mirror of backend/utils/tags.py::normalize_tag, pinned by the same cases.
 * Returns "" where the server would refuse the tag.
 */
export function normalizeTag(raw: string): string {
  const slug = raw
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\+/g, "plus")
    .replace(/#/g, "sharp")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug.slice(0, 50).replace(/-+$/, "");
}

/** FastAPI's detail is a string for HTTPException and a list for a 422. */
export function describeError(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        const e = item as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(e.loc) && e.loc.length ? String(e.loc[e.loc.length - 1]) : "";
        return field ? `${field}: ${e.msg ?? "invalid"}` : (e.msg ?? "invalid");
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

export interface CandidateExportQuery {
  keyword?: string;
  status?: string;
  jobId?: string;
  tags?: string[];
}

/** The CSV link for whatever the candidates list is currently filtered to. */
export function exportHref({ keyword, status, jobId, tags }: CandidateExportQuery): string {
  const query = new URLSearchParams();
  if (keyword) query.set("keyword", keyword);
  if (status) query.set("status", status);
  if (jobId) query.set("job_id", jobId);
  for (const tag of tags ?? []) query.append("tag", tag);
  const qs = query.toString();
  return qs ? `/api/candidates/export?${qs}` : "/api/candidates/export";
}

/** The download link for everything held about one candidate (pilot plan Track 1 #5). */
export function dataExportHref(candidateId: string, format: "json" | "text"): string {
  const base = `/api/candidates/${encodeURIComponent(candidateId)}/data-export`;
  return format === "text" ? `${base}?format=text` : base;
}

export interface ActiveApplication {
  applicationId: number;
  stageName: string;
}

/** Candidate id to their in-progress application on this job, read off the board. */
export function applicationsByCandidate(pipeline: JobPipeline): Record<string, ActiveApplication> {
  const out: Record<string, ActiveApplication> = {};
  for (const column of pipeline.columns) {
    for (const card of column.applications) {
      out[card.candidate_id] = { applicationId: card.application_id, stageName: column.stage_name };
    }
  }
  return out;
}

export function bulkSummary(
  action: "advance" | "reject",
  succeeded: number,
  failed: number,
): string {
  const verb = action === "advance" ? "Advanced" : "Rejected";
  const moved = `${verb} ${succeeded} ${succeeded === 1 ? "candidate" : "candidates"}.`;
  if (failed === 0) return moved;
  return `${moved} ${failed} could not be ${action === "advance" ? "advanced" : "rejected"}.`;
}

/**
 * Shown under every tag input (Track 2 Phase 5). Tags are free text, so the
 * one rule that keeps them lawful is said where people type them.
 */
export const TAG_GUIDANCE =
  "Tag skills, availability, or follow-ups. Never tag pay, health, age, or any protected trait.";

/** How many tag chips the candidates filter shows before the rest are left out. */
export const TAG_FILTER_CHIPS = 12;

/**
 * The tag chips for the candidates filter: the most used tags, plus any
 * selected tag that would not otherwise make the cut, so a selection can
 * always be cleared. Keeps the API's most-used-first order.
 */
export function tagFilterChips(
  counts: { tag: string; count: number }[],
  selected: string[],
  limit: number = TAG_FILTER_CHIPS,
): { tag: string; count: number | null }[] {
  const top: { tag: string; count: number | null }[] = counts.slice(0, limit);
  const shown = new Set(top.map((c) => c.tag));
  for (const tag of selected) {
    if (shown.has(tag)) continue;
    const known = counts.find((c) => c.tag === tag);
    top.push({ tag, count: known ? known.count : null });
    shown.add(tag);
  }
  return top;
}

/** The selected tags after clicking one chip: on if it was off, off if it was on. */
export function toggleTag(selected: string[], tag: string): string[] {
  return selected.includes(tag) ? selected.filter((t) => t !== tag) : [...selected, tag];
}

/** What the bulk bar says about the current selection. `jobTitle` null: no job filter. */
export function selectionLabel(selected: number, movable: number, jobTitle: string | null): string {
  if (selected === 0) {
    return jobTitle
      ? `Select candidates to tag them, or to move them together in ${jobTitle}.`
      : "Select candidates to tag them together.";
  }
  const picked = `${selected} selected`;
  if (!jobTitle) return picked;
  return movable === selected
    ? `${picked} in ${jobTitle}`
    : `${picked}, ${movable} in progress in ${jobTitle}`;
}

/** The line after a bulk tag, like bulkSummary for moves. */
export function bulkTagSummary(tag: string, succeeded: number, failed: number): string {
  const done = `Tagged ${succeeded} ${succeeded === 1 ? "candidate" : "candidates"} ${tag}.`;
  if (failed === 0) return done;
  return `${done} ${failed} could not be tagged.`;
}

export type UploadStatus = "queued" | "parsing" | "saving" | "done" | "failed";

export interface UploadItem {
  id: string;
  /** Position in the files the user picked, used to find the File again. */
  index: number;
  fileName: string;
  status: UploadStatus;
  candidateName?: string;
  candidateId?: string;
  detail?: string;
  /** Track 2 Phase 2: how well the saved applicant fits the job. */
  fit?: ApplicantFit | null;
}

/**
 * The progress list once a batch has finished: everyone added, best fit
 * first, then the files that were not added. While a batch runs the list
 * stays in file order so rows do not jump under the cursor.
 */
export function rankedUploads(items: UploadItem[]): UploadItem[] {
  const added = items.filter((item) => item.status === "done");
  const rest = items.filter((item) => item.status !== "done");
  return [...byFit(added, (item) => item.fit), ...rest];
}

/** Which picked files will be uploaded, and a reason for each one that will not. */
export function queueFiles(files: { name: string; size: number }[]): {
  items: UploadItem[];
  skipped: string[];
} {
  const items: UploadItem[] = [];
  const skipped: string[] = [];
  files.forEach((file, index) => {
    if (file.size === 0) {
      skipped.push(`${file.name}: the file is empty`);
    } else if (file.size > MAX_FILE_BYTES) {
      skipped.push(`${file.name}: larger than 8 MB`);
    } else if (items.length >= MAX_BULK_FILES) {
      skipped.push(`${file.name}: only ${MAX_BULK_FILES} files per batch`);
    } else {
      items.push({ id: `${index}:${file.name}`, index, fileName: file.name, status: "queued" });
    }
  });
  return { items, skipped };
}

export function updateItem(
  items: UploadItem[],
  id: string,
  patch: Partial<UploadItem>,
): UploadItem[] {
  return items.map((item) => (item.id === id ? { ...item, ...patch } : item));
}

export function uploadProgress(items: UploadItem[]): {
  total: number;
  done: number;
  failed: number;
  finished: boolean;
} {
  const done = items.filter((i) => i.status === "done").length;
  const failed = items.filter((i) => i.status === "failed").length;
  return {
    total: items.length,
    done,
    failed,
    finished: items.length > 0 && done + failed === items.length,
  };
}

/** The person's name from a parse response, wherever this parser path put it. */
export function candidateNameFromParse(payload: {
  personal_info?: Record<string, unknown> | null;
  parsed_data?: Record<string, unknown> | null;
}): string | null {
  const direct = payload.personal_info?.name;
  const nested = (payload.parsed_data?.personal_info as Record<string, unknown> | undefined)?.name;
  const name = typeof direct === "string" && direct.trim() ? direct : nested;
  return typeof name === "string" && name.trim() ? name.trim() : null;
}
