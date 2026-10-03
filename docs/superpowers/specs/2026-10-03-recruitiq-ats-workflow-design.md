# RecruitIQ ATS workflow: design and phase blueprint

Date: 2026-10-03
Status: approved blueprint (decisions confirmed with Sean the same day)
Source review: `.claude/audits/2026-10-03-slate-ats-review.md` (Slate, a
colleague's internal hiring tracker at the same company)
Supersedes nothing. Extends the portfolio revival spec
(`2026-08-26-recruitiq-portfolio-revival-design.md`) with a workflow layer.

## 1. Goal

Turn RecruitIQ from an evaluation tool (parse, rank, explain) into an
applicant tracking system that runs the company's real hiring process end to
end, while keeping the things RecruitIQ already does better than Slate:
explainable scores, de-identified prompts, a local-model option, and an
assistant that does not fabricate.

"Mirror Slate, but cleaner, less cluttered, in proper English."

## 2. Decisions

Confirmed with Sean on 2026-10-03:

| Question | Decision |
|---|---|
| Default pipeline | Slate's 11 stages. Every job can turn stages off. |
| Project layer above jobs | No. `department` on the job is the grouping. |
| User roles | Four: Admin, Hiring Manager, Hiring Team, Interviewer. |
| AI score visibility | Interviewers do not see the score until they have submitted feedback on that candidate. Admin, Hiring Manager, and Hiring Team always see it. |

Design decisions made while writing this blueprint:

1. **Rounds and outcomes are different kinds of stage.** Slate lists "Offer
   declined" and "Candidate joined" as stages 10 and 11 and lets you "advance"
   into them, which makes no sense (you cannot pass through "declined" to
   reach "hired"). RecruitIQ keeps all 11 names visible on the timeline, but
   stages 1 to 9 are `round` and stages 10 and 11 are `outcome`. Advance from
   the last enabled round lands on the Hired outcome. Reject at any round sets
   the Rejected outcome (an application status, not a stage). Decline is a
   separate action available only at Offer and Offer accepted.
2. **One application per candidate per job.** Slate clones the candidate row
   for each role. RecruitIQ already has `job_applications` as the link table,
   so "consider for another role" creates a second application for the same
   candidate. One person, one profile, many pipelines.
3. **`candidates.status` becomes a derived value.** The dashboard, the
   candidates table, and the stage chips all read it today. Rather than
   rewriting them, every pipeline transition recomputes it from the
   application just touched (see 3.3). It stays in the table, but nothing
   writes it directly any more except the pipeline service.
4. **Writes stay admin-only until Phase B.** The existing read-only gate
   already covers every new POST route by default. Phase B introduces the
   four roles and the per-role rules.
5. **Stage customisation is enable/disable and rename in Phase A.** Custom
   stages and reordering are Phase E. Most of the value is in turning off
   rounds a job does not run.
6. **No projects, no bench, no calendar, no scheduled reports, no interview
   skill profiles.** Each can be added later without reworking the schema
   below.

## 3. Target data model (all phases)

Existing tables are listed only where they change. Every new table gets an
Alembic revision, verified on a scratch database (CLAUDE.md database rule).

### 3.1 New tables

**`pipeline_stages`** (Phase A). One row per stage per job. Copied from
`DEFAULT_STAGES` when a job is created, or lazily the first time a job's
pipeline is read.

| column | type | notes |
|---|---|---|
| id | serial PK | |
| job_id | int FK jobs ON DELETE CASCADE | |
| key | varchar(50) | stable identifier, e.g. `hm_review` |
| name | varchar(100) | shown in the UI, editable per job |
| description | text | candidate-facing "what to expect" copy |
| kind | varchar(20) | `round` or `outcome` |
| position | int | display order |
| enabled | bool | disabled rounds are skipped automatically |
| unique (job_id, key) | | |

**`application_stages`** (Phase A). One row per stage per application. This
is the history.

| column | type | notes |
|---|---|---|
| id | serial PK | |
| application_id | int FK job_applications ON DELETE CASCADE | |
| stage_id | int FK pipeline_stages ON DELETE CASCADE | |
| status | varchar(20) | `pending`, `in_progress`, `passed`, `failed`, `skipped` |
| started_at | timestamp | set when it becomes in_progress |
| completed_at | timestamp | set on passed, failed, skipped |
| changed_by | varchar(36) FK users nullable | who moved it (Phase B fills it) |
| note | text nullable | optional reason given on reject or skip |
| unique (application_id, stage_id) | | |

**`interviews`** (Phase B). Replaces the in-memory mock router.

| column | type |
|---|---|
| id | serial PK |
| application_stage_id | int FK application_stages ON DELETE CASCADE |
| interviewer_id | varchar(36) FK users |
| assignment_source | varchar(20): `manual` or `default` |
| created_at | timestamp |
| unique (application_stage_id, interviewer_id) | |

**`feedback`** (Phase B).

| column | type |
|---|---|
| id | serial PK |
| interview_id | int FK interviews ON DELETE CASCADE, unique |
| rating | smallint 1 to 5 |
| recommendation | varchar(20): `strong_hire`, `hire`, `no_hire`, `strong_no_hire` |
| notes | text |
| submitted_at | timestamp |

**`stage_default_interviewers`** (Phase B). `pipeline_stage_id`,
`user_id`. Auto-assigned when an application reaches that stage.

**`notes`** (Phase C). Replaces the single `candidates.notes` text column.

| column | type |
|---|---|
| id | serial PK |
| candidate_id | varchar(36) FK candidates ON DELETE CASCADE |
| application_id | int FK nullable (null means candidate-level) |
| stage_id | int FK nullable (set means stage-level) |
| author_id | varchar(36) FK users |
| body | text |
| created_at | timestamp |

**`candidate_tags`** (Phase C). `candidate_id`, `tag` varchar(50), unique
pair. Tags are lower-kebab-case on write.

**`email_templates`** and **`email_log`** (Phase E).

**`job_templates`** is not a table. "Start from an existing job" on the new
job form copies fields from a chosen job (Phase E).

### 3.2 Changed tables

- `job_applications.status` vocabulary becomes `active`, `hired`,
  `rejected`, `declined`, `withdrawn`. The Phase A migration maps the old
  values: `accepted` to `hired`, `rejected` stays, everything else to
  `active`.
- `job_applications` gains `public_token` varchar(36) unique (Phase E) for
  the candidate status link.
- `users` gains `name` varchar(100) and the `role` column accepts
  `admin`, `hiring_manager`, `hiring_team`, `interviewer`, `demo` (Phase B).
- `jobs.hiring_manager` and `jobs.recruiter` stay free text in Phase A and
  gain optional `hiring_manager_id` and `recruiter_id` FKs in Phase B. The
  text columns are kept for display and seed data.
- `candidates.notes` is read-only after Phase C and dropped in a later
  cleanup once the notes table has been live for one release.

### 3.3 Derived candidate status

`candidates.status` is recomputed by the pipeline service after every
transition, from the application that was just changed:

| application state | candidate.status |
|---|---|
| active, current stage `resume_submitted` | `active` |
| active, current stage `hm_review` | `screening` |
| active, current stage any round from `technical_written` to `hr_screen` | `interviewing` |
| active, current stage `offer` or `offer_accepted` | `offered` |
| `hired` | `hired` |
| `rejected` | `rejected` |
| `declined` or `withdrawn` | `withdrawn` |

A candidate with two applications shows the status of whichever one moved
last. That is acceptable for Phase A and revisited if it confuses anyone.

## 4. The 11 default stages

Canonical keys, names, kinds, and candidate-facing descriptions. The names
are the "proper English" versions of Slate's.

| # | key | name | kind | description |
|---|---|---|---|---|
| 1 | resume_submitted | Resume submitted | round | We have your resume and are reviewing it. |
| 2 | hm_review | Hiring manager review | round | The hiring manager reviews your background against the role. |
| 3 | technical_written | Technical assessment | round | A take-home or written exercise on the fundamentals of the role. |
| 4 | technical_interview | Technical interview | round | A live conversation going deep on your primary area. |
| 5 | problem_solving | Problem solving | round | An open-ended reasoning session with the team. |
| 6 | case_study | Case study | round | A scenario-based discussion with a small panel. |
| 7 | hr_screen | HR screen | round | A final conversation about logistics, timing, and references. |
| 8 | offer | Offer | round | An offer has been extended. |
| 9 | offer_accepted | Offer accepted | round | You have accepted. We are completing paperwork and a start date. |
| 10 | offer_declined | Offer declined | outcome | You declined the offer. |
| 11 | hired | Hired | outcome | Welcome aboard. |

Transitions:

- **Advance**: current round passed, next enabled round in progress. From
  the last enabled round, the application becomes `hired` and the Hired
  outcome row is marked passed.
- **Skip**: current round skipped, next enabled round in progress. Not
  available on the last enabled round.
- **Reject**: current round failed, every later pending row skipped,
  application `rejected`.
- **Decline**: only at Offer or Offer accepted. Current round passed, Offer
  declined outcome row passed, later rows skipped, application `declined`.
- A terminal application (`hired`, `rejected`, `declined`, `withdrawn`)
  refuses every action with 409.
- All four run in one database transaction.

## 5. Screens after all phases

Changes only. Everything not listed stays as it is today.

| Screen | Phase | Change |
|---|---|---|
| Dashboard `/` | D | Funnel by stage (ever reached vs currently here), "needs attention" list (no movement in 7+ days, pending feedback), activity feed. Keep three tiles, drop nothing that exists. |
| Jobs `/jobs` | A | Card shows active-application count from the pipeline, not the stored counter. |
| Job detail `/jobs/[id]` | A | New Pipeline card above Matching: one column per enabled stage, candidate chips, outcome counts. Stage settings (enable, disable, rename) behind an admin-only "Edit stages" control. |
| Job form | E | "Start from an existing job" picker that copies fields. |
| Candidates `/candidates` | C | "Add candidate" button, job filter, CSV export, checkbox bulk advance and reject. Keep the search box and stage chips. |
| Candidate detail `/candidates/[id]` | A | Replace the Applications card with one Pipeline card per application: stage timeline, current stage highlighted, Advance, Skip, Reject, Decline for writers. |
| Candidate detail | B | Interviewers section per stage (assign), Feedback section (rating, recommendation, notes), score hidden from interviewers until they submit. |
| Candidate detail | C | Notes thread (candidate-level and per stage), tags, "Consider for another role". |
| Upload `/upload` | C | After parsing, "Add to [job] pipeline" creates the application. Bulk upload. |
| Interviews `/interviews` | B | New. My rounds, pending feedback, all (for managers). |
| Reports `/reports` | D | New. Funnel, time in stage, no-movement list, source mix, CSV export. |
| Team `/team` | B | New. Users table, invite by email, change role (admin). |
| Settings `/settings` | B | New. Own name, timezone. |
| Public status `/c/[token]` | E | New. First name, role, stage timeline with descriptions. No scores, no names, no notes. |
| Assistant | B, D | New tools: pipeline state for a job, who is at a stage, pending feedback. Score visibility rule applies to the assistant too. |
| Transparency | B | New card: "What feedback is and is not used for". Feedback never feeds the scorer. |

## 6. Navigation

Once Interviews, Reports, and Team exist the top bar is full. Move to a
grouped sidebar at `lg` and up, icons-only rail below, same light theme:

- **Hiring**: Dashboard, Jobs, Candidates, Interviews
- **Intelligence**: Matching, Upload, Assistant, Transparency
- **Admin**: Reports, Team, Settings

Phase A keeps the current top bar. The sidebar lands with Phase B when the
item count first exceeds eight.

## 7. Terminology (canonical)

| Use | Not |
|---|---|
| Job, requisition | Role, SR, SR number |
| Department | Practice, Account, Client |
| Hiring manager | HM |
| Hiring team | Hiring_team, recruiter (as a role name) |
| Stage | Round (except in prose about interview rounds) |
| In progress, Passed, Skipped, Rejected | in_progress, passed, failed |
| Hired | Joined, Candidate joined |
| Offer declined | Rejected offer, Declined |
| HR screen | HC Evaluation |
| Technical assessment | Technical written |
| Feedback (singular) | Feedbacks |
| No movement in 7+ days | Stale |
| Export | HTML report |
| American spelling throughout | Mixed |

No em dashes anywhere a user can read. No vendor names in product copy.

## 8. Phases

Each phase is independently shippable and demoable with the seed data.
Each gets its own implementation plan in `docs/superpowers/plans/`.

### Phase A: Pipeline core (plan written: `2026-10-03-ats-phase-a-pipeline-core.md`)

Scope: the two tables, the pipeline service, the transition endpoints,
stage enable/disable/rename, the job-page board, the candidate-page
timeline with actions, seed and migration backfill, assistant untouched.

Acceptance:
- `GET /api/jobs/{id}/pipeline` returns 11 stages for any job, including
  jobs created before the migration.
- Advance, Skip, Reject, Decline behave per section 4, atomically, and
  refuse terminal applications with 409.
- The demo role gets 403 on all four actions (covered by the existing
  route-walking auth test without new code).
- Dashboard and candidates table keep working unchanged, because
  `candidates.status` is kept in sync.
- Fresh database plus `alembic upgrade head` plus `seed_demo.py` yields a
  populated board on every job.

### Phase B: Team and feedback (plan written: `2026-10-03-ats-phase-b-team-feedback.md`)

Scope: four roles and `name` on users, invite flow (admin creates user with
a temporary password; no email yet), permission matrix in
`enforce_read_only` and per-route checks, `interviews` and `feedback`
tables, stage default interviewers, assign on the candidate page, Interviews
page, feedback form (1 to 5, recommendation, notes), score hiding for
interviewers, Team and Settings pages, sidebar navigation, assistant tool
for pending feedback.

Permission matrix (from Slate, adopted as is):

| Action | Admin | Hiring Manager | Hiring Team | Interviewer |
|---|---|---|---|---|
| Create or edit jobs | yes | yes | no | no |
| Add candidates | yes | yes | yes | no |
| Advance, skip, reject, decline | yes | yes | yes | no |
| Submit feedback on assigned stage | yes | yes | yes | yes |
| Invite users | yes | yes | no | no |
| Change another user's role | yes | no | no | no |
| Delete candidate, job, user | yes | no | no | no |
| See AI score before own feedback | yes | yes | yes | no |

Acceptance: an interviewer account can see only the candidates they are
assigned to, cannot see a score until their feedback exists, and the
transparency page states that feedback never reaches the scorer.

### Phase C: Intake, notes, tags (plan written: `2026-10-03-ats-phase-c-intake-notes-tags.md`)

Scope: upload page ends with "Add to [job] pipeline"; manual add candidate
(name, email, job); bulk upload (sequential, progress list); `notes` table
with candidate-level and stage-level threads; `candidate_tags`; "Consider
for another role"; Candidates page gains Add candidate, job filter, CSV
export, bulk advance and reject.

Acceptance: a resume dropped on Upload becomes a candidate at stage 1 of
the chosen job with no further clicks, and the save path is exercised live
(unit tests have missed save-path bugs before).

### Phase D: Reports and dashboard (plan written: `2026-10-03-ats-phase-d-reports-dashboard.md`)

Scope: Reports page (funnel ever-reached vs here, median time in stage,
no-movement list, source mix, hires and rejections this quarter, CSV
export of the filtered candidate list), dashboard funnel and attention
list, activity feed from `application_stages` timestamps. No PDF, no
scheduling, no fabricated trend lines.

Acceptance: every number on Reports is a query over `application_stages`
and the page says so, matching the dashboard's "every number is a query"
line.

### Phase E: Candidate-facing and templates (plan written: `2026-10-03-ats-phase-e-candidate-facing.md`)

Scope: public status page on `job_applications.public_token`; email
templates (interview invite, resume request, polite close, offer) with a
log, sent through SMTP configured in `/etc/recruitiq/env`, with a "no
transport configured" state that still lets you copy the text; "start from
an existing job"; optional AI job description draft through the existing
provider chain and de-identification rules; custom stages and reordering.

Acceptance: the public page shows nothing but first name, job title,
department, stage timeline, and descriptions, and a test pins that it
carries no score, no email, and no internal names (same pattern as
`test_traces_carry_no_contact_details`).

## 9. Non-goals

Bench, scheduled reports, interview skill profiles, calendar availability,
projects above jobs, cloning candidate rows per role, dark theme, PDF
export, trend sparklines without real data, a floating chatbot (the
Assistant page stays).

## 10. Risks and rules carried from the project

- New endpoints that take `Depends(get_db)` are plain `def`, never
  `async def` (CLAUDE.md sharp edge). The pipeline router follows this.
- Any route or response-model change requires
  `poetry run python scripts/export_openapi.py`, `cd web; npm run types:api`,
  and committing both `openapi.json` and `web/src/lib/schema.d.ts`.
  Adding fields to `CandidateApplicationSummary` also requires
  `UPDATE_API_GOLDEN=1` and a line-by-line read of the golden diff.
- Migrations are verified on a scratch database before the suite runs.
- The seed script stays self-sufficient and fully synthetic. Slate's seed
  data contains real names and real job descriptions; none of it is copied.
- Embedded text does not change in Phases A to D, so no re-embed is needed.
- The read-only demo must keep working on every screen, including the new
  ones, because visitors from Sean's resume land there.
