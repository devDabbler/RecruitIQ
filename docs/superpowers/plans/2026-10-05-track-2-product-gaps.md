# Track 2 - Product gaps, phase by phase

Date: 2026-10-05. Source: gap table in `.claude/audits/2026-10-05-slate-source-review.md`
(numbers in brackets below are that table's gap numbers) and Track 2 of
`2026-10-05-fractal-pilot-and-gap-plan.md`.

Goal: make RecruitIQ easy for a recruiting team to use day to day once it
runs in house. Track 1 is done except SSO (#4), which is parked until this
track finishes or Fractal sends identity-provider details.

**How to run a phase:** one fresh session per phase, one PR per phase:

```
/st Track 2 Phase N, per docs/superpowers/plans/2026-10-05-track-2-product-gaps.md
```

Each phase below says what the user gets, the decisions already made (do
not re-ask them), the scope, and what "done" means. Anything a phase leaves
open is listed under "Decide in session"; take the stated default unless the
code says otherwise.

## Order at a glance

| Phase | What the team gets | Gaps | Size | Depends on |
|---|---|---|---|---|
| 1 | Must-have / nice-to-have requirements on jobs; scores capped when must-haves are missing | 1 | M | - |
| 2 | A job's applicants ranked by fit (table, board, bulk upload result) | 2 | M | 1 |
| 3 | Requisition numbers, department picklist, real source picker, Withdraw action | 11, 12, 15, 13 | M (4 x S) | - |
| 4 | Feedback templates, drafts, shortcuts, pending-feedback badge in the nav | 6, 7, 8 | M | - |
| 5 | Tag column, tag filter, bulk tag; median time to hire and to reject | 9, 16 | S | - |
| 6 | AI summary of a candidate's interview feedback | 3 | M | 4 (drafts must not be summarized) |
| 7 | @mentions in notes, with email | 4 | M | - |
| 8 | Daily no-movement email digest | 5 | S-M | 7 (shares staff-email plumbing) |

Phases 3, 4 and 5 are independent and small; if a session finishes early,
the next one can start. Phases 1 then 2 are the headline (Slate's best idea;
credit Prasnajeet's design in the PR description).

Deferred, not in this track: JD from uploaded PDF/Word (10), in-app workflow
guide (17), audit-trail UI page (14, the data already exists from PR #51),
notice period / expected pay capture at HR screen, offer accepted vs joined.

## Rules every phase must follow

These are the traps earlier PRs hit; each one fails CI or bites in prod.

- **Candidate data tables.** A new table that leads back to `candidates`
  (directly or via applications, stages, interviews, notes) must be added to
  `erasure_service.ERASURE_STEPS`, `data_export_service.SECTION_LABELS` and
  `retention_service.ACTIVITY_COLUMNS`. Secrets/derived columns go in
  `OMITTED_COLUMNS`. Three tests enforce this.
- **Routes.** Every new route must be classified once in
  `audit_service.AUDITED_ROUTES` or `NOT_AUDITED`. A mutating route missing
  from `ROUTE_PERMISSIONS` (`backend/utils/permissions.py`) is admin-only by
  default. A new permission also goes in the MATRIX in `test_permissions.py`
  and is re-exported with `scripts/export_permissions.py`
  (`web/src/lib/role-permissions.json`). Interviewers are default-deny: add
  to their allowlist only what they need.
- **Endpoints using `Depends(get_db)` are plain `def`.**
- **Schema** only through a new Alembic revision, verified on a scratch DB.
- **API shape changes:** `scripts/export_openapi.py`, `npm run types:api`,
  commit `openapi.json`, `web/src/lib/schema.d.ts`, `web/src/lib/openapi.json`.
- **Web action proxies allowlist actions** (`app/api/applications/...`); a
  new pipeline or bulk action needs adding there too.
- **Scoring changes** keep the transparency trace honest: anything that moves
  a score appears in the trace and in the SCORED list; anything that must not
  stays in `UNSCORED_CANDIDATE_FIELDS` (`test_transparency.py`).
- **Score visibility:** interviewers do not see a candidate's score until they
  have submitted feedback (`can_view_feedback` / `SCORE_BEFORE_FEEDBACK`).
  Every new place that shows a score must apply the same rule.
- **AI features** go through `LLMService` with their own `task_type` (pattern:
  `job_description_draft.py` + `routers/job_drafts.py`), de-identified with
  `resume_privacy`, never fed match scores, output passed through
  `plain_dashes`. Tests mock the LLM.
- **Seed data** stays synthetic; update `scripts/seed_demo.py` so the public
  demo shows each new feature (reseeding prod is a hard stop in /st: report
  it as a follow-up instead of running a destructive reseed).
- **Timers:** follow `deploy/recruitiq-retention.*`; `deploy.sh` enables a
  timer only when its env var is set. A PR that edits `deploy.sh` needs two
  deploy runs (it pulls itself mid-run).
- No em dashes in anything a user sees.

---

## Phase 1 - Structured requirements + score caps [1]

**The team gets:** each job lists must-have skills, nice-to-have skills, a
years-of-experience range and a minimum education. A candidate missing a
must-have cannot score above 70; missing two or more caps them at 50. The
transparency trace and "explain match" say exactly which cap applied and why.

**Decided:**
- New nullable `jobs.requirements` JSONB: `must_have_skills: [str]`,
  `nice_to_have_skills: [str]`, `min_years: int|null`, `max_years: int|null`,
  `min_education: none|bachelor|master|phd`. Validated by a Pydantic model;
  limits of 20 skills per list, 60 chars per skill.
- Jobs without requirements score **exactly** as today. Pin that with a
  regression test over the seeded jobs before changing `score_pair`.
- Caps flag, never auto-reject (Slate auto-rejects; we leave the decision to
  a human).
- Must-have match reuses the existing exact/partial skill matcher in
  `matching_enhancer.py`; a partial match counts as present.
- Nice-to-haves add weight on top of the existing `skills` score; the legacy
  `skills` list stays and is what nice-to-have falls back to when empty.
- Years outside the range lower the experience sub-score; under `min_years`
  by 2+ years counts as one missing must-have for capping.
- Education uses a small normalizer (B.Tech/BSc/BA -> bachelor, MSc/MBA/MS ->
  master, PhD/DPhil -> phd) over `candidate_education.degree`; unknown
  degree = unknown, never a cap.

**Scope:**
- Backend: migration; `Job` model, `backend/models/job.py` create/update/
  response; `routers/jobs.py`; `score_pair` (`matching_integrator.py`) and the
  enhancer; `routers/transparency.py` `_pair_trace` + policy lists; assistant
  `explain_match` / `get_job` output.
- Web: `job-form.tsx` + `lib/job-form.ts` (two chip inputs, years range, min
  education select); job detail page shows requirements; transparency
  `TraceRow` shows caps. AI job draft (`job_description_draft.py`) may
  propose must-haves; optional, skip if it bloats the PR.
- Seed: give every demo job sensible requirements so caps show up live.

**Done when:** regression test proves unchanged scores without requirements;
tests for each cap, the years rule, the education normalizer and the trace;
live check on dev that a job with must-haves reorders `/matching` and the
trace explains it.

**Decide in session:** whether nice-to-haves get a separate trace line or
fold into the skills line (default: separate line).

## Phase 2 - Rank a job's applicants [2]

**The team gets:** on a job, applicants sorted by fit: a Fit column (sortable)
on the job-filtered candidate table, a score chip on pipeline board cards,
and the bulk-upload result screen listing the new applicants best first.

**Decided:**
- Scope is the job's **applicants** (`job_applications`), not the whole
  pool. The whole-pool "Matching candidates" card stays as it is.
- Score visibility rule applies (interviewers see a dash until they have
  submitted feedback for that candidate).
- Uses Phase 1's `score_pair`, so caps show here too, with a "capped" hint.

**Scope:**
- Backend: a `fit` field on `ApplicationCard` (`routers/pipeline.py` `_board`)
  and on the candidate list when `job_id` is set (`routers/candidates.py`),
  plus `sort_by=fit`; bulk upload returns the score per saved file.
- Web: `candidate-table.tsx`, `pipeline-board.tsx`, `bulk-uploader.tsx`.

**Decide in session (measure first):** live scoring vs stored scores. Time
`score_pair` over 50 applicants on dev. Under ~1s: compute live, no schema.
Over: store `job_applications.fit_score` + `fit_scored_at`, set at intake
(`intake_service.add_to_job`) and recomputed when the job's requirements or
skills change or the candidate profile is edited, with a "Rescore" button
for admins. Default expectation: live is fast enough, because the 9s today
comes from scoring every candidate through the agent, not from `score_pair`.

**Done when:** sorted table, board chips and bulk-upload ranking work on dev
for a job with 10+ applicants; interviewer-visibility test; response-time
check on the board endpoint recorded in the PR.

## Phase 3 - Job and intake hygiene [11, 12, 15, 13]

**The team gets:** a requisition number on every job (to match Workday), a
fixed department list so reports stop splitting "Eng" and "Engineering", a
real "How did they find us" picker on every way a candidate comes in, and a
Withdraw action when a candidate pulls out.

**Decided:**
- **Requisition number:** nullable `jobs.requisition_number` String(40),
  unique when set, free text (Workday's format, not ours). Shown on the job
  page, jobs list, job search, CSV export; searchable.
- **Departments:** new `departments` table (id, name unique, active), admin
  managed from the existing admin/team area. Migration seeds it from the
  distinct existing `jobs.department` values. Jobs keep the department name
  string (no FK churn); create/update validates it against active
  departments; renaming a department updates its jobs in the same
  transaction. Job form uses a select.
- **Source:** one vocabulary for application source: the `CandidateSource`
  values (linkedin, indeed, company_website, referral, agency, job_board,
  direct_application, other) plus `internal`. Picker on add-candidate panel,
  bulk uploader (one source for the batch) and "Consider for role". Existing
  free-text values are mapped by migration (`resume_upload` ->
  `direct_application`, `direct` -> `direct_application`, unknown -> `other`).
  `source_mix` labels updated.
- **Withdraw:** new pipeline action `withdraw` (candidate pulled out, any
  active stage) next to `decline`; sets `APP_WITHDRAWN`, optional reason note.
  Board `outcomes` counts withdrawn; reports and status link already know it.
  Needs: `pipeline_service.ACTIONS`, permission regex in
  `utils/permissions.py`, both web proxy allowlists, `lib/pipeline.ts`, and an
  outcome stage for withdrawn in `DEFAULT_STAGES` with a migration that adds
  it to existing jobs.

**Done when:** each of the four has backend tests, the job form and intake
screens use them, and the reports page shows clean departments and sources.

## Phase 4 - Feedback workflow [6, 7, 8]

**The team gets:** interviewers start from a template, can save a draft and
come back, submit with Ctrl+Enter, and see a badge in the nav with how many
feedback forms they owe.

**Decided:**
- **Templates:** `feedback_templates` (id, name, body, job_id nullable =
  global, created_by, updated_at). Admins and hiring managers manage them
  (global from the admin area, per job from the job page). The form offers
  the job's templates then global ones; choosing one fills the notes box.
  Not candidate data, so no erasure entry.
- **Drafts:** `feedback.status` (`draft` | `submitted`, existing rows
  `submitted`), `submitted_at` null while draft. PUT saves a draft (author
  only), POST submit finalizes as today (409 after submit stays). Drafts are
  invisible to everyone but the author, do **not** unlock score visibility,
  and still count as pending. Feedback is already in ERASURE_STEPS; add
  `updated_at` to `ACTIVITY_COLUMNS` if a column is added.
- **Shortcuts:** 1-5 sets rating when focus is not in the textarea,
  Ctrl/Cmd+Enter submits, autosave the draft on a short debounce.
- **Badge:** count of the signed-in user's pending interviews (existing
  `feedback_service.pending_feedback`), shown on the Interviews nav item via
  `PendingDot`; `SessionSidebar` fetches it with the user.

**Done when:** draft/submit/visibility tests (a draft never leaks to another
interviewer or unlocks a score), template CRUD tests with permissions, the
badge renders for an interviewer with pending feedback.

## Phase 5 - Tags in lists + time-to-outcome [9, 16]

**The team gets:** a Tags column and tag filter on the candidates list, a
"Tag" bulk action next to Advance/Reject, and median days to hire and to
reject on the dashboard and reports page.

**Decided:**
- `GET /api/candidates/?tag=a&tag=b` (all must match), shared with the CSV
  export through `_filtered_candidates`; tag counts from `GET /api/tags`
  drive the filter chips.
- Bulk tag is `POST /api/candidates/bulk/tag` (candidate ids + tag; each item
  its own savepoint, like the applications bulk endpoint), allowed from any
  candidates list, not only job-filtered.
- Medians: from `applied_at` to the hired / rejected stage change, via
  `percentile_cont` like `time_in_stage`; per job on the reports page,
  overall on the dashboard. Declines and withdrawals are not rejections.
- Tag guidance shown once in the tag input help text: never tag pay,
  health, age or other protected traits.

**Done when:** filter + bulk tag tests, medians tested against fixed
timelines, both screens updated.

## Phase 6 - AI feedback summary [3]

**The team gets:** once a candidate has 2+ submitted feedback forms for an
application, hiring managers and admins can generate a short committee
brief: themes, agreements, disagreements, open questions.

**Decided:**
- New `feedback_summary.py` following `job_description_draft.py`
  (`task_type="feedback_summary"`, structured output, `plain_dashes`).
- Input is submitted feedback only (rating, recommendation, notes), never
  drafts, never the match score. Candidate and interviewer names scrubbed
  with `resume_privacy` (promote `_name_patterns` to a public helper);
  interviewers become "Interviewer 1..n".
- Generated on demand and **not stored** (no new candidate table); the UI
  says it is AI-generated and when.
- Visible only to roles that can already see all feedback on that
  application (`can_view_feedback`); audited as a view.
- Works on the local model (private-deployment goal); eval a handful of
  synthetic feedback sets on the Ollama tier and on OpenRouter before
  merging and note the result in the PR.

**Done when:** tests with a mocked LLM (refuses under 2 submissions, drafts
excluded, names scrubbed, permission gate), live run on dev, 503 path when
providers are down.

## Phase 7 - @mentions [4]

**The team gets:** typing `@` in a note offers teammates; the person
mentioned gets an email with a link and sees unread mentions in the nav.

**Decided:**
- Stored as `@[Name](user:<id>)` in the note body; rendered as a chip.
- `note_mentions` (note_id FK cascade, user_id, created_at, read_at): leads
  back to candidates through notes, so it joins ERASURE_STEPS,
  SECTION_LABELS and ACTIVITY_COLUMNS.
- Only people who can already see the candidate can be mentioned
  (interviewers only if assigned to that candidate); the typeahead filters
  and the API refuses others with a clear message.
- The email carries the author's name and a link, **never the note text**
  (keeps candidate data out of inboxes). Sent only when SMTP is configured;
  failures logged, never block the note.
- `email_log.application_id` is NOT NULL, so staff emails are not logged
  there; log to the journal (ids only) and to `note_mentions`.
- Nav badge for unread mentions reuses Phase 4's sidebar fetch; a Mentions
  list page marks them read.

**Done when:** mention parse/permission/email tests (email body contains no
note text), erasure/export/retention coverage tests pass with the new table,
typeahead works on dev.

## Phase 8 - No-movement digest [5]

**The team gets:** a weekday-morning email to each job's recruiter and
hiring manager listing their candidates stuck in a round for 7+ days, with
links.

**Decided:**
- `scripts/digest.py` + `deploy/recruitiq-digest.{service,timer}` (weekdays
  08:00 server time, same hardening as retention). `deploy.sh` enables it
  only when `DIGEST_ENABLED=true`; the script also refuses unless
  `DEPLOYMENT_MODE=internal` and SMTP is configured.
- Recipients from `jobs.recruiter_id` / `hiring_manager_id` (the job form
  must start sending those ids; today it sends only the free-text names:
  fix that in this phase). Jobs with neither get one digest to admins.
- Reuses `reports_service.no_movement`; `NO_MOVEMENT_DAYS` becomes a setting
  (default 7) and the "7 days" copy on dashboard/reports reads it.
- Email lists candidate names and job titles (staff only, same as the app),
  no notes or scores. `--dry-run` prints recipients and counts only.

**Done when:** grouping/recipient tests, dry-run output on dev, the job form
saves recruiter/hiring manager ids, timer installed disabled on prod.
