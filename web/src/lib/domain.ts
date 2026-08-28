/**
 * Names for the shapes the screens use.
 *
 * Every type here is an alias into `schema.d.ts`, which openapi-typescript
 * generates from the committed `openapi.json`. Nothing is hand-modelled: if a
 * FastAPI `response_model` changes, these change with it and `tsc` points at
 * the screens that need updating. That is the whole reason Phase 3a backfilled
 * `response_model` before any of this existed (spec §3).
 */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Candidate = Schemas["CandidateResponse"];
export type CandidateSearch = Schemas["CandidateSearchResponse"];
export type Job = Schemas["JobResponse"];
export type Application = Schemas["CandidateApplicationSummary"];
export type SavedJob = Schemas["CandidateSavedJobSummary"];
export type User = Schemas["UserResponse"];
export type CandidateMatch = Schemas["CandidateMatchResult"];
export type JobMatch = Schemas["JobMatchResult"];
export type ResumeSummary = Schemas["CandidateResumeSummary"];

/** `GET /api/jobs/` is paginated the same way the candidate list is. */
export interface JobList {
  results: Job[];
  total: number;
}

/** `GET /api/candidates/skills_breakdown` — skill name to headcount. */
export type SkillsBreakdown = Record<string, number>;

/**
 * The candidate funnel, in the order a recruiter reads it.
 *
 * Mirrors `CandidateStatus` in backend/models/candidate.py. Kept as a const
 * array rather than derived from the schema because the *order* carries
 * meaning here and an enum's declaration order is not part of the OpenAPI
 * contract.
 */
export const PIPELINE_STAGES = [
  "active",
  "screening",
  "interviewing",
  "offered",
  "hired",
  "rejected",
  "on_hold",
] as const;

export type PipelineStage = (typeof PIPELINE_STAGES)[number];

export const STAGE_LABELS: Record<PipelineStage, string> = {
  active: "Active",
  screening: "Screening",
  interviewing: "Interviewing",
  offered: "Offered",
  hired: "Hired",
  rejected: "Rejected",
  on_hold: "On hold",
};

/**
 * Tailwind classes per stage. Explicit strings, not interpolated: Tailwind
 * scans source text, so a class built at runtime is never emitted.
 */
export const STAGE_CLASSES: Record<PipelineStage, string> = {
  active: "bg-slate-100 text-slate-700 border-slate-200",
  screening: "bg-blue-50 text-blue-700 border-blue-200",
  interviewing: "bg-violet-50 text-violet-700 border-violet-200",
  offered: "bg-amber-50 text-amber-700 border-amber-200",
  hired: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
  on_hold: "bg-neutral-100 text-neutral-600 border-neutral-200",
};

export function isPipelineStage(value: string | null | undefined): value is PipelineStage {
  return !!value && (PIPELINE_STAGES as readonly string[]).includes(value);
}

export function fullName(candidate: Pick<Candidate, "first_name" | "last_name">): string {
  const name = [candidate.first_name, candidate.last_name].filter(Boolean).join(" ").trim();
  return name || "Unnamed candidate";
}

export function initials(candidate: Pick<Candidate, "first_name" | "last_name">): string {
  const letters = [candidate.first_name?.[0], candidate.last_name?.[0]].filter(Boolean).join("");
  return (letters || "?").toUpperCase();
}
