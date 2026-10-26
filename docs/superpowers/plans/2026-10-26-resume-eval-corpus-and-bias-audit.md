# Resume evaluation corpus and bias audit

Date: 2026-10-26
Status: proposed, not started. Nothing here is built or collected until
the gates in section 3 are met.
Sources: `2026-10-05-fractal-pilot-and-gap-plan.md` (pilot controls),
`docs/decisions/0001-llm-provider-chain.md` and `0002-per-task-llm-routing.md`
(routing), `backend/tests/test_score_baseline.py` (current scoring golden),
`evals/results.md` (parse eval, 99% hosted vs 86% local).

## 1. Why

Every resume evaluation today is a fresh model call with no baseline. Two
runs on the same resume can disagree, and nobody can say which run was
right or whether either was fair. Sean's instinct is that "training on
resumes" fixes this. The useful half of that instinct is: accuracy and
fairness both need a corpus of real evaluations to measure against. The
half to resist is updating model weights on past hiring decisions, which
teaches the model past bias (Amazon retired its resume model in 2018 for
this reason) and makes the result impossible to audit.

So the plan collects labels, not training data, and spends them in this
order: measure, then calibrate, then (narrowly, last) train.

This is also compliance groundwork. NYC Local Law 144 requires an annual
bias audit of automated employment decision tools, and the EU AI Act
classes recruitment AI as high-risk. A formal adoption pitch that arrives
with its own audit numbers is stronger than one that promises them later.

## 2. What exists today

| Piece | Where | What it gives us |
|---|---|---|
| Single scoring function | `MatchingIntegrator.score_pair` (`backend/services/matching_integrator.py`) | One place to snapshot a score, its sub-scores and its explanation |
| Scoring regression golden | `backend/tests/golden/score_pair_baseline.json`, `test_score_baseline.py` | Proves scores did not move; says nothing about whether they are right |
| Structured requirements and caps | Track 2 Phase 1 | Fixed rubric in code, the biggest consistency win already shipped |
| Relevance banding golden | 19-case set (PR #32) | Pattern for a hand-labelled accuracy set |
| Parse eval | `evals/run_eval.py`, `evals/scorer.py`, `evals/results.md` | Extraction accuracy per model; the one place fine-tuning could later apply |
| Assistant golden set | `evals/assistant_golden.json`, `test_assistant_golden.py` | Pattern for a live eval runner |
| De-identification | `backend/services/resume_privacy.anonymize_parsed_resume` | Scrubbed copy of a parse, with a per-field report of what was removed |
| Human judgements | `Feedback` (rating, recommendation), `ApplicationStage` (passed/failed/skipped), `JobApplication` outcomes | Labels, produced as a side effect of the ATS workflow |
| Controls | audit log (PR #51), erasure (PR #50), export (PR #52), retention (PR #53), internal mode (PR #49) | Every new table joins `ERASURE_STEPS`, `SECTION_LABELS`, `ACTIVITY_COLUMNS` and the audit classification, or CI fails |

The labels are the point. A standalone scorer never had them; the pipeline
produces them for free. This is also the argument that makes the workflow
half of the product load-bearing for the evaluation half.

## 3. Gates before any real data is stored

All of these, not some:

1. Pilot approved and running under `DEPLOYMENT_MODE=internal`.
2. Consent and privacy-notice text approved by whoever owns that at the
   host company. Candidates must be told their application data is used to
   evaluate and improve the screening tool. A `consent_evaluation` flag on
   the candidate, default false, gates every write in Phase 1.
3. `RETENTION_DAYS` set; the corpus follows it (anonymised rows may outlive
   the candidate, scrubbed text may not).
4. Demographic data (needed for impact ratios) is a separate decision: it
   is self-reported, voluntary, stored apart from the candidate record,
   never shown to anyone, and only ever read in aggregate. If legal says no,
   Phase 2 runs the counterfactual audit only.

## 4. Principles

- Labels, not weights. Measure first; train only where labels are objective.
- De-identified by construction: the corpus stores the scrubbed parse, never
  the resume file or raw text.
- Snapshot the score at decision time, with the model id, prompt version and
  requirements version, so a later change can be compared like for like.
- Read-only on the request path. Collection runs as a nightly job, like
  retention, so a slow or failed write can never affect a recruiter.
- Never a hire/no-hire model. Fine-tuning, if it ever happens, is for
  extraction only.

## 5. Phases

### Phase 0: build what needs no real data (can start now)

- **Scoring accuracy golden.** Hand-label every seeded job x seeded
  candidate pair with an expected band (strong, moderate, none) and assert
  `score_pair` lands in it, with a tolerance. Unlike the baseline file this
  encodes what the answer should be. Lives next to `test_score_baseline.py`.
- **Counterfactual harness.** For each seeded candidate, generate variants
  with the name, pronouns, school, address, graduation year and employment
  gaps changed and assert `score_pair` output is identical. This proves
  the de-identification path actually reaches the scorer. One test file,
  runs in CI, no model call needed with the deterministic fake embedder.
- **Score snapshot shape.** Define the `evaluation_snapshots` row (section 6)
  and the Alembic revision, but do not wire writes yet.

Size: S-M. One PR on the normal /st loop.

### Phase 1: label capture (pilot live, gates met)

- Nightly job `scripts/collect_evaluations.py` (systemd timer, same pattern
  as `scripts/retention.py`): for every application whose candidate has
  `consent_evaluation=true`, write or update one `evaluation_snapshots` row
  with the score snapshot, the scrubbed parse, and the labels derived from
  the pipeline so far (furthest stage reached, mean feedback rating,
  recommendation counts, outcome).
- Labels update as the pipeline moves; the score snapshot is written once,
  at first scoring, and kept.
- New table joins erasure, export, retention and audit per the standing
  rules. Erasure removes the row; retention anonymises it (drops the
  scrubbed parse, keeps scores and labels).
- Nothing reads this table yet except the export.

Size: M.

### Phase 2: measure (at least 200 labelled applications over 3+ roles)

- `evals/scoring_eval.py`: per role family, Spearman correlation between
  AI score and furthest stage reached; precision at k for "advanced past
  hiring manager review"; a calibration table (score decile vs advance
  rate). Output to `evals/scoring_results.md`, dated.
- Counterfactual audit on the real corpus: same swaps as Phase 0 over the
  scrubbed parses, report any pair that moves.
- Impact ratios (LL144 style) by self-reported group, only if the gate in
  section 3 item 4 is met; otherwise state that it was not measured.
- Decision point: if correlation is weak, the fix is in requirements and
  rubric (Phase 1 of Track 2 machinery), not in the model.

Size: M. Repeat every quarter; the report is the audit artifact.

### Phase 3: calibrate with examples, not training

- When scoring, retrieve two or three past snapshots for the same role
  family with similar scrubbed profiles (pgvector is already there) and
  show them to the model as worked examples, with their labels. Goes
  through `build_chain` like every other prompt, de-identified.
- Measure against Phase 2 before and after. Keep it only if it moves the
  numbers.

Size: M.

### Phase 4 (optional): fine-tune a local extraction model

- Only once 1,000+ parses exist with recruiter corrections (needs a small
  "fix this field" capture in the candidate UI, which is also just a useful
  feature). Labels are objective: the corrected fields.
- Target: close the local parse gap (86% today vs 99% hosted) so the
  fully local deployment is not an accuracy trade-off.
- Train on scrubbed text only, on the operator's own hardware, through the
  existing Ollama path. Never on hire/no-hire labels.

Size: L. Decide after Phase 2 results.

## 6. Data shape (Phase 0 defines, Phase 1 writes)

`evaluation_snapshots`

| Column | Notes |
|---|---|
| id, application_id, candidate_id, job_id | FKs; cascade through `ERASURE_STEPS` |
| scored_at, model_id, prompt_version, requirements_version | Like-for-like comparison later |
| score_json | Full `score_pair` output |
| scrubbed_profile_json | `anonymize_parsed_resume` output; nulled by retention |
| furthest_stage, mean_rating, recommendation_counts_json, outcome | Labels, refreshed nightly |
| labels_updated_at | `ACTIVITY_COLUMNS` entry for retention |

Demographics, if approved, live in a separate table keyed by a one-way
token, with no FK to candidates, readable only by the eval script.

## 7. Minimum sizes and what "enough" means

- 200 labelled applications across 3 role families: first correlation and
  calibration numbers, wide error bars, good enough to steer rubric work.
- 500: counterfactual audit with meaning; impact ratios per group if groups
  have 30+ members.
- 1,000 corrected parses: fine-tuning becomes worth trying.

Until the first threshold, say "not yet measured" in any pitch. The seed
data is synthetic and must never be counted toward these numbers.

## 8. Not doing

- No fine-tuning on outcomes or feedback, ever.
- No storing of resume files or raw text in the corpus.
- No collection on recruitiq.io (public demo, synthetic data only).
- No demographic inference from names, photos or addresses. Self-report or
  nothing.

## 9. Open questions

- Who approves the consent text and the demographic collection at the host
  company?
- Does the pilot's retention period apply to anonymised rows too?
- Do interviewers' ratings count as labels if interviewers never see AI
  scores (current rule), or only outcomes? Default: both, reported
  separately.
