/**
 * Interview and feedback vocabulary (ATS Phase B). Mirrors
 * feedback_service.py; the API validates, this only labels.
 */
import { roleLabel } from "./permissions";

export const RECOMMENDATIONS = ["strong_hire", "hire", "no_hire", "strong_no_hire"] as const;

export const RECOMMENDATION_LABELS: Record<string, string> = {
  strong_hire: "Strong hire",
  hire: "Hire",
  no_hire: "No hire",
  strong_no_hire: "Strong no hire",
};

export const INTERVIEW_STATE_LABELS: Record<string, string> = {
  upcoming: "Upcoming",
  waiting: "Waiting for feedback",
  submitted: "Feedback submitted",
  skipped: "Stage skipped",
};

/** Same rule as the backend's display_name: a name, else the role. Never an email. */
export function memberName(member: { name?: string | null; role: string }): string {
  return member.name || roleLabel(member.role);
}

/** Track 2 Phase 6: the API refuses a summary of fewer forms than this. */
export const SUMMARY_MIN_FEEDBACK = 2;

/**
 * Whether to offer the AI feedback summary. Mirrors the API: enough submitted
 * forms, every one of them readable by this viewer, and not an interviewer
 * (interviewers are refused even after they submit).
 */
export function canSummarizeFeedback(
  interviews: { state: string; feedback_hidden?: boolean | null }[],
  role: string | null | undefined,
): boolean {
  if (!role || role === "interviewer") return false;
  if (interviews.some((interview) => interview.feedback_hidden)) return false;
  return interviews.filter((interview) => interview.state === "submitted").length >= SUMMARY_MIN_FEEDBACK;
}

/**
 * The label under a summary. The API sends a naive UTC timestamp, so it is
 * read as UTC and shown in the viewer's time zone (or `timeZone`, for tests).
 */
export function summaryStamp(count: number, generatedAt: string, timeZone?: string): string {
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(generatedAt) ? generatedAt : `${generatedAt}Z`;
  const date = new Date(iso);
  const when = Number.isNaN(date.getTime())
    ? ""
    : ` on ${new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZone,
      }).format(date)}`;
  return `AI-generated from ${count} submitted feedback forms${when}. Not saved. Check it against the forms before you act on it.`;
}
