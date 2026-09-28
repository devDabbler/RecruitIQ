/**
 * Turning a scoring trace into the ladder the Transparency screen renders.
 *
 * Pure: the API already did the arithmetic, this only decides which rungs to
 * show and how to word them. Kept out of the page so it can be unit tested
 * without rendering anything.
 */
import type { PairTrace } from "./domain";

export type LadderKind = "component" | "penalty" | "blend" | "final";

export interface LadderStep {
  kind: LadderKind;
  label: string;
  /** The number this rung produced, on the 0 to 100 scale. */
  value: number;
  /** One line a recruiter can read: what was compared and what came of it. */
  detail: string;
}

const RELATIONSHIP_WORDS: Record<string, string> = {
  same_category: "same role family, similarity boosted by 1.3x",
  moderately_incompatible: "related but different role families, capped at 20",
  highly_incompatible: "unrelated role families, capped at 12",
  unrelated: "different role families, no adjustment",
  uncategorized: "no role family recognised for one or both titles, no adjustment",
  missing_title: "one title is blank, default score",
};

export function pct(value: number): string {
  return `${Math.round(value)}`;
}

export function similarity(value: number | null | undefined): string {
  return value === null || value === undefined ? "n/a" : value.toFixed(2);
}

function list(items: string[], max = 4): string {
  if (items.length === 0) return "none";
  const shown = items.slice(0, max).join(", ");
  return items.length > max ? `${shown} and ${items.length - max} more` : shown;
}

export function scoreLadder(trace: PairTrace): LadderStep[] {
  const { skills, role, experience, tier } = trace;
  const steps: LadderStep[] = [];

  steps.push({
    kind: "component",
    label: "Skill overlap",
    value: skills.raw_score,
    detail: skills.no_data
      ? "No skills listed on one side, so a neutral 30 is used"
      : `${skills.exact.length} exact (${list(skills.exact)}), ${skills.partial.length} partial (${list(skills.partial)}), ${skills.missing.length} missing (${list(skills.missing)})${skills.coverage_bonus ? ". Coverage bonus of 10% applied" : ""}`,
  });

  if (skills.penalty_applied) {
    steps.push({
      kind: "penalty",
      label: "Cross-domain skill discount",
      value: skills.score,
      detail: `${role.job_title} reads as ${words(skills.job_category)} and ${role.candidate_position} as ${words(skills.candidate_category)}, so shared skills count for ${Math.round(skills.penalty_factor * 100)}%`,
    });
  }

  steps.push({
    kind: "component",
    label: "Role fit",
    value: role.score,
    detail: `Title similarity ${similarity(role.semantic_similarity)}${role.semantic_similarity === null || role.semantic_similarity === undefined ? " (embedding unavailable, default 30)" : ""}; ${RELATIONSHIP_WORDS[role.relationship] ?? role.relationship}`,
  });

  steps.push({
    kind: "component",
    label: "Seniority",
    value: experience.score,
    detail: `Job reads as ${experience.job_level} (${experience.job_years} yrs), candidate as ${experience.candidate_level} (${experience.candidate_years} yrs). Level match ${pct(experience.level_match)}, years match ${pct(experience.years_match)}${experience.adjustment ? `, adjustment ${experience.adjustment}` : ""}`,
  });

  steps.push({
    kind: "blend",
    label: `Weighted blend (${tier.label.toLowerCase()})`,
    value: trace.weighted_score,
    detail: `${tier.condition}: skills x${tier.weights.skill}, role x${tier.weights.role}, seniority x${tier.weights.experience}${tier.multiplier < 1 ? `, then scaled by ${tier.multiplier}` : ""}`,
  });

  if (trace.final_penalty_applied) {
    steps.push({
      kind: "penalty",
      label: "Weak role and weak skills",
      value: trace.match_score,
      detail: `Both the role and skill scores were low, so the blend is scaled by ${trace.final_penalty_multiplier}`,
    });
  }

  steps.push({
    kind: "final",
    label: "Final score",
    value: trace.match_score,
    detail: trace.above_threshold
      ? "Shown on the Matching screen"
      : "Below the threshold, so the Matching screen does not list this person",
  });

  return steps;
}

function words(category: string | null | undefined): string {
  return category ? category.replace(/_/g, " ") : "no known family";
}
