/**
 * How an applicant's fit for a job is shown (Track 2 Phase 2).
 *
 * The number is the same `score_pair` match score the Matching page and the
 * transparency trace use. An interviewer gets `hidden` until they have
 * submitted feedback on the candidate, and then sees a dash, never a number.
 */
import type { components } from "./schema";

export type ApplicantFit = components["schemas"]["ApplicantFit"];

export type FitTone = "strong" | "moderate" | "weak" | "none";

export interface FitDisplay {
  text: string;
  tone: FitTone;
  /** Tooltip and screen-reader text: what the number means and any cap. */
  title: string;
  capped: boolean;
}

export const FIT_HIDDEN_TITLE = "Submit your feedback on this candidate to see their fit score.";

export function fitDisplay(fit: ApplicantFit | null | undefined): FitDisplay {
  if (!fit || fit.hidden || fit.score === null || fit.score === undefined) {
    return {
      text: "-",
      tone: "none",
      title: fit?.hidden ? FIT_HIDDEN_TITLE : "Not scored",
      capped: false,
    };
  }
  const score = Math.round(fit.score);
  const tone: FitTone = score >= 70 ? "strong" : score >= 50 ? "moderate" : "weak";
  const missing = fit.missing ?? [];
  const parts = [`Fit ${score} out of 100.`];
  if (fit.capped) parts.push(`Capped because they are missing ${joinMissing(missing)}.`);
  else if (missing.length) parts.push(`Missing ${joinMissing(missing)}.`);
  return { text: String(score), tone, title: parts.join(" "), capped: fit.capped ?? false };
}

/** The short form for a board card: "missing Docker", "missing Python, Docker". */
export function capReason(missing: string[] | null | undefined): string {
  const items = (missing ?? []).map((m) => m.replace(/^must-have skill /, ""));
  return items.length ? `missing ${items.join(", ")}` : "a requirement is missing";
}

function joinMissing(missing: string[]): string {
  if (missing.length === 0) return "a requirement";
  if (missing.length === 1) return missing[0];
  return `${missing.slice(0, -1).join(", ")} and ${missing[missing.length - 1]}`;
}

/** Best first; anything without a visible score goes last, in its original order. */
export function byFit<T>(items: T[], fitOf: (item: T) => ApplicantFit | null | undefined): T[] {
  const score = (item: T) => {
    const fit = fitOf(item);
    return fit && !fit.hidden && typeof fit.score === "number" ? fit.score : null;
  };
  return items
    .map((item, index) => ({ item, index, score: score(item) }))
    .sort((a, b) => {
      if (a.score === null && b.score === null) return a.index - b.index;
      if (a.score === null) return 1;
      if (b.score === null) return -1;
      return b.score - a.score || a.index - b.index;
    })
    .map(({ item }) => item);
}

/** The candidate list's sort when it is filtered to a job: best first unless asked otherwise. */
export type FitSort = "best" | "worst";

export function fitSortFrom(value: string | undefined): FitSort {
  return value === "worst" ? "worst" : "best";
}

export function fitQuery(sort: FitSort): { sortBy: "fit"; sortOrder: "asc" | "desc" } {
  return { sortBy: "fit", sortOrder: sort === "worst" ? "asc" : "desc" };
}
