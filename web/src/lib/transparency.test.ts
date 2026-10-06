import { describe, expect, it } from "vitest";

import type { PairTrace } from "./domain";
import { scoreLadder, similarity } from "./transparency";

function trace(overrides: Partial<PairTrace> = {}): PairTrace {
  return {
    rank: 1,
    candidate_id: "c1",
    candidate_name: "Ada Lovelace",
    above_threshold: true,
    match_score: 61.5,
    weighted_score: 61.5,
    skills: {
      job_skills: ["Python", "SQL", "dbt"],
      candidate_skills: ["Python", "SQL"],
      exact: ["Python", "SQL"],
      partial: [],
      missing: ["dbt"],
      coverage_bonus: false,
      no_data: false,
      raw_score: 66.7,
      nice_to_have_bonus: 0,
      penalty_applied: false,
      penalty_factor: 1,
      job_category: "data_science",
      candidate_category: "data_science",
      score: 66.7,
    },
    role: {
      job_title: "senior data engineer",
      candidate_position: "data engineer",
      semantic_similarity: 0.82,
      base_score: 82,
      job_category: "data_science",
      candidate_category: "data_science",
      relationship: "same_category",
      score: 100,
    },
    experience: {
      job_level: "senior",
      job_years: 5,
      candidate_level: "mid",
      candidate_years: 4,
      level_diff: -1,
      level_match: 70,
      years_diff: -1,
      years_match: 100,
      adjustment: 0,
      years_range_penalty: 0,
      score: 79,
    },
    tier: {
      name: "standard",
      label: "Standard",
      condition: "role score 50 or above",
      weights: { skill: 0.35, role: 0.45, experience: 0.2 },
      multiplier: 1,
    },
    final_penalty_applied: false,
    final_penalty_multiplier: 0.4,
    explanation: "Good role alignment",
    ...overrides,
  };
}

describe("scoreLadder", () => {
  it("shows the three components, the blend, and the final score when nothing was penalised", () => {
    const steps = scoreLadder(trace());
    expect(steps.map((s) => s.kind)).toEqual(["component", "component", "component", "blend", "final"]);
    expect(steps.at(-1)!.value).toBe(61.5);
    expect(steps[0].detail).toContain("2 exact (Python, SQL)");
    expect(steps[0].detail).toContain("1 missing (dbt)");
  });

  it("adds a rung for each penalty that actually fired", () => {
    const steps = scoreLadder(
      trace({
        match_score: 4.1,
        weighted_score: 10.2,
        above_threshold: false,
        skills: {
          ...trace().skills,
          penalty_applied: true,
          penalty_factor: 0.3,
          raw_score: 66.7,
          score: 20,
          candidate_category: "software_engineering",
        },
        final_penalty_applied: true,
      }),
    );
    const labels = steps.map((s) => s.label);
    expect(labels).toContain("Cross-domain skill discount");
    expect(labels).toContain("Weak role and weak skills");
    expect(steps.find((s) => s.label === "Cross-domain skill discount")!.detail).toContain("30%");
    expect(steps.at(-1)!.detail).toMatch(/Below the threshold/);
  });

  it("says when the embedding was unavailable instead of inventing a similarity", () => {
    const steps = scoreLadder(
      trace({ role: { ...trace().role, semantic_similarity: null, base_score: 30 } }),
    );
    expect(steps.find((s) => s.label === "Role fit")!.detail).toContain("embedding unavailable");
    expect(similarity(null)).toBe("n/a");
    expect(similarity(0.4567)).toBe("0.46");
  });

  it("explains the neutral skill score when a side has no skills", () => {
    const steps = scoreLadder(
      trace({ skills: { ...trace().skills, no_data: true, raw_score: 30, score: 30, exact: [], missing: [] } }),
    );
    expect(steps[0].detail).toMatch(/neutral 30/);
  });

  it("adds nice-to-have, years and requirement rungs when the job sets requirements", () => {
    const steps = scoreLadder(
      trace({
        match_score: 70,
        skills: { ...trace().skills, nice_to_have_bonus: 5 },
        experience: { ...trace().experience, years_range_penalty: 20, score: 59 },
        requirements: {
          must_have: { skills: ["Python", "Rust"], present: ["Python"], missing: ["Rust"] },
          nice_to_have: { skills: ["dbt", "Spark"], present: ["dbt"], missing: ["Spark"] },
          years: {
            min_years: 6,
            max_years: null,
            candidate_years: 4,
            short_by: 2,
            over_by: 0,
            penalty: 20,
            counts_as_missing: true,
          },
          education: {
            min_education: "master",
            candidate_education: null,
            meets: null,
            counts_as_missing: false,
          },
          cap: {
            missing: ["must-have skill Rust", "at least 6 years of experience"],
            missing_count: 2,
            limit: 50,
            applied: true,
            score_before: 74.2,
          },
        },
      }),
    );
    const byLabel = Object.fromEntries(steps.map((s) => [s.label, s]));
    expect(byLabel["Nice-to-have skills"].value).toBeCloseTo(71.7);
    expect(byLabel["Nice-to-have skills"].detail).toContain("1 of 2 (dbt)");
    expect(byLabel["Seniority"].value).toBe(79);
    expect(byLabel["Years of experience"].value).toBe(59);
    expect(byLabel["Years of experience"].detail).toContain("About 4 years recorded against at least 6 years");
    expect(byLabel["Requirements"].kind).toBe("penalty");
    expect(byLabel["Requirements"].detail).toContain("Must-haves missing: Rust");
    expect(byLabel["Requirements"].detail).toContain("capped at 50 (was 74.2)");
    expect(byLabel["Requirements"].detail).toContain("master's degree was not checked");
    expect(steps.at(-1)!.kind).toBe("final");
  });

  it("adds no requirement rungs for a job without requirements", () => {
    const labels = scoreLadder(trace({ requirements: null })).map((s) => s.label);
    expect(labels).not.toContain("Requirements");
    expect(labels).not.toContain("Nice-to-have skills");
    expect(labels).not.toContain("Years of experience");
  });
});
