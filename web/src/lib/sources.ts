/**
 * How a candidate found the job (Track 2 Phase 3): one vocabulary for the
 * add-candidate panel, the bulk uploader, and "Consider for another role".
 *
 * Mirrors SOURCE_LABELS in backend/services/sources.py, in the same order
 * (most common first). A test checks the values against the API's
 * ApplicationSource enum so the two cannot drift.
 */
import type { ApplicationSource } from "./domain";

export const SOURCE_OPTIONS: readonly { value: ApplicationSource; label: string }[] = [
  { value: "linkedin", label: "LinkedIn" },
  { value: "referral", label: "Referral" },
  { value: "company_website", label: "Company website" },
  { value: "indeed", label: "Indeed" },
  { value: "job_board", label: "Other job board" },
  { value: "agency", label: "Agency" },
  { value: "direct_application", label: "Applied directly" },
  { value: "internal", label: "Internal" },
  { value: "other", label: "Other" },
];

/** What a new application records when nobody picks a source. */
export const DEFAULT_SOURCE: ApplicationSource = "direct_application";

export function sourceLabel(value: string | null | undefined): string {
  if (!value || value === "unknown") return "Not recorded";
  return SOURCE_OPTIONS.find((option) => option.value === value)?.label ?? "Other";
}
