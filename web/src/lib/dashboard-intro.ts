/**
 * The welcome copy at the top of the dashboard: what RecruitIQ is and a short
 * tour of the screens worth visiting first.
 *
 * The dashboard is the first page a visitor lands on, usually from a link with
 * no context, so it has to say what the app does before showing any numbers.
 * Each step names a real route from the nav; keep them in step with nav.tsx.
 */
export type TourStep = { href: string; label: string; detail: string };

export const INTRO_TITLE = "Welcome to RecruitIQ";

export const INTRO_SUMMARY =
  "RecruitIQ is an AI recruiting workspace. It reads resumes, ranks candidates against open roles, " +
  "and explains every score it gives, so a recruiter can see why someone is a fit instead of taking " +
  "a number on trust.";

export const INTRO_DATA_NOTE =
  "Every candidate here is synthetic demo data. Look around freely: the demo account is read-only.";

export const TOUR_STEPS: TourStep[] = [
  {
    href: "/matching",
    label: "Match to a role",
    detail: "Pick a job and see a ranked shortlist with the sub-scores behind each fit.",
  },
  {
    href: "/assistant",
    label: "Ask the assistant",
    detail: "Search in plain English, like Python engineers on the west coast.",
  },
  {
    href: "/upload",
    label: "Parse a resume",
    detail: "Drop in a resume, or try the sample, and review what the parser pulls out.",
  },
  {
    href: "/transparency",
    label: "Audit the scoring",
    detail: "Trace any score back to the signals, weights, and fields that produced it.",
  },
];
