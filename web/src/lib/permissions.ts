/**
 * Who may do what, for drawing controls (ATS Phase B).
 *
 * `role-permissions.json` is generated from backend/utils/permissions.py by
 * scripts/export_permissions.py, and a backend test fails if it drifts. The
 * backend enforces the table; this only decides which buttons to show, since
 * a hidden button is not an access control.
 *
 * No `server-only` import: client components need `can` too.
 */
import table from "./role-permissions.json";

export const JOBS_WRITE = "jobs.write";
export const CANDIDATES_ADD = "candidates.add";
export const PIPELINE_MOVE = "pipeline.move";
export const FEEDBACK_SUBMIT = "feedback.submit";
export const USERS_INVITE = "users.invite";
export const USERS_CHANGE_ROLE = "users.change_role";
export const DELETE_RECORDS = "records.delete";
export const SCORE_BEFORE_FEEDBACK = "score.before_feedback";
export const REPORTS_VIEW = "reports.view";
export const TEMPLATES_MANAGE = "templates.manage";
export const PROFILE_EDIT = "profile.edit";
export const AUDIT_VIEW = "audit.view";
export const DATA_EXPORT = "candidates.export_data";

export type Permission =
  | typeof JOBS_WRITE
  | typeof CANDIDATES_ADD
  | typeof PIPELINE_MOVE
  | typeof FEEDBACK_SUBMIT
  | typeof USERS_INVITE
  | typeof USERS_CHANGE_ROLE
  | typeof DELETE_RECORDS
  | typeof SCORE_BEFORE_FEEDBACK
  | typeof REPORTS_VIEW
  | typeof TEMPLATES_MANAGE
  | typeof PROFILE_EDIT
  | typeof AUDIT_VIEW
  | typeof DATA_EXPORT;

export type Role = "admin" | "hiring_manager" | "hiring_team" | "interviewer" | "demo";

/** The four roles a person on the team can hold, in the order screens list them. */
export const STAFF_ROLES: Role[] = ["admin", "hiring_manager", "hiring_team", "interviewer"];

const GRANTS = table.roles as Record<string, string[]>;
const LABELS = table.labels as Record<string, string>;

export function can(role: string | null | undefined, permission: Permission): boolean {
  if (!role) return false;
  return (GRANTS[role] ?? []).includes(permission);
}

export function roleLabel(role: string | null | undefined): string {
  if (!role) return "Signed out";
  return LABELS[role] ?? role;
}
