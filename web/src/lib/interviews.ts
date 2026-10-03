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
