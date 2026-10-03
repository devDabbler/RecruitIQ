import { describe, expect, it } from "vitest";

import type { StageOut } from "./domain";
import { buildUpdate, moveStage, placementOptions, toEditable, validateEdits } from "./stage-editor";

function stage(key: string, position: number, extra: Partial<StageOut> = {}): StageOut {
  const pinned = ["resume_submitted", "offer", "offer_accepted"].includes(key);
  const outcome = ["offer_declined", "hired"].includes(key);
  return {
    id: position,
    key,
    name: key,
    kind: outcome ? "outcome" : "round",
    description: null,
    position,
    enabled: true,
    custom: key.startsWith("custom_"),
    movable: !pinned && !outcome,
    ...extra,
  };
}

const STAGES = [
  stage("hm_review", 2),
  stage("resume_submitted", 1),
  stage("case_study", 3),
  stage("offer", 4),
  stage("offer_accepted", 5),
  stage("hired", 6),
];

describe("toEditable", () => {
  it("sorts by position and fills defaults", () => {
    const edited = toEditable(STAGES);
    expect(edited.map((s) => s.key)[0]).toBe("resume_submitted");
    expect(edited[0].description).toBe("");
  });
});

describe("moveStage", () => {
  const edited = toEditable(STAGES);

  it("swaps two movable neighbors", () => {
    expect(moveStage(edited, "case_study", -1).map((s) => s.key).slice(1, 3)).toEqual([
      "case_study",
      "hm_review",
    ]);
  });

  it("never moves into or past a pinned stage", () => {
    expect(moveStage(edited, "hm_review", -1)).toBe(edited);
    expect(moveStage(edited, "case_study", 1)).toBe(edited);
    expect(moveStage(edited, "offer", -1)).toBe(edited);
  });
});

describe("buildUpdate", () => {
  const original = toEditable(STAGES);

  it("sends nothing for an untouched pipeline", () => {
    expect(buildUpdate(original, original, [], [])).toEqual({ stages: [], order: null, add: [], remove: [] });
  });

  it("sends only changed stages, the new order, additions, and removals", () => {
    const renamed = original.map((s) => (s.key === "hm_review" ? { ...s, name: "Manager chat " } : s));
    const moved = moveStage(renamed, "case_study", -1);
    const update = buildUpdate(original, moved, [{ name: " Portfolio ", description: "", afterKey: null }], []);
    expect(update.stages).toEqual([
      { key: "hm_review", enabled: true, name: "Manager chat", description: "" },
    ]);
    expect(update.order).toEqual(["case_study", "hm_review"]);
    expect(update.add).toEqual([{ name: "Portfolio", description: null, after_key: null }]);
  });

  it("leaves removed stages out of the order", () => {
    const withCustom = toEditable([...STAGES, stage("custom_x", 3.5)]);
    const remaining = withCustom.filter((s) => s.key !== "custom_x");
    const update = buildUpdate(withCustom, remaining, [], ["custom_x"]);
    expect(update.order).toBeNull();
    expect(update.remove).toEqual(["custom_x"]);
  });
});

describe("validateEdits and placementOptions", () => {
  it("catches empty names and a disabled first stage", () => {
    const edited = toEditable(STAGES);
    expect(validateEdits(edited, [])).toBeNull();
    expect(validateEdits(edited.map((s) => ({ ...s, name: s.key === "offer" ? " " : s.name })), [])).toMatch(
      /needs a name/,
    );
    expect(
      validateEdits(edited.map((s) => (s.key === "resume_submitted" ? { ...s, enabled: false } : s)), []),
    ).toMatch(/cannot be turned off/);
  });

  it("offers the first stage and the interview stages as places to add after", () => {
    expect(placementOptions(toEditable(STAGES)).map((o) => o.key)).toEqual([
      "resume_submitted",
      "hm_review",
      "case_study",
    ]);
  });
});
