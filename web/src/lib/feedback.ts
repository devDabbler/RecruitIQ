/**
 * Feedback form helpers (Track 2 Phase 4): templates, keyboard shortcuts,
 * the nav badge. Pure, so Vitest covers them; the form wires them up.
 */
import type { FeedbackTemplate } from "./domain";

/** How long the form waits after the last change before saving a draft. */
export const AUTOSAVE_MS = 1200;

/** A job's own templates first, then the global ones, each in the order given. */
export function templatesForJob(templates: FeedbackTemplate[], jobId: number): FeedbackTemplate[] {
  return [
    ...templates.filter((t) => t.job_id === jobId),
    ...templates.filter((t) => t.job_id === null || t.job_id === undefined),
  ];
}

/** Fill the notes box. Never throws away what the interviewer already wrote. */
export function applyTemplate(notes: string, body: string): string {
  return notes.trim() ? `${notes.trimEnd()}\n\n${body}` : body;
}

export type Shortcut = { kind: "rating"; value: number } | { kind: "submit" } | null;

/**
 * 1-5 sets the rating, but only when focus is not in a text field (the
 * interviewer may be typing a number). Ctrl or Cmd + Enter submits from anywhere.
 */
export function feedbackShortcut(event: {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey?: boolean;
  inTextField: boolean;
}): Shortcut {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) return { kind: "submit" };
  if (event.inTextField || event.ctrlKey || event.metaKey || event.altKey) return null;
  if (/^[1-5]$/.test(event.key)) return { kind: "rating", value: Number(event.key) };
  return null;
}

/** The nav badge's text: nothing at zero, "9+" past nine. */
export function badgeText(count: number): string | null {
  if (!Number.isFinite(count) || count <= 0) return null;
  return count > 9 ? "9+" : String(Math.floor(count));
}

/**
 * Short, plain "Draft saved 2:41 PM" stamp for the form, in the viewer's
 * time. The API sends naive UTC timestamps, so one without a zone is UTC.
 */
export function draftSavedLabel(updatedAt: string | Date): string {
  const when =
    typeof updatedAt === "string" && /T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(updatedAt)
      ? new Date(`${updatedAt}Z`)
      : new Date(updatedAt);
  if (Number.isNaN(when.getTime())) return "Draft saved";
  return `Draft saved ${when.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
}
