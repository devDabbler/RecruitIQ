/**
 * Wording, visibility, and small arithmetic for the dashboard and Reports.
 *
 * Pure so it can be unit tested without rendering. Every number handed to
 * these functions came from a query in reports_service.py; nothing here
 * invents one.
 */
import type { ActivityEvent } from "./domain";
import { can, REPORTS_VIEW } from "./permissions";
import type { Role } from "./session";

/** Phase C's CSV export route handler. Reports links to it rather than exporting twice. */
export const CANDIDATE_EXPORT_PATH = "/api/candidates/export";

/**
 * Reports are for the hiring roles, and for the read-only demo so a visitor
 * sees every screen. Interviewers are out: they work from their own list.
 */
export function canViewReports(role: Role | null | undefined): boolean {
  if (!role) return false;
  return role === "demo" || can(role, REPORTS_VIEW);
}

export function formatDays(days: number | null | undefined): string {
  if (days === null || days === undefined) return "No completed stages yet";
  if (days < 1) return "Under a day";
  const rounded = days < 10 ? Math.round(days * 10) / 10 : Math.round(days);
  return `${rounded} ${rounded === 1 ? "day" : "days"}`;
}

export function formatShare(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function daysLabel(days: number): string {
  return days === 1 ? "1 day" : `${days} days`;
}

export function funnelWidth(value: number, largest: number): string {
  return `${largest > 0 ? (value / largest) * 100 : 0}%`;
}

export function exportHref(jobId?: number | null): string {
  return jobId ? `${CANDIDATE_EXPORT_PATH}?job_id=${jobId}` : CANDIDATE_EXPORT_PATH;
}

/** The part of an activity line after the candidate's name. */
export function activityPredicate(
  event: Pick<ActivityEvent, "kind" | "job_title"> & { stage_name?: string | null },
): string {
  const stage = event.stage_name ?? "a stage";
  switch (event.kind) {
    case "applied":
      return `applied to ${event.job_title}`;
    case "passed":
      return `passed ${stage} for ${event.job_title}`;
    case "skipped":
      return `skipped ${stage} for ${event.job_title}`;
    case "rejected":
      return `was rejected at ${stage} for ${event.job_title}`;
    case "hired":
      return `was hired as ${event.job_title}`;
    case "declined":
      return `declined the offer for ${event.job_title}`;
    default:
      return `moved forward for ${event.job_title}`;
  }
}
