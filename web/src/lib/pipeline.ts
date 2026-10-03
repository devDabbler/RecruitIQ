/**
 * Pipeline vocabulary and the rules for which actions a writer may take.
 *
 * Mirrors `pipeline_service.py`: the server is the authority and answers 409
 * for anything illegal; this only decides which buttons to draw.
 */
import type { ApplicationDetail } from "./domain";

export type StageAction = "advance" | "skip" | "reject" | "decline";

export const ACTION_LABELS: Record<StageAction, string> = {
  advance: "Advance",
  skip: "Skip stage",
  reject: "Reject",
  decline: "Candidate declined",
};

export const STAGE_STATUS_LABELS: Record<string, string> = {
  pending: "Upcoming",
  in_progress: "In progress",
  passed: "Passed",
  failed: "Rejected here",
  skipped: "Skipped",
};

export const APPLICATION_STATUS_LABELS: Record<string, string> = {
  active: "In progress",
  hired: "Hired",
  rejected: "Rejected",
  declined: "Offer declined",
  withdrawn: "Withdrawn",
};

const DECLINABLE = new Set(["offer", "offer_accepted"]);

/**
 * Skip needs an enabled, still-pending round after the current one to land
 * on. Outcomes are not rounds, so on the last such round only Advance (which
 * hires) remains. A round that already happened does not count: since ATS
 * Phase E stages can be reordered, one can sit after the current round.
 */
function hasLaterRound(application: ApplicationDetail, key: string): boolean {
  const index = application.stages.findIndex((s) => s.key === key);
  if (index === -1) return key !== "offer_accepted";
  return application.stages
    .slice(index + 1)
    .some((s) => s.kind === "round" && s.enabled && s.status === "pending");
}

export function availableActions(application: ApplicationDetail): StageAction[] {
  if (application.status !== "active" || !application.current_stage_key) return [];
  const key = application.current_stage_key;
  const actions: StageAction[] = ["advance"];
  if (hasLaterRound(application, key)) actions.push("skip");
  actions.push("reject");
  if (DECLINABLE.has(key)) actions.push("decline");
  return actions;
}
