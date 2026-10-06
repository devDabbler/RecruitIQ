import { describe, expect, it } from "vitest";

import { availableActions, STAGE_STATUS_LABELS } from "./pipeline";
import type { ApplicationDetail, ApplicationStage } from "./domain";

function detail(overrides: Partial<ApplicationDetail>): ApplicationDetail {
  return {
    id: 1,
    job_id: 1,
    job_title: "Data Engineer",
    candidate_id: "c1",
    candidate_name: "Ada Lovelace",
    status: "active",
    current_stage_key: "hm_review",
    current_stage_name: "Hiring manager review",
    applied_at: null,
    stages: [],
    ...overrides,
  };
}

function stage(key: string, kind: string, enabled = true): ApplicationStage {
  return { key, name: key, kind, enabled, status: "pending" };
}

describe("availableActions", () => {
  it("offers advance, skip, reject, and withdraw mid-pipeline", () => {
    expect(availableActions(detail({}))).toEqual(["advance", "skip", "reject", "withdraw"]);
  });

  it("adds decline once an offer is out", () => {
    expect(availableActions(detail({ current_stage_key: "offer" }))).toEqual([
      "advance",
      "skip",
      "reject",
      "decline",
      "withdraw",
    ]);
    expect(availableActions(detail({ current_stage_key: "offer_accepted" }))).toEqual([
      "advance",
      "reject",
      "decline",
      "withdraw",
    ]);
  });

  it("drops skip when every later round is turned off", () => {
    const stages = [
      stage("offer", "round"),
      stage("offer_accepted", "round", false),
      stage("offer_declined", "outcome"),
      stage("hired", "outcome"),
    ];
    expect(availableActions(detail({ current_stage_key: "offer", stages }))).toEqual([
      "advance",
      "reject",
      "decline",
      "withdraw",
    ]);
  });

  it("drops skip when the only later round already happened", () => {
    const stages = [
      stage("offer", "round"),
      { ...stage("offer_accepted", "round"), status: "passed" },
      stage("offer_declined", "outcome"),
      stage("hired", "outcome"),
    ];
    expect(availableActions(detail({ current_stage_key: "offer", stages }))).toEqual([
      "advance",
      "reject",
      "decline",
      "withdraw",
    ]);
  });

  it("offers nothing on a terminal application", () => {
    expect(availableActions(detail({ status: "hired", current_stage_key: null }))).toEqual([]);
    expect(availableActions(detail({ status: "rejected", current_stage_key: null }))).toEqual([]);
    expect(availableActions(detail({ status: "withdrawn", current_stage_key: null }))).toEqual([]);
  });
});

describe("STAGE_STATUS_LABELS", () => {
  it("has plain English for every status", () => {
    expect(STAGE_STATUS_LABELS.in_progress).toBe("In progress");
    expect(STAGE_STATUS_LABELS.failed).toBe("Rejected here");
  });
});
