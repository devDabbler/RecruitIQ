/**
 * Pure rules for the ATS Phase C screens: tags, errors, export links, bulk
 * results, and the bulk upload queue. No React and no fetch, so every rule
 * here has a unit test.
 */
import type { JobPipeline } from "./domain";

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
}

/** The CSV link for whatever the candidates list is currently filtered to. */
export function exportHref({ keyword, status, jobId }: CandidateExportQuery): string {
  const query = new URLSearchParams();
  if (keyword) query.set("keyword", keyword);
  if (status) query.set("status", status);
  if (jobId) query.set("job_id", jobId);
  const qs = query.toString();
  return qs ? `/api/candidates/export?${qs}` : "/api/candidates/export";
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

export function bulkSummary(action: "advance" | "reject", succeeded: number, failed: number): string {
  const verb = action === "advance" ? "Advanced" : "Rejected";
  const moved = `${verb} ${succeeded} ${succeeded === 1 ? "candidate" : "candidates"}.`;
  if (failed === 0) return moved;
  return `${moved} ${failed} could not be ${action === "advance" ? "advanced" : "rejected"}.`;
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

export function updateItem(items: UploadItem[], id: string, patch: Partial<UploadItem>): UploadItem[] {
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
  return { total: items.length, done, failed, finished: items.length > 0 && done + failed === items.length };
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
