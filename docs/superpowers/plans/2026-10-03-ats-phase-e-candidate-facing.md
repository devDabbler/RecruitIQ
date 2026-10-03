# ATS Phase E: Candidate-Facing Status, Email Templates, Job Drafting, Custom Stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give candidates a private status link showing only their first name, the job, and the stage timeline; let the hiring team email candidates from four editable templates (sent over SMTP when configured, copied by hand when not, logged either way); let job writers start a job from an existing one or from an AI draft; and let job writers add, remove, and reorder interview stages from an "Edit stages" screen on the job page.

**Architecture:** Three new backend services (`status_link_service`, `email_service`, `job_description_draft`) behind three new routers, plus custom-stage functions added to the existing `pipeline_service` and an extended `PUT /api/jobs/{id}/pipeline`. One Alembic revision adds `job_applications.public_token`, `email_templates` (seeded with four defaults), and `email_log`. On the web side the app shell moves into an `(app)` route group so the public `/c/[token]` page renders with no navigation and no session; the candidate page gains a "Candidate communication" section; the job form gains "Start from an existing job" and "Draft with AI"; a new `/jobs/[id]/stages` editor and a new `/email-templates` page are added.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic + `smtplib` (backend), Next.js 16 App Router + Tailwind + Vitest + Playwright (web), pytest with the transactional fixtures in `backend/tests/conftest.py`.

**Spec:** `docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md` (sections 3.1, 3.2, 5 rows marked E, 8 Phase E) plus the Phase A deferral recorded in `2026-10-03-ats-phase-a-pipeline-core.md` self-review: the admin "Edit stages" control.

**Prerequisite:** Phases A, B, C, and D are merged to `main`. This plan only *uses* names those phases define; see "Assumptions about earlier phases" below and check each one before starting.

---

## Assumptions about earlier phases

Phases B to D were planned in parallel with this one, so their code did not exist when this plan was written. Everything below is fixed by the shared contract. Before Task 1, confirm each with a grep; if a name differs, use the real name everywhere this plan uses the assumed one and note it in the PR body.

| Assumed | Owner | Check |
|---|---|---|
| `backend/utils/permissions.py` exports `JOBS_WRITE`, `PIPELINE_MOVE`, `TEMPLATES_MANAGE`, `can(role, permission)`, `require(permission)`, and a module-level list `ROUTE_PERMISSIONS` of `(method, path_regex, permission)` entries that `enforce_read_only` consults | B | `Select-String backend/utils/permissions.py -Pattern "ROUTE_PERMISSIONS\|def require\|TEMPLATES_MANAGE"` |
| `require(permission)` returns a plain callable suitable for `Depends(require(X))` that resolves to the `User` and raises 403 otherwise. **If B's `require()` already returns a `Depends(...)` object, drop the outer `Depends(...)` in every signature below.** | B | read `def require` |
| `ROUTE_PERMISSIONS` is built by a comprehension that compiles an inner list of `(method, pattern_string, permission)` tuples (settled by the Phase B plan). Append this plan's rows to that **inner** list as plain strings; do not `re.compile` them yourself. Paths are matched with `fullmatch`, so the `^...$` anchors below are harmless. | B | read the list |
| `ROLE_HIRING_MANAGER = "hiring_manager"`, `ROLE_HIRING_TEAM = "hiring_team"`, `ROLE_INTERVIEWER = "interviewer"` in `backend/utils/auth.py` | B | grep |
| `users.name` column exists (`User.name`, nullable `String(100)`) | B | grep `name = Column` in `class User` |
| `backend/services/access_service.py` exports `visible_candidate_ids(db, user) -> Optional[set[str]]` that accepts any `User` (including admin and demo) and returns `None` for "no restriction" | B | read it |
| `web/src/lib/permissions.ts` exports `can(role, permission)` and the constants `JOBS_WRITE`, `PIPELINE_MOVE`, `TEMPLATES_MANAGE` with the same string values as the backend | B | grep |
| `web/src/lib/session.ts` `getUser()` returns `{ role, name, ... } \| null`; `canWrite()` means "may move the pipeline" (admin, hiring manager, hiring team) | B | read it |
| `web/src/lib/nav.ts` exports `NAV_GROUPS: { label: string; items: { href: string; label: string; icon: LucideIcon }[] }[]` with an `"Admin"` group | B | read it |
| `web/src/app/layout.tsx` renders the whole app shell (header or sidebar, `<main>`, footer) inside `<body>` | B | read it |
| `/jobs/new` and `/jobs/[id]/edit` redirect anyone without `JOBS_WRITE` | B | read both pages |
| The Alembic head is C's `e6a0c3d4f5b6` (D adds no migration by default) | C, D | `cd backend; poetry run alembic heads` |

Nothing from Phase C or D is required by this plan beyond the migration head.

---

## Conventions for every task

- Work on branch `ats-candidate-facing`, created from `origin/main`.
- Backend tests run from the repo root with the dev database:
  ```powershell
  $env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
  $env:OLLAMA_BASE_URL = "http://localhost:1"
  poetry run pytest backend/tests/test_custom_stages.py -q -p no:cacheprovider
  ```
- Web tests run from `web/`: `npm test`, `npm run typecheck`, `npm run lint`.
- Commit with `git commit -F <file>` (never `-m` with a here-string). No attribution trailers of any kind.
- No em dashes in any string a user can read, including email templates and model prompts. American spelling. Spec section 7 terms ("Hiring manager", "Hired", "Offer declined", "No movement in 7+ days").
- New endpoints that take `Depends(get_db)` are plain `def`. The one `async def` endpoint in this plan (`POST /api/job-drafts/description`) takes no `get_db` itself; its `require()` dependency is a sync `def` that FastAPI runs in the threadpool.
- Backend test fixtures that create rows and then call a route **commit**, never only flush. A route that answers 409 calls `db.rollback()`, which rolls the shared test session back to its last commit and would delete anything a test merely flushed (Phase A lesson).
- Python files are written with the Edit/Write tools or `[IO.File]::WriteAllText`, never `Set-Content -Encoding utf8` (it adds a BOM).
- Every new mutating route goes into `ROUTE_PERMISSIONS` and gets a test that the demo role gets 403 and the wrong staff role gets 403.

## File structure

| File | Responsibility |
|---|---|
| `backend/services/pipeline_service.py` | Modify: never re-open a decided round; custom stage add/remove/reorder; unknown stage keys map to `interviewing` |
| `backend/models/pipeline.py` | Modify: `StageOut.custom`, `StageOut.movable`, `NewStage`, extended `PipelineUpdateRequest` |
| `backend/routers/pipeline.py` | Modify: `PUT /api/jobs/{id}/pipeline` handles `remove`, `stages`, `order`, `add` in one transaction |
| `backend/alembic/versions/f7b1d4e5a6c7_public_status_and_email.py` | Create: `public_token` columns, `email_templates` with four defaults, `email_log` |
| `backend/models/models.py` | Modify: `JobApplication.public_token`, `public_token_created_at`; `EmailTemplate`, `EmailLog` |
| `backend/models/public_status.py` | Create: `PublicStage`, `PublicStatus`, `StatusLinkOut` |
| `backend/services/status_link_service.py` | Create: issue, revoke, find by token, build the allowlisted public view |
| `backend/routers/application_access.py` | Create: `visible_application_or_404` shared by the new application routes |
| `backend/routers/status_links.py` | Create: public status GET, candidate-view preview, status-link GET/POST/DELETE |
| `backend/utils/config.py` | Modify: SMTP settings and `public_app_url` |
| `backend/services/email_service.py` | Create: placeholders, render, unknown-placeholder check, SMTP send |
| `backend/models/email.py` | Create: template, preview, send, and log shapes |
| `backend/routers/emails.py` | Create: templates list/update, preview, log, send |
| `backend/models/job_draft.py` | Create: `JobDraftRequest`, `JobDescriptionDraft` |
| `backend/services/job_description_draft.py` | Create: scrubbed prompt, call through `LLMService` (which uses `build_chain`), dash cleanup |
| `backend/routers/job_drafts.py` | Create: `POST /api/job-drafts/description` |
| `backend/utils/permissions.py` | Modify: six `ROUTE_PERMISSIONS` entries |
| `backend/main.py` | Modify: mount the three routers **above** the pipeline router |
| `backend/tests/phase_e_helpers.py` | Create: `make_application`, `staff_client` |
| `backend/tests/test_custom_stages.py` | Create |
| `backend/tests/test_status_links.py` | Create (includes the pinned no-leak test) |
| `backend/tests/test_email.py` | Create |
| `backend/tests/test_job_drafts.py` | Create |
| `openapi.json`, `web/src/lib/schema.d.ts` | Regenerated |
| `web/src/lib/forward.ts` + test | Create: one helper for every new Next route handler |
| `web/src/app/api/applications/[id]/status-link/route.ts` | Create |
| `web/src/app/api/applications/[id]/emails/route.ts` | Create |
| `web/src/app/api/applications/[id]/emails/preview/route.ts` | Create |
| `web/src/app/api/email-templates/[key]/route.ts` | Create |
| `web/src/app/api/jobs/[id]/pipeline/route.ts` | Create |
| `web/src/app/api/job-drafts/description/route.ts` | Create |
| `web/src/lib/public-paths.ts` + test | Create: which paths never get a demo session |
| `web/src/proxy.ts` | Modify: skip public paths |
| `web/src/app/layout.tsx` | Modify: html, body, fonts, metadata only |
| `web/src/app/(app)/layout.tsx` | Create: the app shell moved out of the root layout |
| `web/src/app/(app)/...` | Move: every existing page directory |
| `web/src/app/(public)/layout.tsx`, `(public)/c/[token]/page.tsx` | Create: the candidate-facing page |
| `web/src/lib/public-status.ts` + test | Create: labels, greeting, token shape |
| `web/src/components/public-status-view.tsx` | Create: shared by the public page and the staff preview |
| `web/src/app/(app)/applications/[id]/candidate-view/page.tsx` | Create: staff and demo preview |
| `web/src/lib/email-composer.ts` + test | Create: placeholder checks, clipboard text, send state |
| `web/src/components/status-link-control.tsx` | Create |
| `web/src/components/email-composer.tsx` | Create |
| `web/src/components/application-outreach.tsx` | Create: status link, composer, history under each timeline |
| `web/src/components/application-timeline.tsx` | Modify: accept `children` |
| `web/src/app/(app)/candidates/[id]/page.tsx` | Modify: pass outreach data |
| `web/src/app/(app)/email-templates/page.tsx`, `web/src/components/template-editor.tsx` | Create |
| `web/src/lib/nav.ts` | Modify: Email templates under Admin |
| `web/src/lib/job-form.ts` + test | Modify: `copyJobValues`, draft helpers |
| `web/src/components/copy-from-job.tsx` | Create |
| `web/src/components/job-form.tsx` | Modify: "Draft with AI" |
| `web/src/app/(app)/jobs/new/page.tsx` | Modify: `?from=` and the picker |
| `web/src/lib/stage-editor.ts` + test | Create |
| `web/src/components/stage-editor.tsx` | Create |
| `web/src/app/(app)/jobs/[id]/stages/page.tsx` | Create |
| `web/src/app/(app)/jobs/[id]/page.tsx` | Modify: "Edit stages" link |
| `web/src/lib/domain.ts`, `web/src/lib/data.ts` | Modify: aliases and fetchers |
| `web/e2e/public-status.spec.ts` | Create: the public page mints no session |

---

### Task 1: Branch, and stop transitions from re-opening decided rounds

Custom stages and reordering can put a round that already happened (passed or skipped) *after* the current one. Today `_next_enabled_round` returns the next enabled round whatever its status, so Advance would set a passed round back to in progress. Fix that first, with regression tests, before anything can reorder.

**Files:**
- Create: `backend/tests/phase_e_helpers.py`
- Create: `backend/tests/test_custom_stages.py`
- Modify: `backend/services/pipeline_service.py` (`_next_enabled_round`, `skip`, `sync_candidate_status`)

- [ ] **Step 1: Create the branch and confirm the assumptions**

```powershell
git fetch origin
git switch -c ats-candidate-facing origin/main
Select-String backend/utils/permissions.py -Pattern "ROUTE_PERMISSIONS|def require|TEMPLATES_MANAGE|JOBS_WRITE|PIPELINE_MOVE"
Select-String backend/services/access_service.py -Pattern "def visible_candidate_ids"
Select-String backend/models/models.py -Pattern "name = Column\(String\(100\)"
cd backend; poetry run alembic heads; cd ..
```

Expected: every pattern found; one head. Write the head id down for Task 4.

- [ ] **Step 2: Write the shared test helpers**

Create `backend/tests/phase_e_helpers.py`:

```python
"""Helpers shared by the Phase E test files.

`make_application` builds its own job, candidate, and application so a test
never depends on (or disturbs) the session-wide seed, and it commits: a route
that answers 409 rolls the shared session back to its last commit, which
would otherwise delete rows a test had only flushed.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from backend.main import app
from backend.models.models import Candidate, Job, JobApplication, User
from backend.services import pipeline_service as ps
from backend.utils.auth import create_access_token

SEED_EMAIL_DOMAIN = "recruitiq-seed.example.com"
APPLIED_AT = datetime(2025, 1, 1, 12, 0, 0)


def make_application(
    db_session,
    *,
    job: Job | None = None,
    first_name: str = "Mira",
    last_name: str = "Quillfeather",
    hiring_manager: str = "Hollis Brandt",
    recruiter: str = "Ines Marlow",
) -> tuple[Job, JobApplication]:
    """A fresh candidate applied to `job` (a new job when None), started at stage 1."""
    if job is None:
        job = Job(
            title="Platform Engineer",
            department="Engineering",
            job_overview="Build the platform.",
            required_qualifications="Python, 4+ years",
            location="Remote",
            location_type="remote",
            job_type="full_time",
            experience_level="mid",
            hiring_manager=hiring_manager,
            recruiter=recruiter,
            status="open",
            skills="Python,SQL",
            job_metadata={},
            views=0,
            applications=0,
        )
        db_session.add(job)
        db_session.flush()

    candidate_id = str(uuid.uuid4())
    db_session.add(
        Candidate(
            id=candidate_id,
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name.lower()}-{candidate_id[:8]}@{SEED_EMAIL_DOMAIN}",
            phone="+1-555-0199",
            status="active",
            source="referral",
            notes="Internal: expects a counter offer.",
        )
    )
    db_session.flush()

    application = JobApplication(
        job_id=job.id,
        candidate_id=candidate_id,
        applied_at=APPLIED_AT,
        updated_at=APPLIED_AT,
        source="referral",
    )
    db_session.add(application)
    db_session.flush()
    ps.start_application(db_session, application)
    db_session.commit()
    return job, application


def staff_user(db_session, role: str, name: str | None = None) -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role=role,
        name=name or f"Test {role.replace('_', ' ').title()}",
    )
    db_session.add(user)
    db_session.commit()
    return user


def staff_client(db_session, role: str) -> TestClient:
    """A client signed in as a fresh user with `role`. Needs `override_get_db`."""
    token = create_access_token(staff_user(db_session, role))
    return TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Authorization": f"Bearer {token}"},
    )


def keys_by_status(application: JobApplication, status: str) -> list[str]:
    rows = sorted(application.stages, key=lambda r: r.stage.position)
    return [r.stage.key for r in rows if r.status == status]
```

- [ ] **Step 3: Write the failing tests**

Create `backend/tests/test_custom_stages.py`:

```python
"""Custom stages, reordering, and the transitions that must survive them (ATS Phase E)."""
from __future__ import annotations

import pytest

from backend.models.models import Candidate
from backend.services import pipeline_service as ps
from backend.tests.phase_e_helpers import keys_by_status, make_application, staff_client


def _rows(application):
    return {r.stage.key: r for r in application.stages}


# --- transitions never re-open a decided round -------------------------------


def test_advance_does_not_reopen_a_decided_round(db_session):
    _, application = make_application(db_session)
    ps.advance(db_session, application)  # hm_review
    ps.advance(db_session, application)  # technical_written
    # A round ahead of the current one that already happened, which is what a
    # reorder can produce.
    _rows(application)["technical_interview"].status = ps.PASSED
    db_session.flush()

    ps.advance(db_session, application)

    assert ps.current_stage(application).stage.key == "problem_solving"
    assert _rows(application)["technical_interview"].status == ps.PASSED


def test_skip_refused_when_only_decided_rounds_remain(db_session):
    _, application = make_application(db_session)
    for _ in range(7):
        ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "offer"
    _rows(application)["offer_accepted"].status = ps.PASSED
    db_session.flush()

    with pytest.raises(ps.PipelineError):
        ps.skip(db_session, application)
    assert ps.current_stage(application).stage.key == "offer"

    ps.advance(db_session, application)
    assert application.status == "hired"
```

- [ ] **Step 4: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_custom_stages.py -q -p no:cacheprovider`
Expected: 2 failed. The first lands on `technical_interview`; the second skips into the passed `offer_accepted` row instead of refusing.

- [ ] **Step 5: Fix the service**

In `backend/services/pipeline_service.py`, replace `_next_enabled_round` with:

```python
def _next_enabled_round(rows: list[ApplicationStage], after: ApplicationStage) -> Optional[ApplicationStage]:
    """The next enabled, still-pending round after `after`.

    Rounds that were already decided (passed, failed, or skipped) are passed
    over, never re-opened: since Phase E a job can reorder its rounds, so a
    round that happened can sit after the current one. Disabled pending rounds
    passed over are marked skipped, as before.
    """
    for row in rows:
        if row.stage.position <= after.stage.position:
            continue
        if row.stage.kind != ROUND:
            continue
        if row.status != PENDING:
            continue
        if row.stage.enabled:
            return row
        row.status = SKIPPED
        row.completed_at = datetime.utcnow()
    return None
```

In `skip`, replace the look-ahead condition with:

```python
    if not any(
        r.stage.position > current.stage.position
        and r.stage.kind == ROUND
        and r.stage.enabled
        and r.status == PENDING
        for r in rows
    ):
```

In `sync_candidate_status`, change the last line so a stage key the table does not know (every custom stage, from Task 2 on) reads as an interview round:

```python
    if current is not None:
        # Unknown keys are custom stages, which always sit between Resume
        # submitted and the offer, so they are interview rounds.
        candidate.status = _STAGE_TO_CANDIDATE_STATUS.get(current.stage.key, "interviewing")
```

- [ ] **Step 6: Run the tests, including Phase A's**

Run: `poetry run pytest backend/tests/test_custom_stages.py backend/tests/test_pipeline.py -q -p no:cacheprovider`
Expected: all pass (2 new plus the Phase A file).

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e1.txt`:

```
fix: transitions never re-open a round that already happened

Advance and Skip looked for the next enabled round regardless of its
status. Harmless while stage order was fixed, but Phase E lets a job
reorder its rounds, which can put a passed round after the current one.
Both now look only at pending rounds. Unknown stage keys (custom stages,
next commit) map the candidate to "interviewing". Verified with two
regression tests plus the Phase A pipeline suite.
```

```powershell
git add backend/services/pipeline_service.py backend/tests/phase_e_helpers.py backend/tests/test_custom_stages.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e1.txt
```

---

### Task 2: Custom stages in the pipeline service

Rules, decided here because the spec only says "custom stages and reordering":

- Resume submitted always stays first. Offer and Offer accepted always stay the last two rounds (Decline and the web action rules depend on their keys). Outcomes always stay last. Everything in between ("interview stages") can be reordered, and new stages always land in that middle band.
- Custom stage keys are `custom_<slug>`, unique per job (`_2`, `_3` on collision). A job can have at most 10.
- Adding a stage while candidates are mid-pipeline: anyone already past the new stage (or finished) gets a `skipped` row with a note saying it was added later; anyone before it gets a `pending` row and will pass through it.
- Reordering: an active candidate whose pending round moves behind their current round gets that row `skipped` with a note. A round that already happened and moves ahead stays as it was (Task 1 makes transitions pass over it).
- Removing: only custom stages, and only if no candidate has been in progress at it, passed it, or been rejected there. Otherwise the user is told to turn it off.

**Files:**
- Modify: `backend/services/pipeline_service.py`
- Test: `backend/tests/test_custom_stages.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_custom_stages.py`:

```python
# --- adding stages -------------------------------------------------------------


def _keys(db_session, job_id):
    return [s.key for s in ps.ensure_job_stages(db_session, job_id)]


def test_add_stage_defaults_to_just_before_the_offer(db_session):
    job, _ = make_application(db_session)
    stage = ps.add_custom_stage(db_session, job.id, "Portfolio review", "Walk us through past work.")
    keys = _keys(db_session, job.id)
    assert stage.key == "custom_portfolio_review"
    assert keys.index("custom_portfolio_review") == keys.index("offer") - 1
    assert keys[0] == "resume_submitted"
    assert keys[-2:] == ["offer_declined", "hired"]
    assert [s.position for s in ps.ensure_job_stages(db_session, job.id)] == list(range(1, 13))
    assert ps.is_custom(stage) and ps.is_movable(stage)


def test_add_stage_after_a_given_round_and_keys_stay_unique(db_session):
    job, _ = make_application(db_session)
    first = ps.add_custom_stage(db_session, job.id, "Pair programming", after_key="resume_submitted")
    second = ps.add_custom_stage(db_session, job.id, "Pair programming", after_key="hm_review")
    keys = _keys(db_session, job.id)
    assert keys[:4] == ["resume_submitted", first.key, "hm_review", second.key]
    assert second.key == "custom_pair_programming_2"


def test_add_stage_refused_after_the_offer_or_without_a_name(db_session):
    job, _ = make_application(db_session)
    with pytest.raises(ps.PipelineError):
        ps.add_custom_stage(db_session, job.id, "Too late", after_key="offer")
    with pytest.raises(ps.PipelineError):
        ps.add_custom_stage(db_session, job.id, "   ")


def test_added_stage_count_is_capped(db_session):
    job, _ = make_application(db_session)
    for n in range(ps.MAX_CUSTOM_STAGES):
        ps.add_custom_stage(db_session, job.id, f"Extra {n}")
    with pytest.raises(ps.PipelineError):
        ps.add_custom_stage(db_session, job.id, "One too many")


def test_adding_mid_flight_skips_it_for_candidates_already_past_it(db_session):
    job, ahead = make_application(db_session)
    _, behind = make_application(db_session, job=job, first_name="Tobi")  # still at Resume submitted
    for _ in range(3):
        ps.advance(db_session, ahead)  # now at technical_interview

    stage = ps.add_custom_stage(db_session, job.id, "Culture conversation", after_key="hm_review")

    db_session.expire_all()
    ahead_rows = _rows(ahead)
    behind_rows = _rows(behind)
    assert ahead_rows[stage.key].status == ps.SKIPPED
    assert ahead_rows[stage.key].note == ps.LATE_STAGE_NOTE
    assert behind_rows[stage.key].status == ps.PENDING

    ps.advance(db_session, behind)  # hm_review
    ps.advance(db_session, behind)  # the custom stage
    assert ps.current_stage(behind).stage.key == stage.key
    assert db_session.get(Candidate, behind.candidate_id).status == "interviewing"


# --- reordering ----------------------------------------------------------------


def test_reorder_moves_interview_stages(db_session):
    job, _ = make_application(db_session)
    order = ["case_study", "hm_review", "technical_written", "technical_interview", "problem_solving", "hr_screen"]
    ps.reorder_stages(db_session, job.id, order)
    keys = _keys(db_session, job.id)
    assert keys == ["resume_submitted", *order, "offer", "offer_accepted", "offer_declined", "hired"]


def test_reorder_refuses_pinned_or_partial_lists(db_session):
    job, _ = make_application(db_session)
    with pytest.raises(ps.PipelineError):
        ps.reorder_stages(db_session, job.id, ["hm_review", "technical_written"])
    with pytest.raises(ps.PipelineError):
        ps.reorder_stages(
            db_session,
            job.id,
            ["offer", "hm_review", "technical_written", "technical_interview", "problem_solving", "case_study", "hr_screen"],
        )


def test_reorder_closes_rounds_left_behind(db_session):
    job, application = make_application(db_session)
    for _ in range(3):
        ps.advance(db_session, application)  # technical_interview
    ps.reorder_stages(
        db_session,
        job.id,
        ["hm_review", "case_study", "technical_written", "technical_interview", "problem_solving", "hr_screen"],
    )
    rows = _rows(application)
    assert rows["case_study"].status == ps.SKIPPED
    assert rows["case_study"].note == ps.MOVED_STAGE_NOTE
    assert ps.current_stage(application).stage.key == "technical_interview"
    ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "problem_solving"


# --- removing ------------------------------------------------------------------


def test_remove_custom_stage_compacts_positions(db_session):
    job, application = make_application(db_session)
    stage = ps.add_custom_stage(db_session, job.id, "Take-home review")
    ps.remove_custom_stage(db_session, job.id, stage.key)
    stages = ps.ensure_job_stages(db_session, job.id)
    assert stage.key not in [s.key for s in stages]
    assert [s.position for s in stages] == list(range(1, 12))
    db_session.expire_all()
    assert len(application.stages) == 11


def test_remove_refuses_default_and_used_stages(db_session):
    job, application = make_application(db_session)
    with pytest.raises(ps.PipelineError, match="Turn it off"):
        ps.remove_custom_stage(db_session, job.id, "case_study")
    stage = ps.add_custom_stage(db_session, job.id, "Intro call", after_key="resume_submitted")
    ps.advance(db_session, application)  # now in progress at the custom stage
    with pytest.raises(ps.PipelineError, match="history"):
        ps.remove_custom_stage(db_session, job.id, stage.key)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_custom_stages.py -q -p no:cacheprovider`
Expected: the 10 new tests fail with `AttributeError: module 'backend.services.pipeline_service' has no attribute 'add_custom_stage'` (or `is_custom`, `reorder_stages`, `remove_custom_stage`).

- [ ] **Step 3: Implement**

At the top of `backend/services/pipeline_service.py`, add `import re` below `from __future__ import annotations`.

Below `DECLINABLE_KEYS = ...`, add:

```python
# Phase E: which stages may move. Resume submitted is where every
# application starts; Offer and Offer accepted carry the Decline rule; the
# outcomes are not rounds. Everything else is an "interview stage".
FIRST_ROUND = "resume_submitted"
OFFER_ROUNDS = ("offer", "offer_accepted")
CUSTOM_PREFIX = "custom_"
MAX_CUSTOM_STAGES = 10
LATE_STAGE_NOTE = "Added to the pipeline after this candidate had moved past this point."
MOVED_STAGE_NOTE = "Moved earlier in the pipeline after this candidate had passed this point."
```

Append to the end of the file (after `ACTIONS = ...`):

```python
# --- custom stages and reordering (ATS Phase E) --------------------------------


def is_custom(stage: PipelineStage) -> bool:
    return stage.key.startswith(CUSTOM_PREFIX)


def is_movable(stage: PipelineStage) -> bool:
    return stage.kind == ROUND and stage.key != FIRST_ROUND and stage.key not in OFFER_ROUNDS


def _custom_key(existing: set[str], name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "stage"
    key = f"{CUSTOM_PREFIX}{slug}"
    n = 2
    while key in existing:
        key = f"{CUSTOM_PREFIX}{slug}_{n}"
        n += 1
    return key


def _layout(stages: list[PipelineStage], middle_keys: list[str]) -> list[PipelineStage]:
    """First round, interview stages in the given order, offer rounds, outcomes."""
    by_key = {s.key: s for s in stages}
    if FIRST_ROUND not in by_key or any(k not in by_key for k in OFFER_ROUNDS):
        raise PipelineError("This job is missing a default stage, so its stages cannot be rearranged.")
    outcomes = [s for s in sorted(stages, key=lambda s: s.position) if s.kind == OUTCOME]
    return [by_key[FIRST_ROUND], *(by_key[k] for k in middle_keys), *(by_key[k] for k in OFFER_ROUNDS), *outcomes]


def _renumber(stages_in_order: list[PipelineStage]) -> None:
    for position, stage in enumerate(stages_in_order, start=1):
        stage.position = position


def _backfill_new_stage(db: Session, stage: PipelineStage) -> None:
    """One row per existing application for a stage added mid-flight."""
    now = datetime.utcnow()
    applications = db.query(JobApplication).filter(JobApplication.job_id == stage.job_id).all()
    for application in applications:
        if not application.stages:
            continue  # ensure_application_stages builds a full set on first read
        current = current_stage(application)
        behind = application.status in TERMINAL or (
            current is not None and current.stage.position > stage.position
        )
        row = ApplicationStage(
            application_id=application.id,
            stage_id=stage.id,
            status=SKIPPED if behind else PENDING,
        )
        if behind:
            row.completed_at = now
            row.note = LATE_STAGE_NOTE
        db.add(row)
    db.flush()
    for application in applications:
        db.expire(application, ["stages"])


def add_custom_stage(
    db: Session,
    job_id: int,
    name: str,
    description: Optional[str] = None,
    after_key: Optional[str] = None,
) -> PipelineStage:
    """A new interview stage, placed after `after_key` (default: just before the offer)."""
    stages = ensure_job_stages(db, job_id)
    name = (name or "").strip()
    if not name:
        raise PipelineError("A stage needs a name.")
    if sum(1 for s in stages if is_custom(s)) >= MAX_CUSTOM_STAGES:
        raise PipelineError(f"A job can have at most {MAX_CUSTOM_STAGES} added stages.")

    middle = [s.key for s in stages if is_movable(s)]
    if after_key is None:
        index = len(middle)
    elif after_key == FIRST_ROUND:
        index = 0
    elif after_key in middle:
        index = middle.index(after_key) + 1
    else:
        raise PipelineError(
            "New stages go after Resume submitted or after another interview stage, never after the offer."
        )

    stage = PipelineStage(
        job_id=job_id,
        key=_custom_key({s.key for s in stages}, name),
        name=name,
        description=(description or "").strip() or None,
        kind=ROUND,
        position=0,
        enabled=True,
    )
    db.add(stage)
    db.flush()
    middle.insert(index, stage.key)
    _renumber(_layout([*stages, stage], middle))
    db.flush()
    _backfill_new_stage(db, stage)
    return stage


def _close_rows_left_behind(db: Session, job_id: int) -> None:
    now = datetime.utcnow()
    applications = (
        db.query(JobApplication)
        .filter(JobApplication.job_id == job_id, JobApplication.status == APP_ACTIVE)
        .all()
    )
    for application in applications:
        current = current_stage(application)
        if current is None:
            continue
        for row in application.stages:
            if (
                row.status == PENDING
                and row.stage.kind == ROUND
                and row.stage.position < current.stage.position
            ):
                row.status = SKIPPED
                row.completed_at = now
                row.note = MOVED_STAGE_NOTE


def reorder_stages(db: Session, job_id: int, middle_order: list[str]) -> None:
    """Put the interview stages in `middle_order`. The pinned stages do not move."""
    stages = ensure_job_stages(db, job_id)
    middle = [s.key for s in stages if is_movable(s)]
    if len(middle_order) != len(set(middle_order)) or set(middle_order) != set(middle):
        raise PipelineError(
            "The new order must list every interview stage exactly once. "
            "Resume submitted stays first and the offer stages stay last."
        )
    _renumber(_layout(stages, middle_order))
    db.flush()
    _close_rows_left_behind(db, job_id)
    db.flush()


def remove_custom_stage(db: Session, job_id: int, key: str) -> None:
    """Delete a stage this job added, if no candidate has history at it."""
    stages = ensure_job_stages(db, job_id)
    stage = next((s for s in stages if s.key == key), None)
    if stage is None:
        raise PipelineError(f"No stage named '{key}' on this job.")
    if not is_custom(stage):
        raise PipelineError(f"'{stage.name}' is a default stage. Turn it off instead of removing it.")
    rows = db.query(ApplicationStage).filter(ApplicationStage.stage_id == stage.id).all()
    if any(r.status in (IN_PROGRESS, PASSED, FAILED) for r in rows):
        raise PipelineError(
            f"'{stage.name}' already has candidate history. Turn it off instead of removing it."
        )
    application_ids = {r.application_id for r in rows}
    for row in rows:
        db.delete(row)
    db.delete(stage)
    db.flush()
    _renumber([s for s in stages if s.id != stage.id])
    db.flush()
    if application_ids:
        for application in db.query(JobApplication).filter(JobApplication.id.in_(application_ids)).all():
            db.expire(application, ["stages"])
```

- [ ] **Step 4: Run the tests**

Run: `poetry run pytest backend/tests/test_custom_stages.py backend/tests/test_pipeline.py -q -p no:cacheprovider`
Expected: 12 passed in `test_custom_stages.py`, Phase A file still green.

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e2.txt`:

```
feat: custom interview stages, reordering, and removal in the pipeline service

Resume submitted stays first and the two offer rounds stay last, so the
Decline rule and every existing transition keep working; only the
interview stages in between can move, and new stages land there.
Candidates already past a stage that is added or moved behind them get
a skipped row with a note rather than an orphaned pending one. Removal
is limited to added stages with no history. Verified with 10 service
tests on top of the Phase A suite.
```

```powershell
git add backend/services/pipeline_service.py backend/tests/test_custom_stages.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e2.txt
```

---

### Task 3: Extend `PUT /api/jobs/{id}/pipeline`

**Files:**
- Modify: `backend/models/pipeline.py`
- Modify: `backend/routers/pipeline.py`
- Modify: `backend/utils/permissions.py`
- Test: `backend/tests/test_custom_stages.py`

- [ ] **Step 1: Write the failing route tests**

Append to `backend/tests/test_custom_stages.py`:

```python
# --- the PUT route -------------------------------------------------------------


def test_put_adds_a_custom_stage(admin_client, db_session):
    job, _ = make_application(db_session)
    response = admin_client.put(
        f"/api/jobs/{job.id}/pipeline",
        json={"add": [{"name": "Portfolio review", "description": "Walk us through your work."}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    added = next(s for s in body["stages"] if s["key"] == "custom_portfolio_review")
    assert added["custom"] is True and added["movable"] is True
    assert "custom_portfolio_review" in [c["stage_key"] for c in body["columns"]]
    first = next(s for s in body["stages"] if s["key"] == "resume_submitted")
    assert first["movable"] is False and first["custom"] is False


def test_put_reorders_columns(admin_client, db_session):
    job, _ = make_application(db_session)
    order = ["hr_screen", "hm_review", "technical_written", "technical_interview", "problem_solving", "case_study"]
    response = admin_client.put(f"/api/jobs/{job.id}/pipeline", json={"order": order})
    assert response.status_code == 200, response.text
    columns = [c["stage_key"] for c in response.json()["columns"]]
    assert columns == ["resume_submitted", *order, "offer", "offer_accepted"]


def test_put_rolls_back_the_whole_request_on_refusal(admin_client, db_session):
    job, _ = make_application(db_session)
    # A valid rename, then an invalid order: the rename must not survive.
    response = admin_client.put(
        f"/api/jobs/{job.id}/pipeline",
        json={
            "stages": [{"key": "case_study", "enabled": True, "name": "Renamed case study"}],
            "order": ["hm_review"],
        },
    )
    assert response.status_code == 409
    assert "exactly once" in response.json()["detail"]
    board = admin_client.get(f"/api/jobs/{job.id}/pipeline").json()
    case_study = next(s for s in board["stages"] if s["key"] == "case_study")
    assert case_study["name"] == "Case study"

    refused = admin_client.put(f"/api/jobs/{job.id}/pipeline", json={"remove": ["case_study"]})
    assert refused.status_code == 409 and "Turn it off" in refused.json()["detail"]


def test_put_pipeline_permissions(demo_client, db_session, override_get_db):
    job, _ = make_application(db_session)
    body = {"stages": [{"key": "case_study", "enabled": False, "name": "Case study"}]}
    assert demo_client.put(f"/api/jobs/{job.id}/pipeline", json=body).status_code == 403
    assert staff_client(db_session, "hiring_team").put(f"/api/jobs/{job.id}/pipeline", json=body).status_code == 403
    assert staff_client(db_session, "interviewer").put(f"/api/jobs/{job.id}/pipeline", json=body).status_code == 403
    assert staff_client(db_session, "hiring_manager").put(f"/api/jobs/{job.id}/pipeline", json=body).status_code == 200
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_custom_stages.py -q -p no:cacheprovider -k put_`
Expected: the first three fail (`custom` missing from the response, `order` and `add` ignored). The permissions test may already pass if Phase B mapped this route; that is fine.

- [ ] **Step 3: Extend the Pydantic models**

In `backend/models/pipeline.py`, add two fields to `StageOut` (after `enabled: bool`):

```python
    # Phase E: added for this job (removable) and allowed to move.
    custom: bool = False
    movable: bool = False
```

Replace `PipelineUpdateRequest` with:

```python
class NewStage(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    # Key of the round the new stage follows: resume_submitted or an interview
    # stage. None places it just before the offer.
    after_key: Optional[str] = None


class PipelineUpdateRequest(BaseModel):
    """Everything the stage editor can change, applied in one transaction.

    Order of application: remove, then stages (enable, disable, rename), then
    order (interview stage keys only), then add.
    """
    stages: List[StageUpdate] = Field(default_factory=list)
    order: Optional[List[str]] = None
    add: List[NewStage] = Field(default_factory=list)
    remove: List[str] = Field(default_factory=list)
```

- [ ] **Step 4: Rewrite the PUT handler and the stage serializer**

In `backend/routers/pipeline.py`, add above `_board`:

```python
def _stage_out(stage) -> StageOut:
    return StageOut(
        id=stage.id,
        key=stage.key,
        name=stage.name,
        kind=stage.kind,
        description=stage.description,
        position=stage.position,
        enabled=stage.enabled,
        custom=ps.is_custom(stage),
        movable=ps.is_movable(stage),
    )
```

In `_board`, replace `stages=[StageOut.model_validate(s) for s in stages],` with `stages=[_stage_out(s) for s in stages],`.

Replace the whole `update_job_pipeline` function with:

```python
@router.put("/jobs/{job_id}/pipeline", response_model=JobPipelineResponse)
def update_job_pipeline(
    job_id: int, payload: PipelineUpdateRequest, db: Session = Depends(get_db)
) -> JobPipelineResponse:
    """Edit a job's stages in one transaction.

    Applied in a fixed order so one request can do everything the stage
    editor offers: remove added stages, enable/disable/rename, reorder the
    interview stages, then add new ones (placed by `after_key`, so they never
    need to appear in `order`). Any refusal rolls the whole request back.
    """
    job = _job_or_404(db, job_id)
    try:
        for key in payload.remove:
            ps.remove_custom_stage(db, job.id, key)

        stages = {s.key: s for s in ps.ensure_job_stages(db, job.id)}
        for update in payload.stages:
            stage = stages.get(update.key)
            if stage is None:
                db.rollback()
                raise HTTPException(status_code=404, detail=f"No stage named '{update.key}' on this job.")
            if not update.enabled and (stage.kind == ps.OUTCOME or stage.key == ps.FIRST_ROUND):
                raise ps.PipelineError(f"'{stage.name}' cannot be turned off.")
            if not update.enabled and stage.enabled:
                in_use = (
                    db.query(ApplicationStage)
                    .join(JobApplication)
                    .filter(
                        ApplicationStage.stage_id == stage.id,
                        ApplicationStage.status == ps.IN_PROGRESS,
                        JobApplication.status == ps.APP_ACTIVE,
                    )
                    .count()
                )
                if in_use:
                    raise ps.PipelineError(
                        f"{in_use} candidate(s) are at '{stage.name}' right now. Move them first."
                    )
            stage.enabled = update.enabled
            stage.name = update.name.strip()
            if update.description is not None:
                stage.description = update.description.strip() or None

        if payload.order is not None:
            ps.reorder_stages(db, job.id, payload.order)
        for new in payload.add:
            ps.add_custom_stage(db, job.id, new.name, new.description, new.after_key)
    except ps.PipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return _board(db, job)
```

(The Phase A tests `test_put_pipeline_never_disables_the_first_round_or_an_outcome` and `test_put_pipeline_refuses_to_disable_a_stage_in_use` still pass: the messages are unchanged and the status is still 409.)

- [ ] **Step 5: Grant the route to job writers**

Check whether Phase B already mapped it:

```powershell
Select-String backend/utils/permissions.py -Pattern "pipeline"
```

If there is no `PUT` entry for `/api/jobs/\d+/pipeline`, add this to `ROUTE_PERMISSIONS`:

```python
    ("PUT", r"^/api/jobs/\d+/pipeline$", JOBS_WRITE),  # Phase E stage editor
```

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_custom_stages.py backend/tests/test_pipeline.py backend/tests/test_auth.py -q -p no:cacheprovider`
Expected: 16 passed in `test_custom_stages.py`; the other two files green.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e3.txt`:

```
feat: stage editor API (add, remove, reorder) on PUT /api/jobs/{id}/pipeline

One request carries everything the editor can change and is applied in
a fixed order inside one transaction, so a refusal anywhere leaves the
job exactly as it was. Stages report whether they were added for this
job and whether they can move, so the UI never has to hard-code the
pinned keys. Hiring managers and admins may edit; hiring team,
interviewers, and the demo get 403.
```

```powershell
git add backend/models/pipeline.py backend/routers/pipeline.py backend/utils/permissions.py backend/tests/test_custom_stages.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e3.txt
```

---

### Task 4: Migration and models for status links and email

**Files:**
- Create: `backend/alembic/versions/f7b1d4e5a6c7_public_status_and_email.py`
- Modify: `backend/models/models.py`

- [ ] **Step 1: Write the migration**

Set `down_revision` to the head printed in Task 1 Step 1. The file below assumes `e6a0c3d4f5b6` (Phase C); if Phase D added `a6b1c2d3e4f5`, use that instead and change the `Revises:` line to match.

Create `backend/alembic/versions/f7b1d4e5a6c7_public_status_and_email.py`:

```python
"""public status links and email templates/log

ATS Phase E (spec 2026-10-03 sections 3.1, 3.2, 8). Adds a revocable
public_token to job_applications for the candidate status page, the
email_templates table seeded with four editable defaults, and email_log,
which records every email sent or copied from the app.

The default template text lives here rather than in seed_demo.py because
it is product configuration, not demo data: production needs it without
a reseed. It is synthetic and contains no addresses.

Revision ID: f7b1d4e5a6c7
Revises: e6a0c3d4f5b6
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7b1d4e5a6c7"
down_revision: Union[str, None] = "e6a0c3d4f5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TEMPLATES = [
    (
        "interview_invite",
        "Interview invitation",
        "Next step for the {{job_title}} role",
        "Hi {{candidate_first_name}},\n\n"
        "Thank you for your interest in the {{job_title}} role on our {{department}} team. "
        "We would like to invite you to the next stage of our process.\n\n"
        "Please reply with a few times that work for you over the next week, and we will confirm one.\n\n"
        "You can follow your application at any time here: {{status_link}}\n\n"
        "Best regards,\n{{sender_name}}",
    ),
    (
        "resume_request",
        "Resume request",
        "Your application for {{job_title}}",
        "Hi {{candidate_first_name}},\n\n"
        "Thank you for applying for the {{job_title}} role. Could you reply with an up-to-date copy "
        "of your resume? We want to make sure we are reviewing your most recent experience.\n\n"
        "Best regards,\n{{sender_name}}",
    ),
    (
        "polite_close",
        "Polite close",
        "An update on your {{job_title}} application",
        "Hi {{candidate_first_name}},\n\n"
        "Thank you for the time you have spent with us on the {{job_title}} role. After careful "
        "consideration, we have decided not to move forward with your application.\n\n"
        "We appreciate your interest in joining the {{department}} team and wish you the best in "
        "your search.\n\n"
        "Kind regards,\n{{sender_name}}",
    ),
    (
        "offer",
        "Offer",
        "Offer for the {{job_title}} role",
        "Hi {{candidate_first_name}},\n\n"
        "We are delighted to let you know that we would like to offer you the {{job_title}} role "
        "on our {{department}} team. A formal offer letter with the details will follow shortly.\n\n"
        "If you have any questions in the meantime, just reply to this email.\n\n"
        "Congratulations,\n{{sender_name}}",
    ),
]


def upgrade() -> None:
    op.add_column("job_applications", sa.Column("public_token", sa.String(36), nullable=True))
    op.add_column("job_applications", sa.Column("public_token_created_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_job_applications_public_token", "job_applications", ["public_token"], unique=True
    )

    templates = op.create_table(
        "email_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.bulk_insert(
        templates,
        [
            {"key": key, "name": name, "subject": subject, "body": body}
            for key, name, subject, body in DEFAULT_TEMPLATES
        ],
    )

    op.create_table(
        "email_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("job_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_key", sa.String(50), nullable=True),
        sa.Column("to_address", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_log_application_id", "email_log", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_email_log_application_id", table_name="email_log")
    op.drop_table("email_log")
    op.drop_table("email_templates")
    op.drop_index("ix_job_applications_public_token", table_name="job_applications")
    op.drop_column("job_applications", "public_token_created_at")
    op.drop_column("job_applications", "public_token")
```

- [ ] **Step 2: Add the ORM models**

In `backend/models/models.py`, inside `class JobApplication`, after `notes = Column(Text, nullable=True)`:

```python
    # ATS Phase E: the candidate status link. Null means no link is active;
    # regenerating replaces it, which is how a leaked link is revoked.
    public_token = Column(String(36), nullable=True, unique=True, index=True)
    public_token_created_at = Column(DateTime, nullable=True)
```

Append to the end of the file:

```python
# ====================================================================
# Email (ATS Phase E, spec 2026-10-03 section 3.1)
# ====================================================================


class EmailTemplate(Base):
    """One editable starting point for candidate email. Seeded by migration f7b1d4e5a6c7."""
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)


class EmailLog(Base):
    """Every email sent, or copied to be sent by hand, from the app."""
    __tablename__ = "email_log"

    id = Column(Integer, primary_key=True)
    application_id = Column(
        Integer, ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_key = Column(String(50), nullable=True)
    to_address = Column(String(255), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)  # sent, failed, copied
    error = Column(Text, nullable=True)
    sent_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

- [ ] **Step 3: Verify on a scratch database**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; poetry run alembic downgrade -1; poetry run alembic upgrade head; cd ..
docker exec recruitiq-db psql -U admin -d st_scratch -c "\d email_log" -c "SELECT key, name FROM email_templates ORDER BY id" -c "\d job_applications"
```

Expected: upgrade, downgrade, upgrade all succeed; four template rows (`interview_invite`, `resume_request`, `polite_close`, `offer`); `job_applications` lists `public_token` with a unique index.

Then apply to the dev database:

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
cd backend; poetry run alembic upgrade head; cd ..
```

Leave `st_scratch` in place; Task 10 reuses it.

- [ ] **Step 4: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e4.txt`:

```
feat: migration for status links, email templates, and the email log

Adds a revocable public_token to applications, an email_templates table
seeded with four synthetic defaults (interview invitation, resume
request, polite close, offer), and email_log. Templates are seeded by
the migration because production needs them without a reseed.
Verified upgrade, downgrade, upgrade on a scratch database.
```

```powershell
git add backend/alembic/versions/f7b1d4e5a6c7_public_status_and_email.py backend/models/models.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e4.txt
```

---

### Task 5: Status link service and the allowlisted public view

The public payload is built field by field from an allowlist. Nothing is serialized from an ORM object, so a column added to `candidates` or `jobs` later cannot leak by accident.

**Files:**
- Create: `backend/models/public_status.py`
- Create: `backend/services/status_link_service.py`
- Test: `backend/tests/test_status_links.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_status_links.py`:

```python
"""Candidate status links (ATS Phase E).

The pinned property: the public payload carries the candidate's first name,
the job title and department, an application status label, and the stage
names with their candidate-facing descriptions. Nothing else. No score, no
email, no phone, no last name, no notes, no internal stage notes, and no
staff names. Same idea as test_traces_carry_no_contact_details.
"""
from __future__ import annotations

import json

from backend.models.models import Candidate
from backend.services import pipeline_service as ps
from backend.services import status_link_service as links
from backend.tests.phase_e_helpers import make_application, staff_client, staff_user

INTERNAL_NOTE = "Panel thought the SQL answer was weak"
ALLOWED_TOP = {"first_name", "job_title", "department", "status", "stages"}
ALLOWED_STAGE = {"name", "description", "state"}


def _banned_values(db_session, job, application, staff):
    candidate = db_session.get(Candidate, application.candidate_id)
    return [
        candidate.last_name,
        candidate.email,
        candidate.phone,
        "counter offer",  # candidate.notes
        INTERNAL_NOTE,
        job.hiring_manager,
        job.recruiter,
        staff.name,
        staff.email,
        "match_score",
        "score",
    ]


def _assert_allowlisted(payload: dict, banned: list[str]):
    assert set(payload) == ALLOWED_TOP
    for stage in payload["stages"]:
        assert set(stage) == ALLOWED_STAGE
    text = json.dumps(payload).lower()
    for value in banned:
        assert value and value.lower() not in text, f"public payload leaked {value!r}"


# --- service ---------------------------------------------------------------


def test_issue_link_is_unguessable_and_rotates(db_session):
    _, application = make_application(db_session)
    first = links.issue_link(db_session, application)
    second = links.issue_link(db_session, application)
    assert len(first) >= 32 and first != second
    assert links.find_by_token(db_session, first) is None
    assert links.find_by_token(db_session, second).id == application.id
    links.revoke_link(db_session, application)
    assert links.find_by_token(db_session, second) is None
    assert links.find_by_token(db_session, "") is None
    assert links.find_by_token(db_session, "x" * 500) is None


def test_public_view_shows_only_the_allowlist(db_session):
    job, application = make_application(db_session)
    staff = staff_user(db_session, "hiring_team", name="Ravi Panelist")
    ps.advance(db_session, application, actor_id=staff.id, note=INTERNAL_NOTE)

    view = links.public_view(db_session, application).model_dump()

    _assert_allowlisted(view, _banned_values(db_session, job, application, staff))
    assert view["first_name"] == "Mira"
    assert view["job_title"] == "Platform Engineer"
    assert view["department"] == "Engineering"
    assert view["status"] == "In progress"
    assert [s["state"] for s in view["stages"][:3]] == ["done", "current", "upcoming"]
    assert view["stages"][1]["description"].startswith("The hiring manager reviews")


def test_public_view_hides_skipped_rounds_and_unreached_outcomes(db_session):
    _, application = make_application(db_session)
    ps.skip(db_session, application)  # Resume submitted skipped
    names = [s.name for s in links.public_view(db_session, application).stages]
    assert "Resume submitted" not in names
    assert "Hired" not in names and "Offer declined" not in names


def test_rejected_application_reads_as_closed(db_session):
    _, application = make_application(db_session)
    ps.advance(db_session, application)
    ps.reject(db_session, application, note=INTERNAL_NOTE)
    view = links.public_view(db_session, application)
    assert view.status == "Closed"
    assert [s.state for s in view.stages] == ["done", "closed"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_status_links.py -q -p no:cacheprovider`
Expected: FAIL with `ImportError: cannot import name 'status_link_service'`.

- [ ] **Step 3: Write the response models**

Create `backend/models/public_status.py`:

```python
"""Shapes for the candidate-facing status page (ATS Phase E).

PublicStatus is an allowlist. Adding a field here publishes it to anyone
holding a status link, so test_status_links pins the exact key set.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PublicStage(BaseModel):
    name: str
    description: Optional[str] = None
    # done, current, upcoming, closed
    state: str


class PublicStatus(BaseModel):
    first_name: Optional[str] = None
    job_title: str
    department: Optional[str] = None
    # In progress, Hired, Closed
    status: str
    stages: List[PublicStage]


class StatusLinkOut(BaseModel):
    active: bool
    # Relative path, e.g. /c/<token>. The web app builds the absolute URL.
    path: Optional[str] = None
    created_at: Optional[datetime] = None
```

- [ ] **Step 4: Write the service**

Create `backend/services/status_link_service.py`:

```python
"""Candidate status links (ATS Phase E, spec 2026-10-03 section 8).

A link is a random token on the application. Holding it shows the
candidate's first name, the job, and the stage timeline, and nothing else.
Regenerating replaces the token (the old link stops working at once);
revoking clears it. Unknown, replaced, and revoked tokens are all the same
404 to the caller.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.models import Candidate, Job, JobApplication
from backend.models.public_status import PublicStage, PublicStatus
from backend.services import pipeline_service as ps

# 24 random bytes -> 32 URL-safe characters, which fits the 36-character
# column and is far beyond guessing range.
TOKEN_BYTES = 24
MAX_TOKEN_LENGTH = 64

PUBLIC_APPLICATION_STATUS = {
    ps.APP_ACTIVE: "In progress",
    ps.APP_HIRED: "Hired",
    ps.APP_REJECTED: "Closed",
    ps.APP_DECLINED: "Closed",
    ps.APP_WITHDRAWN: "Closed",
}

_PUBLIC_STAGE_STATE = {
    ps.PASSED: "done",
    ps.IN_PROGRESS: "current",
    ps.PENDING: "upcoming",
    ps.FAILED: "closed",
}


def issue_link(db: Session, application: JobApplication) -> str:
    """Create or replace the application's link and return the new token."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    application.public_token = token
    application.public_token_created_at = datetime.utcnow()
    db.flush()
    return token


def revoke_link(db: Session, application: JobApplication) -> None:
    application.public_token = None
    application.public_token_created_at = None
    db.flush()


def find_by_token(db: Session, token: str) -> Optional[JobApplication]:
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    return db.query(JobApplication).filter(JobApplication.public_token == token).first()


def public_view(db: Session, application: JobApplication) -> PublicStatus:
    """The candidate-facing view, built only from allowlisted fields."""
    rows = ps.ensure_application_stages(db, application)
    job = db.get(Job, application.job_id)
    candidate = db.get(Candidate, application.candidate_id)

    stages = []
    for row in rows:
        stage = row.stage
        if row.status == ps.SKIPPED:
            continue
        if stage.kind == ps.OUTCOME and row.status != ps.PASSED:
            continue
        if row.status == ps.PENDING and not stage.enabled:
            continue
        stages.append(
            PublicStage(
                name=stage.name,
                description=stage.description,
                state=_PUBLIC_STAGE_STATE[row.status],
            )
        )

    first_name = (candidate.first_name or "").strip() if candidate else ""
    return PublicStatus(
        first_name=first_name or None,
        job_title=(job.title if job else "") or "",
        department=job.department if job else None,
        status=PUBLIC_APPLICATION_STATUS.get(application.status, "In progress"),
        stages=stages,
    )
```

- [ ] **Step 5: Run the tests**

Run: `poetry run pytest backend/tests/test_status_links.py -q -p no:cacheprovider`
Expected: 4 passed.

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e5.txt`:

```
feat: status link service with an allowlisted candidate view

The public view is assembled field by field (first name, job title,
department, a status label, stage names and their candidate-facing
descriptions) so nothing reaches a candidate by serializing a model.
A pinned test proves no score, email, phone, last name, notes, internal
stage notes, or staff names appear. Tokens are 32 random URL-safe
characters; regenerating replaces them.
```

```powershell
git add backend/models/public_status.py backend/services/status_link_service.py backend/tests/test_status_links.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e5.txt
```

---

### Task 6: Status link routes, mounted above the pipeline router

`POST /api/applications/{application_id}/{action}` (Phase A) would match `POST /api/applications/5/status-link` and answer "Unknown action" if it were registered first. Starlette matches routes in registration order, so the new routers are mounted **above** the pipeline router, and a test pins it.

**Files:**
- Create: `backend/routers/application_access.py`
- Create: `backend/routers/status_links.py`
- Modify: `backend/main.py`
- Modify: `backend/utils/permissions.py`
- Test: `backend/tests/test_status_links.py`

- [ ] **Step 1: Write the failing route tests**

Append to `backend/tests/test_status_links.py`:

```python
# --- routes ----------------------------------------------------------------


def test_public_status_unknown_token_is_404(client):
    response = client.get("/api/public/status/not-a-real-token-000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "This status link is not active."


def test_status_link_lifecycle(admin_client, client, db_session):
    _, application = make_application(db_session)
    base = f"/api/applications/{application.id}/status-link"

    assert admin_client.get(base).json() == {"active": False, "path": None, "created_at": None}

    created = admin_client.post(base)
    # 200 with a path, not the transition router's "Unknown action" 404.
    assert created.status_code == 200, created.text
    first_path = created.json()["path"]
    assert first_path.startswith("/c/")
    token = first_path.removeprefix("/c/")
    assert client.get(f"/api/public/status/{token}").status_code == 200

    replaced = admin_client.post(base).json()["path"]
    assert replaced != first_path
    assert client.get(f"/api/public/status/{token}").status_code == 404

    revoked = admin_client.delete(base)
    assert revoked.status_code == 200 and revoked.json()["active"] is False
    assert client.get(f"/api/public/status/{replaced.removeprefix('/c/')}").status_code == 404


def test_status_link_permissions(demo_client, db_session, override_get_db):
    _, application = make_application(db_session)
    base = f"/api/applications/{application.id}/status-link"
    assert demo_client.post(base).status_code == 403
    assert demo_client.get(base).status_code == 403
    assert demo_client.delete(base).status_code == 403
    assert staff_client(db_session, "interviewer").post(base).status_code == 403
    assert staff_client(db_session, "hiring_team").post(base).status_code == 200


def test_candidate_view_matches_the_public_payload(admin_client, demo_client, client, db_session):
    _, application = make_application(db_session)
    preview = demo_client.get(f"/api/applications/{application.id}/candidate-view")
    assert preview.status_code == 200, preview.text
    path = admin_client.post(f"/api/applications/{application.id}/status-link").json()["path"]
    public = client.get(f"/api/public/status/{path.removeprefix('/c/')}")
    assert public.json() == preview.json()


def test_public_payload_over_http_carries_no_internal_details(admin_client, client, db_session):
    job, application = make_application(db_session)
    staff = staff_user(db_session, "hiring_team", name="Ravi Panelist")
    ps.advance(db_session, application, actor_id=staff.id, note=INTERNAL_NOTE)
    db_session.commit()
    path = admin_client.post(f"/api/applications/{application.id}/status-link").json()["path"]

    payload = client.get(f"/api/public/status/{path.removeprefix('/c/')}").json()

    _assert_allowlisted(payload, _banned_values(db_session, job, application, staff))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_status_links.py -q -p no:cacheprovider`
Expected: the 5 new tests fail with 404 or 405 (no routes yet).

- [ ] **Step 3: Write the shared access helper**

Create `backend/routers/application_access.py`:

```python
"""Load an application the caller is allowed to see, or 404 (ATS Phase E).

Interviewers only see candidates they are assigned to (Phase B,
access_service). A route that serves one application must hide the rest
behind the same 404 an unknown id gets, so the existence of an application
is not itself a leak.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.models.models import ApplicationStage, JobApplication, User
from backend.services import access_service


def visible_application_or_404(
    db: Session, application_id: int, user: Optional[User]
) -> JobApplication:
    application = (
        db.query(JobApplication)
        .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
        .filter(JobApplication.id == application_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if user is not None:
        visible = access_service.visible_candidate_ids(db, user)
        if visible is not None and application.candidate_id not in visible:
            raise HTTPException(status_code=404, detail="Application not found")
    return application
```

- [ ] **Step 4: Write the router**

Create `backend/routers/status_links.py`:

```python
"""Candidate status links (ATS Phase E).

`GET /api/public/status/{token}` is the only unauthenticated route that
returns data about one person, so it returns the allowlisted PublicStatus
and nothing else. Unknown, replaced, and revoked tokens get the same 404
body. Plain `def` handlers (sync ORM; CLAUDE.md sharp edge).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.models import JobApplication, User
from ..models.public_status import PublicStatus, StatusLinkOut
from ..services import status_link_service as links
from ..utils.auth import get_optional_user
from ..utils.database import get_db
from ..utils.permissions import PIPELINE_MOVE, require
from .application_access import visible_application_or_404

router = APIRouter()

INACTIVE = "This status link is not active."


def _link_out(application: JobApplication) -> StatusLinkOut:
    if not application.public_token:
        return StatusLinkOut(active=False)
    return StatusLinkOut(
        active=True,
        path=f"/c/{application.public_token}",
        created_at=application.public_token_created_at,
    )


@router.get("/public/status/{token}", response_model=PublicStatus)
def get_public_status(token: str, db: Session = Depends(get_db)) -> PublicStatus:
    """What a candidate sees at their status link. No authentication."""
    application = links.find_by_token(db, token)
    if application is None:
        raise HTTPException(status_code=404, detail=INACTIVE)
    view = links.public_view(db, application)
    db.commit()  # public_view may lazily create stage rows
    return view


@router.get("/applications/{application_id}/candidate-view", response_model=PublicStatus)
def get_candidate_view(
    application_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> PublicStatus:
    """The same page a status link shows, for staff and the demo to preview."""
    application = visible_application_or_404(db, application_id, user)
    view = links.public_view(db, application)
    db.commit()
    return view


@router.get("/applications/{application_id}/status-link", response_model=StatusLinkOut)
def get_status_link(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require(PIPELINE_MOVE)),
) -> StatusLinkOut:
    return _link_out(visible_application_or_404(db, application_id, user))


@router.post("/applications/{application_id}/status-link", response_model=StatusLinkOut)
def create_status_link(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require(PIPELINE_MOVE)),
) -> StatusLinkOut:
    """Create the link, or replace it (the old one stops working immediately)."""
    application = visible_application_or_404(db, application_id, user)
    links.issue_link(db, application)
    db.commit()
    return _link_out(application)


@router.delete("/applications/{application_id}/status-link", response_model=StatusLinkOut)
def revoke_status_link(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require(PIPELINE_MOVE)),
) -> StatusLinkOut:
    application = visible_application_or_404(db, application_id, user)
    links.revoke_link(db, application)
    db.commit()
    return _link_out(application)
```

- [ ] **Step 5: Mount it above the pipeline router**

In `backend/main.py`, add `status_links` to the routers import line that already imports `pipeline` (the line will also gain `emails` and `job_drafts` in Tasks 8 and 9). Then insert directly **above** `app.include_router(pipeline.router, ...)`:

```python
# ATS Phase E. Mounted above the pipeline router on purpose: its
# POST /api/applications/{id}/{action} matches any third path segment and
# would answer "Unknown action" for /status-link and /emails.
app.include_router(status_links.router, prefix="/api", tags=["status-links"])
```

- [ ] **Step 6: Grant the write routes**

Add to `ROUTE_PERMISSIONS` in `backend/utils/permissions.py`:

```python
    ("POST", r"^/api/applications/\d+/status-link$", PIPELINE_MOVE),  # Phase E
    ("DELETE", r"^/api/applications/\d+/status-link$", PIPELINE_MOVE),  # Phase E
```

- [ ] **Step 7: Run the tests**

Run: `poetry run pytest backend/tests/test_status_links.py backend/tests/test_pipeline.py backend/tests/test_auth.py -q -p no:cacheprovider`
Expected: 9 passed in `test_status_links.py`; the other files green. The auth route walk now includes `POST` and `DELETE /api/applications/{application_id}/status-link` and both refuse the demo and anonymous callers.

- [ ] **Step 8: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e6.txt`:

```
feat: status link routes and the public status endpoint

Staff create, replace, and turn off a candidate's link; anyone with the
link gets the allowlisted view at GET /api/public/status/{token}; staff
and the demo can preview the same view per application. The router is
mounted above the pipeline router because the transition route would
otherwise swallow /status-link. Interviewers get the same 404 for
applications they are not assigned to. Verified with 5 route tests,
including the no-leak check over HTTP.
```

```powershell
git add backend/routers/application_access.py backend/routers/status_links.py backend/main.py backend/utils/permissions.py backend/tests/test_status_links.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e6.txt
```

---

### Task 7: SMTP settings and the email service

**Files:**
- Modify: `backend/utils/config.py`
- Create: `backend/services/email_service.py`
- Test: `backend/tests/test_email.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_email.py`:

```python
"""Email templates, rendering, sending, and the log (ATS Phase E)."""
from __future__ import annotations

import pytest

from backend.services import email_service
from backend.utils.config import get_settings


class FakeSMTP:
    """Stands in for smtplib.SMTP; records what would have been sent."""

    sent: list = []
    fail_with: Exception | None = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.tls = False
        self.user = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        self.user = user

    def send_message(self, message):
        if FakeSMTP.fail_with:
            raise FakeSMTP.fail_with
        FakeSMTP.sent.append((self, message))


@pytest.fixture
def smtp(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_from", "Hiring <hiring@example.test>")
    monkeypatch.setattr(settings, "smtp_username", "mailer")
    monkeypatch.setattr(settings, "smtp_password", "hunter2-not-real")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    FakeSMTP.fail_with = None
    return settings


@pytest.fixture
def no_smtp(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from", "")
    return settings


# --- service ---------------------------------------------------------------


def test_render_fills_known_placeholders():
    text, missing = email_service.render(
        "Hi {{candidate_first_name}}, about {{ job_title }}.",
        {"candidate_first_name": "Mira", "job_title": "Platform Engineer"},
    )
    assert text == "Hi Mira, about Platform Engineer."
    assert missing == []


def test_render_reports_missing_and_unknown_placeholders():
    text, missing = email_service.render(
        "Link: {{status_link}} {{status_link}} {{favourite_color}}",
        {"status_link": None},
    )
    assert text == "Link: {{status_link}} {{status_link}} {{favourite_color}}"
    assert missing == ["status_link", "favourite_color"]


def test_unknown_placeholders():
    assert email_service.unknown_placeholders("{{job_title}} {{salary}} {{salary}}") == ["salary"]


def test_send_uses_starttls_and_login_when_configured(smtp):
    email_service.send(smtp, "mira@example.test", "Hello", "Body text")
    connection, message = FakeSMTP.sent[0]
    assert connection.host == "smtp.example.test" and connection.tls and connection.user == "mailer"
    assert message["To"] == "mira@example.test"
    assert message["From"] == "Hiring <hiring@example.test>"
    assert message.get_content().strip() == "Body text"


def test_send_without_transport_raises(no_smtp):
    assert email_service.transport_configured(no_smtp) is False
    with pytest.raises(email_service.EmailTransportError, match="No email transport"):
        email_service.send(no_smtp, "mira@example.test", "Hello", "Body")


def test_send_strips_header_injection_and_hides_the_password(smtp):
    email_service.send(smtp, "mira@example.test", "Hello\r\nBcc: someone@example.test", "Body")
    _, message = FakeSMTP.sent[0]
    assert "\n" not in message["Subject"] and message["Bcc"] is None

    import smtplib

    FakeSMTP.fail_with = smtplib.SMTPAuthenticationError(535, b"bad credentials hunter2-not-real")
    with pytest.raises(email_service.EmailTransportError) as excinfo:
        email_service.send(smtp, "mira@example.test", "Hello", "Body")
    assert "hunter2" not in str(excinfo.value)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_email.py -q -p no:cacheprovider`
Expected: FAIL with `ImportError: cannot import name 'email_service'`.

- [ ] **Step 3: Add the settings**

In `backend/utils/config.py`, inside `class Settings`, after the `demo_user_email` line:

```python
    # Outbound email (ATS Phase E). No host or no from address means "no
    # transport": the composer offers the finished text to copy instead of
    # sending. Real values live in /etc/recruitiq/env on the droplet, never
    # in git.
    smtp_host: str = Field(default=os.getenv("SMTP_HOST", ""))
    smtp_port: int = Field(default=int(os.getenv("SMTP_PORT", "587")))
    smtp_username: str = Field(default=os.getenv("SMTP_USERNAME", ""))
    smtp_password: str = Field(default=os.getenv("SMTP_PASSWORD", ""))
    smtp_from: str = Field(default=os.getenv("SMTP_FROM", ""))
    smtp_starttls: bool = Field(default=os.getenv("SMTP_STARTTLS", "true").lower() == "true")
    # Where candidate-facing links point. Status links in email are built
    # from this, never from a request's Host header.
    public_app_url: str = Field(default=os.getenv("PUBLIC_APP_URL", "http://localhost:3000"))
```

- [ ] **Step 4: Write the service**

Create `backend/services/email_service.py`:

```python
"""Email templates and the SMTP transport (ATS Phase E).

Templates hold `{{placeholder}}` markers from a fixed list. Rendering fills
the ones it has values for and reports the rest as missing, and the send
route refuses to send while anything is missing, so a candidate never gets
an email with a literal "{{status_link}}" in it.

The transport is plain SMTP with STARTTLS, configured from the environment.
When it is not configured, nothing is sent and the UI offers the text to
copy instead; that is a supported state, not an error.
"""
from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.models import Candidate, Job, JobApplication, User

PLACEHOLDERS = ("candidate_first_name", "job_title", "department", "sender_name", "status_link")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_]+)\s*\}\}")
DEFAULT_SENDER_NAME = "The hiring team"


class EmailTransportError(Exception):
    """Sending failed or is not configured. The message is safe to show a user."""


def render(text: str, values: dict[str, Optional[str]]) -> tuple[str, list[str]]:
    """Fill known placeholders that have a value. Return the text and what is still missing."""
    missing: list[str] = []

    def substitute(match: re.Match) -> str:
        name = match.group(1)
        value = values.get(name) if name in PLACEHOLDERS else None
        if value:
            return value
        if name not in missing:
            missing.append(name)
        return match.group(0)

    return _PLACEHOLDER_RE.sub(substitute, text or ""), missing


def unknown_placeholders(text: str) -> list[str]:
    found: list[str] = []
    for name in _PLACEHOLDER_RE.findall(text or ""):
        if name not in PLACEHOLDERS and name not in found:
            found.append(name)
    return found


def placeholder_values(
    db: Session, application: JobApplication, sender: Optional[User], settings
) -> dict[str, Optional[str]]:
    candidate = db.get(Candidate, application.candidate_id)
    job = db.get(Job, application.job_id)
    link = None
    if application.public_token:
        link = f"{settings.public_app_url.rstrip('/')}/c/{application.public_token}"
    sender_name = (getattr(sender, "name", None) or "").strip() or DEFAULT_SENDER_NAME
    return {
        "candidate_first_name": (candidate.first_name or "").strip() or None if candidate else None,
        "job_title": job.title if job else None,
        "department": job.department if job else None,
        "sender_name": sender_name,
        "status_link": link,
    }


def transport_configured(settings) -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send(settings, to_address: str, subject: str, body: str) -> None:
    if not transport_configured(settings):
        raise EmailTransportError("No email transport is configured.")
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_address
    # A newline in a header is how one email becomes two recipients.
    message["Subject"] = " ".join(subject.splitlines()).strip()
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # The class name only: server replies can echo credentials back.
        raise EmailTransportError(
            f"The mail server did not accept the message ({exc.__class__.__name__})."
        ) from exc
```

- [ ] **Step 5: Run the tests**

Run: `poetry run pytest backend/tests/test_email.py -q -p no:cacheprovider`
Expected: 6 passed.

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e7.txt`:

```
feat: email rendering and an SMTP transport configured from the environment

Placeholders come from a fixed list; anything unfilled or unknown is
reported as missing so the send route can refuse it. Without SMTP
settings the app reports "no transport" and the UI will offer the text
to copy. Header newlines are collapsed and transport errors never echo
the server reply. Verified with 6 tests against a fake SMTP class.
```

```powershell
git add backend/utils/config.py backend/services/email_service.py backend/tests/test_email.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e7.txt
```

---

### Task 8: Email routes

**Files:**
- Create: `backend/models/email.py`
- Create: `backend/routers/emails.py`
- Modify: `backend/main.py`, `backend/utils/permissions.py`
- Test: `backend/tests/test_email.py`

- [ ] **Step 1: Write the failing route tests**

Append to `backend/tests/test_email.py`:

```python
# --- routes ----------------------------------------------------------------

from backend.models.models import EmailLog, EmailTemplate  # noqa: E402
from backend.tests.phase_e_helpers import make_application, staff_client  # noqa: E402

PREVIEW = "/api/applications/{id}/emails/preview?template_key=interview_invite"


def _send_body(mode="send", **overrides):
    body = {
        "template_key": "interview_invite",
        "subject": "Next step for the {{job_title}} role",
        "body": "Hi {{candidate_first_name}}, more soon. {{sender_name}}",
        "mode": mode,
    }
    body.update(overrides)
    return body


def test_templates_list_has_the_four_defaults(client, no_smtp):
    response = client.get("/api/email-templates")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [t["key"] for t in body["templates"]] == [
        "interview_invite",
        "resume_request",
        "polite_close",
        "offer",
    ]
    assert body["transport_configured"] is False
    assert "status_link" in body["placeholders"]


def test_preview_as_demo_fills_first_name_and_flags_the_missing_link(demo_client, db_session):
    _, application = make_application(db_session)
    response = demo_client.get(PREVIEW.format(id=application.id))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"].startswith("Hi Mira,")
    assert body["missing"] == ["status_link"]
    assert body["to_address"].startswith("mira-")


def test_preview_includes_the_status_link_once_issued(admin_client, db_session):
    _, application = make_application(db_session)
    path = admin_client.post(f"/api/applications/{application.id}/status-link").json()["path"]
    body = admin_client.get(PREVIEW.format(id=application.id)).json()
    assert body["missing"] == []
    assert f"{get_settings().public_app_url.rstrip('/')}{path}" in body["body"]


def test_send_permissions(demo_client, db_session, override_get_db):
    _, application = make_application(db_session)
    url = f"/api/applications/{application.id}/emails"
    assert demo_client.post(url, json=_send_body("copied")).status_code == 403
    interviewer = staff_client(db_session, "interviewer")
    assert interviewer.post(url, json=_send_body("copied")).status_code == 403
    # Phase B's interviewer gate refuses paths outside INTERVIEWER_PATHS with 403
    # before the handler runs; email previews are not on that list.
    assert interviewer.get(PREVIEW.format(id=application.id)).status_code == 403


def test_copy_mode_logs_without_sending(db_session, override_get_db, smtp):
    _, application = make_application(db_session)
    team = staff_client(db_session, "hiring_team")
    response = team.post(f"/api/applications/{application.id}/emails", json=_send_body("copied"))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "copied"
    assert response.json()["sent_by_name"] == "Test Hiring Team"
    assert FakeSMTP.sent == []


def test_send_without_transport_is_409(admin_client, db_session, no_smtp):
    _, application = make_application(db_session)
    response = admin_client.post(f"/api/applications/{application.id}/emails", json=_send_body())
    assert response.status_code == 409
    assert "Copy the text" in response.json()["detail"]


def test_send_with_transport_logs_sent(admin_client, db_session, smtp):
    _, application = make_application(db_session)
    response = admin_client.post(f"/api/applications/{application.id}/emails", json=_send_body())
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "sent"
    _, message = FakeSMTP.sent[0]
    assert message["Subject"] == "Next step for the Platform Engineer role"
    log = admin_client.get(f"/api/applications/{application.id}/emails").json()
    assert [entry["status"] for entry in log] == ["sent"]


def test_send_failure_logs_failed_and_returns_502(admin_client, db_session, smtp):
    import smtplib

    _, application = make_application(db_session)
    FakeSMTP.fail_with = smtplib.SMTPServerDisconnected("gone")
    response = admin_client.post(f"/api/applications/{application.id}/emails", json=_send_body())
    assert response.status_code == 502
    entry = db_session.query(EmailLog).filter(EmailLog.application_id == application.id).one()
    assert entry.status == "failed" and "SMTPServerDisconnected" in entry.error


def test_send_refuses_unfilled_placeholders(admin_client, db_session, smtp):
    _, application = make_application(db_session)
    response = admin_client.post(
        f"/api/applications/{application.id}/emails",
        json=_send_body(body="Track it here: {{status_link}}"),
    )
    assert response.status_code == 409
    assert "{{status_link}}" in response.json()["detail"]
    assert FakeSMTP.sent == []


def test_update_template_permissions_and_validation(db_session, override_get_db):
    template = db_session.query(EmailTemplate).filter(EmailTemplate.key == "offer").one()
    original = (template.name, template.subject, template.body)
    url = "/api/email-templates/offer"
    edit = {"name": "Offer", "subject": "Offer: {{job_title}}", "body": "Hi {{candidate_first_name}}"}
    try:
        assert staff_client(db_session, "hiring_team").put(url, json=edit).status_code == 403
        manager = staff_client(db_session, "hiring_manager")
        bad = manager.put(url, json={**edit, "body": "Hi {{nickname}}"})
        assert bad.status_code == 400 and "{{nickname}}" in bad.json()["detail"]
        good = manager.put(url, json=edit)
        assert good.status_code == 200, good.text
        assert good.json()["subject"] == "Offer: {{job_title}}"
    finally:
        template.name, template.subject, template.body = original
        db_session.commit()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_email.py -q -p no:cacheprovider`
Expected: the 10 route tests fail with 404 (no routes).

- [ ] **Step 3: Write the Pydantic models**

Create `backend/models/email.py`:

```python
"""Request and response shapes for the email router (ATS Phase E)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EmailTemplateOut(BaseModel):
    key: str
    name: str
    subject: str
    body: str
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EmailTemplatesResponse(BaseModel):
    templates: List[EmailTemplateOut]
    transport_configured: bool
    placeholders: List[str]


class EmailTemplateUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)


class EmailPreview(BaseModel):
    template_key: str
    subject: str
    body: str
    to_address: Optional[str] = None
    missing: List[str]
    transport_configured: bool


class EmailSendRequest(BaseModel):
    template_key: Optional[str] = Field(default=None, max_length=50)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    # "copied": the user copied the text to send from their own inbox; logged, not sent.
    mode: Literal["send", "copied"]


class EmailLogOut(BaseModel):
    id: int
    template_key: Optional[str] = None
    to_address: str
    subject: str
    body: str
    status: str
    error: Optional[str] = None
    sent_by_name: Optional[str] = None
    created_at: datetime
```

- [ ] **Step 4: Write the router**

Create `backend/routers/emails.py`:

```python
"""Email templates, preview, send, and the log (ATS Phase E).

Preview and the log are reads, open to anyone who can see the candidate
(including the demo, so the portfolio shows the feature). Sending and
logging a copy need PIPELINE_MOVE; editing templates needs
TEMPLATES_MANAGE. Plain `def` handlers.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models.email import (
    EmailLogOut,
    EmailPreview,
    EmailSendRequest,
    EmailTemplateOut,
    EmailTemplatesResponse,
    EmailTemplateUpdate,
)
from ..models.models import Candidate, EmailLog, EmailTemplate, User
from ..services import email_service
from ..utils.auth import get_optional_user
from ..utils.config import get_settings
from ..utils.database import get_db
from ..utils.permissions import PIPELINE_MOVE, TEMPLATES_MANAGE, require
from .application_access import visible_application_or_404

router = APIRouter()


def _braced(names: List[str]) -> str:
    return ", ".join("{{" + name + "}}" for name in names)


def _log_out(db: Session, entry: EmailLog) -> EmailLogOut:
    sender = db.get(User, entry.sent_by) if entry.sent_by else None
    return EmailLogOut(
        id=entry.id,
        template_key=entry.template_key,
        to_address=entry.to_address,
        subject=entry.subject,
        body=entry.body,
        status=entry.status,
        error=entry.error,
        sent_by_name=(getattr(sender, "name", None) or None) if sender else None,
        created_at=entry.created_at,
    )


@router.get("/email-templates", response_model=EmailTemplatesResponse)
def list_templates(db: Session = Depends(get_db)) -> EmailTemplatesResponse:
    templates = db.query(EmailTemplate).order_by(EmailTemplate.id).all()
    return EmailTemplatesResponse(
        templates=[EmailTemplateOut.model_validate(t) for t in templates],
        transport_configured=email_service.transport_configured(get_settings()),
        placeholders=list(email_service.PLACEHOLDERS),
    )


@router.put("/email-templates/{key}", response_model=EmailTemplateOut)
def update_template(
    key: str,
    payload: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require(TEMPLATES_MANAGE)),
) -> EmailTemplateOut:
    template = db.query(EmailTemplate).filter(EmailTemplate.key == key).first()
    if template is None:
        raise HTTPException(status_code=404, detail=f"No email template named '{key}'.")
    unknown = email_service.unknown_placeholders(payload.subject + "\n" + payload.body)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown placeholder {_braced(unknown[:1])}. Use one of: "
            f"{_braced(list(email_service.PLACEHOLDERS))}.",
        )
    template.name = payload.name.strip()
    template.subject = payload.subject.strip()
    template.body = payload.body.strip()
    template.updated_at = datetime.utcnow()
    template.updated_by = user.id
    db.commit()
    db.refresh(template)
    return EmailTemplateOut.model_validate(template)


@router.get("/applications/{application_id}/emails/preview", response_model=EmailPreview)
def preview_email(
    application_id: int,
    template_key: str = Query(..., pattern=r"^[a-z_]{1,50}$"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> EmailPreview:
    application = visible_application_or_404(db, application_id, user)
    template = db.query(EmailTemplate).filter(EmailTemplate.key == template_key).first()
    if template is None:
        raise HTTPException(status_code=404, detail=f"No email template named '{template_key}'.")
    settings = get_settings()
    values = email_service.placeholder_values(db, application, user, settings)
    subject, missing_subject = email_service.render(template.subject, values)
    body, missing_body = email_service.render(template.body, values)
    candidate = db.get(Candidate, application.candidate_id)
    return EmailPreview(
        template_key=template.key,
        subject=subject,
        body=body,
        to_address=candidate.email if candidate else None,
        missing=list(dict.fromkeys(missing_subject + missing_body)),
        transport_configured=email_service.transport_configured(settings),
    )


@router.get("/applications/{application_id}/emails", response_model=List[EmailLogOut])
def list_emails(
    application_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> List[EmailLogOut]:
    application = visible_application_or_404(db, application_id, user)
    entries = (
        db.query(EmailLog)
        .filter(EmailLog.application_id == application.id)
        .order_by(EmailLog.created_at.desc(), EmailLog.id.desc())
        .all()
    )
    return [_log_out(db, entry) for entry in entries]


@router.post("/applications/{application_id}/emails", response_model=EmailLogOut)
def send_email(
    application_id: int,
    payload: EmailSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require(PIPELINE_MOVE)),
) -> EmailLogOut:
    """Send through SMTP, or log that the text was copied to send by hand."""
    application = visible_application_or_404(db, application_id, user)
    candidate = db.get(Candidate, application.candidate_id)
    if candidate is None or not candidate.email:
        raise HTTPException(status_code=409, detail="This candidate has no email address on file.")

    settings = get_settings()
    values = email_service.placeholder_values(db, application, user, settings)
    subject, missing_subject = email_service.render(payload.subject, values)
    body, missing_body = email_service.render(payload.body, values)
    missing = list(dict.fromkeys(missing_subject + missing_body))
    if missing:
        hint = (
            " Create a status link first, or remove {{status_link}} from the text."
            if "status_link" in missing
            else ""
        )
        raise HTTPException(status_code=409, detail=f"Fill in {_braced(missing)} before sending.{hint}")

    entry = EmailLog(
        application_id=application.id,
        template_key=payload.template_key,
        to_address=candidate.email,
        subject=subject,
        body=body,
        status="copied",
        sent_by=user.id,
        created_at=datetime.utcnow(),
    )
    if payload.mode == "send":
        if not email_service.transport_configured(settings):
            raise HTTPException(
                status_code=409,
                detail="No mail server is configured. Copy the text and send it from your own inbox.",
            )
        try:
            email_service.send(settings, candidate.email, subject, body)
            entry.status = "sent"
        except email_service.EmailTransportError as exc:
            entry.status = "failed"
            entry.error = str(exc)
            db.add(entry)
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _log_out(db, entry)
```

- [ ] **Step 5: Mount it and grant the write routes**

In `backend/main.py`, add `emails` to the routers import line, and below the `status_links` include (still above the pipeline router):

```python
app.include_router(emails.router, prefix="/api", tags=["email"])
```

Add to `ROUTE_PERMISSIONS`:

```python
    ("POST", r"^/api/applications/\d+/emails$", PIPELINE_MOVE),  # Phase E
    ("PUT", r"^/api/email-templates/[a-z_]+$", TEMPLATES_MANAGE),  # Phase E
```

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_email.py backend/tests/test_auth.py -q -p no:cacheprovider`
Expected: 16 passed in `test_email.py`; auth suite green.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e8.txt`:

```
feat: email templates, preview, send, and log endpoints

Preview and history are readable by anyone who can see the candidate,
so the demo can show the feature without sending anything. Sending and
"copied" logging need pipeline rights; template edits need template
rights and reject unknown placeholders. Sends with unfilled placeholders
are refused, no transport is a 409 that tells the user to copy the text,
and a mail server failure is logged as failed and returned as 502.
Verified with 10 route tests against a fake SMTP class.
```

```powershell
git add backend/models/email.py backend/routers/emails.py backend/main.py backend/utils/permissions.py backend/tests/test_email.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e8.txt
```

---

### Task 9: AI job description draft

The draft prompt is built only from the job fields the user typed (title, department, experience level, work arrangement, skills). It never reads a candidate. Every field still goes through `resume_privacy.scrub_text`, so an email address or phone number pasted into a title by mistake does not leave the server. The call goes through `LLMService.generate_structured`, which uses `build_chain` (ADR 0002 routing; never call a provider directly).

**Files:**
- Create: `backend/models/job_draft.py`
- Create: `backend/services/job_description_draft.py`
- Create: `backend/routers/job_drafts.py`
- Modify: `backend/main.py`, `backend/utils/permissions.py`
- Test: `backend/tests/test_job_drafts.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_job_drafts.py`:

```python
"""AI job description drafts (ATS Phase E)."""
from __future__ import annotations

import asyncio

from backend.models.job_draft import JobDraftRequest
from backend.services import job_description_draft as drafting
from backend.services.llm.base import AllProvidersFailedError
from backend.tests.phase_e_helpers import staff_client


class FakeLLM:
    def __init__(self, data=None, error=None):
        self.data = data or {
            "job_overview": "Own the platform \u2014 end to end.",
            "required_qualifications": "Python\nSQL",
        }
        self.error = error
        self.calls = []

    async def generate_structured(self, prompt, schema, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        return self.data


REQUEST = {
    "title": "Platform Engineer, contact me at hm@example.test or 555-123-4567",
    "department": "Engineering",
    "experience_level": "senior",
    "location_type": "remote",
    "skills": ["Python", "Kubernetes"],
}


def test_prompt_holds_only_job_fields_and_is_scrubbed():
    prompt = drafting.build_prompt(JobDraftRequest(**REQUEST))
    assert "Platform Engineer" in prompt and "Kubernetes" in prompt and "senior" in prompt
    assert "hm@example.test" not in prompt and "555-123-4567" not in prompt


def test_draft_goes_through_the_chain_and_normalizes_dashes():
    llm = FakeLLM()
    draft = asyncio.run(drafting.draft(JobDraftRequest(**REQUEST), llm=llm))
    assert "\u2014" not in draft.job_overview
    assert draft.required_qualifications == "Python\nSQL"
    assert llm.calls[0][1]["task_type"] == "job_description"


def test_draft_route_permissions(demo_client, db_session, override_get_db, monkeypatch):
    monkeypatch.setattr(drafting, "get_llm_service", lambda: FakeLLM())
    url = "/api/job-drafts/description"
    assert demo_client.post(url, json=REQUEST).status_code == 403
    assert staff_client(db_session, "hiring_team").post(url, json=REQUEST).status_code == 403
    response = staff_client(db_session, "hiring_manager").post(url, json=REQUEST)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"job_overview", "required_qualifications"}


def test_draft_route_reports_provider_failure_as_503(admin_client, monkeypatch):
    monkeypatch.setattr(
        drafting, "get_llm_service", lambda: FakeLLM(error=AllProvidersFailedError([RuntimeError("down")]))
    )
    response = admin_client.post("/api/job-drafts/description", json=REQUEST)
    assert response.status_code == 503
    assert "write the description by hand" in response.json()["detail"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_job_drafts.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.models.job_draft'`.

Check `AllProvidersFailedError`'s constructor in `backend/services/llm/base.py`; if it does not take a list, construct it the way that file defines.

- [ ] **Step 3: Write the models**

Create `backend/models/job_draft.py`:

```python
"""Request and response shapes for AI job description drafts (ATS Phase E)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class JobDraftRequest(BaseModel):
    """Only the structured job fields. There is deliberately no free-text field."""
    title: str = Field(min_length=1, max_length=255)
    department: Optional[str] = Field(default=None, max_length=100)
    experience_level: Optional[str] = Field(default=None, max_length=50)
    location_type: Optional[str] = Field(default=None, max_length=50)
    skills: List[str] = Field(default_factory=list, max_length=30)


class JobDescriptionDraft(BaseModel):
    job_overview: str
    required_qualifications: str
```

- [ ] **Step 4: Write the service**

Create `backend/services/job_description_draft.py`:

```python
"""Draft a job overview and qualifications from the job's own fields (ATS Phase E).

The prompt is built from the structured fields a job writer typed and
nothing else: no candidate, resume, or note is ever read here. Each field
is still scrubbed with the upload de-identification rules, so contact
details pasted into a title by mistake stay on the server. The call goes
through LLMService, which routes via build_chain (ADR 0002); add
LLM_PROVIDER_ORDER_JOB_DESCRIPTION to route it separately.
"""
from __future__ import annotations

from typing import Optional

from backend.models.job_draft import JobDescriptionDraft, JobDraftRequest
from backend.services.assistant_tools import plain_dashes
from backend.services.llm_service import get_llm_service
from backend.services.resume_privacy import scrub_text

TASK_TYPE = "job_description"

SYSTEM_PROMPT = (
    "You write clear, inclusive job descriptions for a recruiting team. Use plain "
    "American English and short sentences. Do not use em dashes. Do not invent a "
    "company name, salary, benefits, or facts that were not given."
)


def build_prompt(request: JobDraftRequest) -> str:
    counts = {"name_mentions": 0, "emails": 0, "phones": 0, "links": 0}

    def clean(value: Optional[str]) -> str:
        return scrub_text((value or "").strip(), [], counts)

    lines = [f"Title: {clean(request.title)}"]
    if request.department:
        lines.append(f"Department: {clean(request.department)}")
    if request.experience_level:
        lines.append(f"Experience level: {clean(request.experience_level)}")
    if request.location_type:
        lines.append(f"Work arrangement: {clean(request.location_type)}")
    skills = [clean(skill) for skill in request.skills if skill and skill.strip()]
    if skills:
        lines.append("Key skills: " + ", ".join(skills))

    return (
        "Draft a job description for the role below.\n"
        "Write job_overview as two short paragraphs about what the person will do "
        "and why the work matters.\n"
        "Write required_qualifications as 4 to 7 lines, one requirement per line, "
        "with no bullet characters.\n"
        "Use only the facts given.\n\n" + "\n".join(lines)
    )


async def draft(request: JobDraftRequest, llm=None) -> JobDescriptionDraft:
    """Raises AllProvidersFailedError when no tier answers, ValueError on unusable output."""
    llm = llm or get_llm_service()
    data = await llm.generate_structured(
        build_prompt(request),
        JobDescriptionDraft,
        system_message=SYSTEM_PROMPT,
        max_tokens=900,
        task_type=TASK_TYPE,
    )
    parsed = JobDescriptionDraft.model_validate(data)
    return JobDescriptionDraft(
        job_overview=plain_dashes(parsed.job_overview).strip(),
        required_qualifications=plain_dashes(parsed.required_qualifications).strip(),
    )
```

- [ ] **Step 5: Write the router**

Create `backend/routers/job_drafts.py`:

```python
"""AI job description drafts (ATS Phase E).

`async def` because it awaits the provider chain. It takes no `get_db`
itself; `require()` is a sync dependency FastAPI runs in its threadpool.
Nothing is written to the database: the draft goes back into the job form
for a person to edit and save.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ..models.job_draft import JobDescriptionDraft, JobDraftRequest
from ..models.models import User
from ..services import job_description_draft as drafting
from ..services.llm.base import AllProvidersFailedError
from ..utils.permissions import JOBS_WRITE, require

router = APIRouter()


@router.post("/job-drafts/description", response_model=JobDescriptionDraft)
async def draft_job_description(
    payload: JobDraftRequest,
    user: User = Depends(require(JOBS_WRITE)),
) -> JobDescriptionDraft:
    try:
        return await drafting.draft(payload)
    except AllProvidersFailedError:
        raise HTTPException(
            status_code=503,
            detail="The drafting service is unavailable right now. Try again later, or write the description by hand.",
        )
    except (ValidationError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="The draft came back in a shape we could not use. Try again, or write the description by hand.",
        )
```

- [ ] **Step 6: Mount it and grant it**

In `backend/main.py`, add `job_drafts` to the routers import line and, with the other Phase E includes above the pipeline router:

```python
app.include_router(job_drafts.router, prefix="/api", tags=["job-drafts"])
```

Add to `ROUTE_PERMISSIONS`:

```python
    ("POST", r"^/api/job-drafts/description$", JOBS_WRITE),  # Phase E
```

- [ ] **Step 7: Run the tests**

Run: `poetry run pytest backend/tests/test_job_drafts.py backend/tests/test_auth.py -q -p no:cacheprovider`
Expected: 4 passed; auth suite green.

- [ ] **Step 8: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e9.txt`:

```
feat: AI job description draft for job writers

Built from the structured job fields only and scrubbed with the upload
de-identification rules, then sent through LLMService and therefore the
provider chain (routable on its own via
LLM_PROVIDER_ORDER_JOB_DESCRIPTION). Dashes are normalized server side.
Admins and hiring managers may draft; provider failure is a 503 that
tells the user to write it by hand. Nothing is saved by this endpoint.
```

```powershell
git add backend/models/job_draft.py backend/services/job_description_draft.py backend/routers/job_drafts.py backend/main.py backend/utils/permissions.py backend/tests/test_job_drafts.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e9.txt
```

---

### Task 10: Contract files and the full backend suite

**Files:**
- Regenerate: `openapi.json`, `web/src/lib/schema.d.ts`
- Possibly: `backend/tests/golden/api_response_shapes.json`

- [ ] **Step 1: Export OpenAPI and regenerate web types**

```powershell
poetry run python scripts/export_openapi.py
poetry run python scripts/export_openapi.py --check
cd web; npm run types:api; cd ..
Select-String web/src/lib/schema.d.ts -Pattern "PublicStatus:|StatusLinkOut:|EmailPreview:|EmailLogOut:|JobDescriptionDraft:|NewStage:"
```

Expected: `--check` passes; all six schema names found; `StageOut` now has `custom?` and `movable?`.

- [ ] **Step 2: Check the API contract golden**

```powershell
poetry run pytest backend/tests/test_api_contract.py -q -p no:cacheprovider
```

If it fails only because a captured shape gained `custom` or `movable` (or any other Phase E field), regenerate and read the diff:

```powershell
$env:UPDATE_API_GOLDEN = "1"
poetry run pytest backend/tests/test_api_contract.py -q -p no:cacheprovider
Remove-Item Env:UPDATE_API_GOLDEN
git diff backend/tests/golden/api_response_shapes.json
```

Expected diff: additions only. Any removed key is a regression; stop and fix.

- [ ] **Step 3: Lint and the full suite on the scratch database**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
$env:OLLAMA_BASE_URL = "http://localhost:1"
poetry run ruff check backend --select E9,F63,F7,F82 --exclude backend/tests
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
poetry run pytest -q -p no:cacheprovider
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
```

Run the suite in the background (about 8 minutes) and start Task 11 meanwhile.

Expected: ruff clean; everything green except the two embedding tests known to fail only under the unreachable-Ollama env (if they still exist).

- [ ] **Step 4: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e10.txt`:

```
chore: regenerate OpenAPI and web types for Phase E

openapi.json and schema.d.ts gain the status link, email, job draft,
and stage editor shapes. Full suite green on a scratch database built
from migrations alone.
```

```powershell
git add openapi.json web/src/lib/schema.d.ts
git add backend/tests/golden/api_response_shapes.json  # only if Step 2 regenerated it
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e10.txt
```

---

### Task 11: Web types, fetchers, and one forwarding helper

Every new client action needs a Next route handler (the browser never sees the session token). Instead of copying the existing 60-line proxy six times, one helper does the token, the 401, the 503, and the pass-through.

**Files:**
- Modify: `web/src/lib/domain.ts`, `web/src/lib/data.ts`
- Create: `web/src/lib/forward.ts`, `web/src/lib/forward.test.ts`
- Create: the six route handlers listed in the file table

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/forward.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getToken = vi.fn();
vi.mock("./session", () => ({ getToken: () => getToken() }));

const { forward } = await import("./forward");

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  getToken.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("forward", () => {
  it("refuses without a session and never calls the API", async () => {
    getToken.mockResolvedValue(null);
    const response = await forward("/api/x", { method: "POST", signInMessage: "Sign in first." });
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ detail: "Sign in first." });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("passes the upstream status and body through with the bearer token", async () => {
    getToken.mockResolvedValue("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Move them first." }), { status: 409 }),
    );
    const response = await forward("/api/x", {
      method: "PUT",
      body: { a: 1 },
      signInMessage: "Sign in first.",
    });
    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({ detail: "Move them first." });
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toMatch(/\/api\/x$/);
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer jwt-abc");
    expect(init?.body).toBe(JSON.stringify({ a: 1 }));
  });

  it("answers 503 when the API is unreachable", async () => {
    getToken.mockResolvedValue("jwt-abc");
    vi.mocked(fetch).mockRejectedValue(new Error("ECONNREFUSED"));
    const response = await forward("/api/x", { method: "GET", signInMessage: "Sign in first." });
    expect(response.status).toBe(503);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd web; npx vitest run src/lib/forward.test.ts`
Expected: FAIL, cannot resolve `./forward`.

- [ ] **Step 3: Write the helper**

Create `web/src/lib/forward.ts`:

```ts
/**
 * Forward one browser action to the API with the httpOnly session token.
 *
 * Every Phase E route handler is this plus input checks. The backend's
 * permission gate is the authority; this only attaches the token and passes
 * the status and body back untouched. Plain `Response`, not `NextResponse`:
 * route handlers accept either, and plain responses keep this testable.
 */
import "server-only";

import { API_BASE_URL } from "./config";
import { getToken } from "./session";

export type ForwardMethod = "GET" | "POST" | "PUT" | "DELETE";

export async function forward(
  upstreamPath: string,
  {
    method,
    body,
    signInMessage,
  }: { method: ForwardMethod; body?: unknown; signInMessage: string },
): Promise<Response> {
  const token = await getToken();
  if (!token) return Response.json({ detail: signInMessage }, { status: 401 });

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const init: RequestInit = { method, headers, cache: "no-store" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}${upstreamPath}`, init);
  } catch {
    return Response.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  const text = await upstream.text();
  return new Response(text || null, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The request's JSON body, or undefined when there is none or it is not JSON. */
export async function readJson(request: Request): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    return undefined;
  }
}

export const isId = (value: string) => /^\d+$/.test(value);

export function badRequest(detail: string): Response {
  return Response.json({ detail }, { status: 400 });
}
```

- [ ] **Step 4: Write the route handlers**

Create `web/src/app/api/applications/[id]/status-link/route.ts`:

```ts
import { badRequest, forward, isId } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const SIGN_IN = "Sign in to manage status links.";
type Context = { params: Promise<{ id: string }> };

async function handle(context: Context, method: "POST" | "DELETE") {
  const { id } = await context.params;
  if (!isId(id)) return badRequest("That is not a valid application id.");
  return forward(`/api/applications/${id}/status-link`, { method, signInMessage: SIGN_IN });
}

export async function POST(_request: Request, context: Context) {
  return handle(context, "POST");
}

export async function DELETE(_request: Request, context: Context) {
  return handle(context, "DELETE");
}
```

Create `web/src/app/api/applications/[id]/emails/route.ts`:

```ts
import { badRequest, forward, isId, readJson } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!isId(id)) return badRequest("That is not a valid application id.");
  const body = await readJson(request);
  if (body === undefined) return badRequest("Expected a JSON body.");
  return forward(`/api/applications/${id}/emails`, {
    method: "POST",
    body,
    signInMessage: "Sign in to email candidates.",
  });
}
```

Create `web/src/app/api/applications/[id]/emails/preview/route.ts`:

```ts
import { badRequest, forward, isId } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!isId(id)) return badRequest("That is not a valid application id.");
  const key = new URL(request.url).searchParams.get("template_key") ?? "";
  if (!/^[a-z_]{1,50}$/.test(key)) return badRequest("That is not a valid template.");
  return forward(`/api/applications/${id}/emails/preview?template_key=${key}`, {
    method: "GET",
    signInMessage: "Sign in to preview email.",
  });
}
```

Create `web/src/app/api/email-templates/[key]/route.ts`:

```ts
import { badRequest, forward, readJson } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function PUT(request: Request, context: { params: Promise<{ key: string }> }) {
  const { key } = await context.params;
  if (!/^[a-z_]{1,50}$/.test(key)) return badRequest("That is not a valid template.");
  const body = await readJson(request);
  if (body === undefined) return badRequest("Expected a JSON body.");
  return forward(`/api/email-templates/${key}`, {
    method: "PUT",
    body,
    signInMessage: "Sign in to edit templates.",
  });
}
```

Create `web/src/app/api/jobs/[id]/pipeline/route.ts`:

```ts
import { badRequest, forward, isId, readJson } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function PUT(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!isId(id)) return badRequest("That is not a valid job id.");
  const body = await readJson(request);
  if (body === undefined) return badRequest("Expected a JSON body.");
  return forward(`/api/jobs/${id}/pipeline`, {
    method: "PUT",
    body,
    signInMessage: "Sign in to edit stages.",
  });
}
```

Create `web/src/app/api/job-drafts/description/route.ts`:

```ts
import { badRequest, forward, readJson } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  const body = await readJson(request);
  if (body === undefined) return badRequest("Expected a JSON body.");
  return forward("/api/job-drafts/description", {
    method: "POST",
    body,
    signInMessage: "Sign in to draft a job description.",
  });
}
```

(`/api/applications/[id]/status-link` and `/emails` are static segments, so Next prefers them over the Phase A `[action]` handler at the same depth.)

- [ ] **Step 5: Add the type aliases and fetchers**

In `web/src/lib/domain.ts`, below the Phase A aliases:

```ts
/** ATS Phase E: candidate-facing status, email, drafts, and the stage editor. */
export type PublicStatus = Schemas["PublicStatus"];
export type PublicStage = Schemas["PublicStage"];
export type StatusLink = Schemas["StatusLinkOut"];
export type EmailTemplate = Schemas["EmailTemplateOut"];
export type EmailTemplates = Schemas["EmailTemplatesResponse"];
export type EmailPreview = Schemas["EmailPreview"];
export type EmailLogEntry = Schemas["EmailLogOut"];
export type JobDescriptionDraft = Schemas["JobDescriptionDraft"];
export type StageOut = Schemas["StageOut"];
export type PipelineUpdate = Schemas["PipelineUpdateRequest"];
```

In `web/src/lib/data.ts`, change the api import to `import { ApiError, apiFetch, apiFetchOptional } from "./api";`, add `EmailLogEntry`, `EmailTemplates`, `PublicStatus`, and `StatusLink` to the `./domain` type import, and append:

```ts
// --- ATS Phase E -------------------------------------------------------------

/**
 * What a candidate sees at their status link.
 *
 * Deliberately sends no session token: this must render exactly what an
 * anonymous browser gets, even when a staff member opens their own link.
 */
export async function getPublicStatus(token: string): Promise<PublicStatus | null> {
  return apiFetchOptional<PublicStatus>(`/api/public/status/${encodeURIComponent(token)}`);
}

/** The same view, by application, for staff and the demo to preview. */
export async function getCandidateView(applicationId: number | string): Promise<PublicStatus | null> {
  return apiFetchOptional<PublicStatus>(`/api/applications/${applicationId}/candidate-view`, {
    token: await getToken(),
  });
}

/** The application's status link, or null for anyone not allowed to manage it. */
export async function getStatusLink(applicationId: number | string): Promise<StatusLink | null> {
  try {
    return await apiFetchOptional<StatusLink>(`/api/applications/${applicationId}/status-link`, {
      token: await getToken(),
    });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
    throw error;
  }
}

export async function getEmailTemplates(): Promise<EmailTemplates> {
  return apiFetch<EmailTemplates>("/api/email-templates", { token: await getToken() });
}

export async function getEmailLog(applicationId: number | string): Promise<EmailLogEntry[]> {
  return (
    (await apiFetchOptional<EmailLogEntry[]>(`/api/applications/${applicationId}/emails`, {
      token: await getToken(),
    })) ?? []
  );
}
```

- [ ] **Step 6: Run the checks**

Run: `cd web; npx vitest run src/lib/forward.test.ts; npm run typecheck; npm run lint`
Expected: 3 tests pass; typecheck and lint clean.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e11.txt`:

```
feat(web): Phase E fetchers, route handlers, and one forwarding helper

Six new browser actions share one tested helper for the session token,
the signed-out 401, the API-down 503, and status pass-through. The
public status fetcher sends no token on purpose, so staff opening a
candidate's link see exactly what the candidate sees.
```

```powershell
git add web/src/lib/forward.ts web/src/lib/forward.test.ts web/src/lib/domain.ts web/src/lib/data.ts "web/src/app/api/applications/[id]/status-link/route.ts" "web/src/app/api/applications/[id]/emails/route.ts" "web/src/app/api/applications/[id]/emails/preview/route.ts" "web/src/app/api/email-templates/[key]/route.ts" "web/src/app/api/jobs/[id]/pipeline/route.ts" web/src/app/api/job-drafts/description/route.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e11.txt
```

---

### Task 12: The public status page, with no app shell and no session

Two things keep a candidate's page clean. The proxy skips `/c/...`, so visiting a status link never mints a demo session cookie. And the app shell (navigation, session badge, footer) moves out of the root layout into an `(app)` route group, so `/c/...` renders with none of it. Route groups do not change URLs, so every existing link and test keeps working.

**Files:**
- Create: `web/src/lib/public-paths.ts`, `web/src/lib/public-paths.test.ts`
- Modify: `web/src/proxy.ts`
- Modify: `web/src/app/layout.tsx`; Create: `web/src/app/(app)/layout.tsx`; Move: every page directory
- Create: `web/src/lib/public-status.ts`, `web/src/lib/public-status.test.ts`
- Create: `web/src/components/public-status-view.tsx`
- Create: `web/src/app/(public)/layout.tsx`, `web/src/app/(public)/c/[token]/page.tsx`
- Create: `web/src/app/(app)/applications/[id]/candidate-view/page.tsx`
- Create: `web/e2e/public-status.spec.ts`

- [ ] **Step 1: Write the failing unit tests**

Create `web/src/lib/public-paths.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { isPublicPath } from "./public-paths";

describe("isPublicPath", () => {
  it("covers candidate status links and nothing else", () => {
    expect(isPublicPath("/c/abc123")).toBe(true);
    expect(isPublicPath("/c/abc123/extra")).toBe(true);
    expect(isPublicPath("/candidates")).toBe(false);
    expect(isPublicPath("/c")).toBe(false);
    expect(isPublicPath("/")).toBe(false);
  });
});
```

Create `web/src/lib/public-status.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { PublicStatus } from "./domain";
import { PUBLIC_STATE_LABELS, currentStageName, greeting, looksLikeToken } from "./public-status";

const STATUS: PublicStatus = {
  first_name: "Mira",
  job_title: "Platform Engineer",
  department: "Engineering",
  status: "In progress",
  stages: [
    { name: "Resume submitted", description: null, state: "done" },
    { name: "Hiring manager review", description: "Review.", state: "current" },
  ],
};

describe("public status helpers", () => {
  it("greets by first name, or politely without one", () => {
    expect(greeting("Mira")).toBe("Hi Mira,");
    expect(greeting("  ")).toBe("Hello,");
    expect(greeting(null)).toBe("Hello,");
  });

  it("finds the current stage", () => {
    expect(currentStageName(STATUS)).toBe("Hiring manager review");
    expect(currentStageName({ ...STATUS, stages: [] })).toBeNull();
  });

  it("only calls the API for token-shaped values", () => {
    expect(looksLikeToken("abcdefghijklmnopqrstuvwxyz012345")).toBe(true);
    expect(looksLikeToken("short")).toBe(false);
    expect(looksLikeToken("../../etc/passwd-xxxxxxxxxxxx")).toBe(false);
  });

  it("labels every state in plain English", () => {
    expect(PUBLIC_STATE_LABELS.current).toBe("In progress");
    expect(PUBLIC_STATE_LABELS.closed).toBe("Closed");
  });
});
```

Run: `cd web; npx vitest run src/lib/public-paths.test.ts src/lib/public-status.test.ts`
Expected: FAIL, modules not found.

- [ ] **Step 2: Write the helpers**

Create `web/src/lib/public-paths.ts`:

```ts
/**
 * Paths a candidate opens from an email. They never get a demo session and
 * never render the app shell.
 */
export const PUBLIC_PREFIXES = ["/c/"] as const;

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}
```

Create `web/src/lib/public-status.ts`:

```ts
/** Vocabulary for the candidate-facing status page. */
import type { PublicStatus } from "./domain";

export const PUBLIC_STATE_LABELS: Record<string, string> = {
  done: "Complete",
  current: "In progress",
  upcoming: "Coming up",
  closed: "Closed",
};

export function greeting(firstName: string | null | undefined): string {
  const name = firstName?.trim();
  return name ? `Hi ${name},` : "Hello,";
}

export function currentStageName(status: PublicStatus): string | null {
  return status.stages.find((stage) => stage.state === "current")?.name ?? null;
}

/** Status tokens are 32 URL-safe characters; anything else is not worth a request. */
const TOKEN_SHAPE = /^[A-Za-z0-9_-]{16,64}$/;

export function looksLikeToken(value: string): boolean {
  return TOKEN_SHAPE.test(value);
}
```

- [ ] **Step 3: Skip public paths in the proxy**

In `web/src/proxy.ts`, add `import { isPublicPath } from "./lib/public-paths";` below the config import, and make this the first statement in `proxy()`:

```ts
  // A candidate opening their status link must never be handed a session:
  // the page reads nothing private, and a staff-side token minted for
  // someone outside the company would be the wrong default.
  if (isPublicPath(request.nextUrl.pathname)) {
    return NextResponse.next();
  }
```

- [ ] **Step 4: Move the app shell into an `(app)` route group**

Move every page entry under `web/src/app` except the API routes and the root files:

```powershell
New-Item -ItemType Directory -Force "web/src/app/(app)" | Out-Null
$keep = @("api", "globals.css", "layout.tsx", "not-found.tsx", "favicon.ico", "(app)", "(public)")
Get-ChildItem web/src/app | Where-Object { $keep -notcontains $_.Name } | ForEach-Object {
  git mv -- "web/src/app/$($_.Name)" "web/src/app/(app)/$($_.Name)"
}
Copy-Item web/src/app/not-found.tsx "web/src/app/(app)/not-found.tsx"
git status --short web/src/app
```

Expected: renames for `page.tsx`, `loading.tsx`, and every page directory (Phase A's `candidates`, `jobs`, and so on, plus B to D's `interviews`, `team`, `settings`, `reports`); a new `(app)/not-found.tsx`. `api` did not move.

Now split `web/src/app/layout.tsx`:

1. Create `web/src/app/(app)/layout.tsx`. Its body is **everything that is currently between `<body ...>` and `</body>` in `web/src/app/layout.tsx`** (the header or Phase B sidebar, `<main>`, and the footer), returned inside a fragment, plus the imports those elements use (`Link`, `Suspense`, `Nav` or `Sidebar`, `SessionBadge`, `SessionBadgeFallback`, and anything Phase B added). Shape:

```tsx
import type { ReactNode } from "react";
// ...the imports the moved JSX needs, cut from app/layout.tsx...

/**
 * The staff app shell: navigation, session badge, footer.
 *
 * Lives in the (app) route group rather than the root layout so the
 * candidate-facing /c/[token] page (the (public) group) renders without
 * any of it. Route groups do not change URLs.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <>
      {/* ...the JSX that was inside <body>, unchanged, with {children} where it was... */}
    </>
  );
}
```

2. Replace `web/src/app/layout.tsx` with the document only. Keep the font setup and metadata exactly as they are today; for reference, as of Phase A it was:

```tsx
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist_Mono, Inter } from "next/font/google";

import "./globals.css";

// globals.css resolves the Tailwind font tokens from --font-sans; the variable
// name must match or every screen silently falls back to the browser stack.
const inter = Inter({ variable: "--font-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RecruitIQ",
  description: "AI-assisted applicant tracking, built by a recruiter.",
};

/**
 * The document only. The staff shell is app/(app)/layout.tsx; the
 * candidate-facing pages are app/(public).
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
```

3. Run `cd web; npm run typecheck; npm run lint`. Expected: clean. `PageProps<"/candidates/[id]">` and friends are unchanged because route groups do not affect paths.

- [ ] **Step 5: Write the shared view and the public page**

Create `web/src/components/public-status-view.tsx`:

```tsx
import { Check, Circle, CircleDot, X } from "lucide-react";

import type { PublicStatus } from "@/lib/domain";
import { PUBLIC_STATE_LABELS, greeting } from "@/lib/public-status";
import { cn } from "@/lib/utils";

const ICONS = { done: Check, current: CircleDot, upcoming: Circle, closed: X } as const;

const ICON_CLASSES: Record<string, string> = {
  done: "text-emerald-600",
  current: "text-indigo-600",
  upcoming: "text-slate-300",
  closed: "text-slate-400",
};

/**
 * What a candidate sees: greeting, job, status, and the stage list with the
 * candidate-facing descriptions. Rendered from the allowlisted API shape
 * only; there is nothing else to render.
 */
export function PublicStatusView({ status }: { status: PublicStatus }) {
  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <p className="text-sm text-slate-500">{greeting(status.first_name)}</p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Your application for {status.job_title}
        </h1>
        <p className="text-sm text-slate-600">
          {status.department ? `${status.department} · ` : ""}
          <span className="font-medium text-slate-800">{status.status}</span>
        </p>
      </header>

      <ol className="space-y-1 rounded-lg border border-slate-200 bg-white p-4">
        {status.stages.map((stage, index) => {
          const Icon = ICONS[stage.state as keyof typeof ICONS] ?? Circle;
          const isCurrent = stage.state === "current";
          return (
            <li
              key={`${index}-${stage.name}`}
              className={cn(
                "flex items-start gap-3 rounded-md px-2 py-2 text-sm",
                isCurrent && "bg-indigo-50",
              )}
            >
              <Icon
                className={cn("mt-0.5 h-4 w-4 shrink-0", ICON_CLASSES[stage.state])}
                aria-hidden
              />
              <span className="min-w-0 flex-1">
                <span
                  className={cn("block", isCurrent ? "font-medium text-slate-900" : "text-slate-700")}
                >
                  {stage.name}
                </span>
                {stage.description && stage.state !== "closed" ? (
                  <span className="block text-xs text-slate-500">{stage.description}</span>
                ) : null}
              </span>
              <span className="shrink-0 text-xs text-slate-400">
                {PUBLIC_STATE_LABELS[stage.state] ?? ""}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-xs text-slate-500">
        This page shows where your application stands. It never includes interview notes, feedback,
        or scores. If you have a question, reply to the email that brought you here.
      </p>
    </article>
  );
}
```

Create `web/src/app/(public)/layout.tsx`:

```tsx
import type { Metadata } from "next";
import type { ReactNode } from "react";

/**
 * Candidate-facing pages: no navigation, no session, not indexed, and no
 * Referer header, so the token in the URL is never sent to another site.
 */
export const metadata: Metadata = {
  title: "Application status",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function PublicLayout({ children }: { children: ReactNode }) {
  return <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:px-6">{children}</main>;
}
```

Create `web/src/app/(public)/c/[token]/page.tsx`:

```tsx
import { PublicStatusView } from "@/components/public-status-view";
import { getPublicStatus } from "@/lib/data";
import { looksLikeToken } from "@/lib/public-status";

export const dynamic = "force-dynamic";

export default async function CandidateStatusPage({ params }: PageProps<"/c/[token]">) {
  const { token } = await params;
  const status = looksLikeToken(token) ? await getPublicStatus(token).catch(() => null) : null;

  if (!status) {
    return (
      <div className="space-y-3 py-16 text-center">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">
          This link is not active
        </h1>
        <p className="mx-auto max-w-md text-sm text-slate-600">
          It may have been replaced by a newer link. Ask the person who sent it to you for a fresh
          one.
        </p>
      </div>
    );
  }

  return <PublicStatusView status={status} />;
}
```

- [ ] **Step 6: Write the staff preview page**

Create `web/src/app/(app)/applications/[id]/candidate-view/page.tsx`:

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PublicStatusView } from "@/components/public-status-view";
import { getApplication, getCandidateView } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function CandidateViewPage({
  params,
}: PageProps<"/applications/[id]/candidate-view">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const [view, application] = await Promise.all([getCandidateView(id), getApplication(id)]);
  if (!view || !application) notFound();

  return (
    <>
      <Link
        href={`/candidates/${application.candidate_id}`}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to {application.candidate_name}
      </Link>
      <div className="mb-6 max-w-2xl rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        Preview. This is exactly what the candidate sees at their status link. Nothing here comes
        from notes, feedback, or match scores.
      </div>
      <div className="max-w-2xl">
        <PublicStatusView status={view} />
      </div>
    </>
  );
}
```

- [ ] **Step 7: Write the end-to-end check**

Create `web/e2e/public-status.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

/**
 * A status link must render without the app shell and must not mint the
 * demo session that every other first visit gets.
 */
test("a status link never mints a session and shows no navigation", async ({ page, context }) => {
  await page.goto("/c/not-a-real-token-000000");
  await expect(page.getByRole("heading", { name: "This link is not active" })).toBeVisible();
  const cookies = await context.cookies();
  expect(cookies.find((cookie) => cookie.name === "recruitiq_session")).toBeUndefined();
  await expect(page.getByRole("link", { name: "Candidates" })).toHaveCount(0);
});
```

- [ ] **Step 8: Run the checks**

```powershell
cd web
npx vitest run src/lib/public-paths.test.ts src/lib/public-status.test.ts
npm run typecheck; npm run lint; npm test
cd ..
```

Expected: 5 new tests pass; everything clean.

- [ ] **Step 9: Check it live**

Start the backend (`cd backend; poetry run python -m uvicorn main:app --port 8010`) and the web dev server (`cd web; npm run dev`). Create a link for any seeded application with a dev admin token (mint one with a short scratchpad script that calls `create_access_token` on the first admin user, as in Phase A), then:

1. Open `http://localhost:3000/c/<token>` in a private window. Expected: greeting, job, stage list; no navigation; DevTools shows no `recruitiq_session` cookie.
2. Open `http://localhost:3000/applications/<id>/candidate-view`. Expected: the same content inside the app shell with the amber "Preview" banner.
3. Open `http://localhost:3000/`, `/candidates`, `/jobs`. Expected: unchanged.

Then: `cd web; $env:E2E_BASE_URL = "http://localhost:3000"; npx playwright test`. Expected: all pass, including the new spec.

- [ ] **Step 10: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e12.txt`:

```
feat(web): candidate status page with no app shell and no session

The staff shell moves into an (app) route group (URLs unchanged) so
/c/[token] renders on its own; the proxy skips /c/ so a candidate never
receives the demo session cookie; the page is noindex and sends no
Referer. Staff and the demo get the same view as a preview per
application. Verified with unit tests, a Playwright check that no
session cookie is set, and live in a private window.
```

```powershell
git add -A web/src/app
git add web/src/proxy.ts web/src/lib/public-paths.ts web/src/lib/public-paths.test.ts web/src/lib/public-status.ts web/src/lib/public-status.test.ts web/src/components/public-status-view.tsx web/e2e/public-status.spec.ts
git status --short
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e12.txt
```

(`git add -A web/src/app` is scoped to that directory on purpose: the move touches every page and is easiest to stage as one unit. Check `git status --short` shows only renames and the new files before committing.)

---

### Task 13: Candidate communication on the candidate page

**Files:**
- Create: `web/src/lib/email-composer.ts`, `web/src/lib/email-composer.test.ts`
- Create: `web/src/components/status-link-control.tsx`, `web/src/components/email-composer.tsx`, `web/src/components/application-outreach.tsx`
- Modify: `web/src/components/application-timeline.tsx`
- Modify: `web/src/app/(app)/candidates/[id]/page.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/email-composer.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  composeClipboardText,
  remainingPlaceholders,
  sendState,
  unknownPlaceholders,
} from "./email-composer";

describe("remainingPlaceholders", () => {
  it("lists unfilled markers once, in order", () => {
    expect(remainingPlaceholders("Hi {{a}}", "{{ b }} {{a}}")).toEqual(["a", "b"]);
    expect(remainingPlaceholders("All filled in.")).toEqual([]);
  });
});

describe("unknownPlaceholders", () => {
  it("flags markers outside the allowed list", () => {
    expect(unknownPlaceholders("{{job_title}} {{salary}}", ["job_title"])).toEqual(["salary"]);
  });
});

describe("composeClipboardText", () => {
  it("puts the subject on its own line above the body", () => {
    expect(composeClipboardText(" Hello ", "Body\n")).toBe("Subject: Hello\n\nBody\n");
  });
});

describe("sendState", () => {
  it("explains every reason sending is not available", () => {
    expect(sendState({ canSend: false, transportConfigured: true, remaining: [] }).allowed).toBe(false);
    expect(
      sendState({ canSend: true, transportConfigured: true, remaining: ["status_link"] }).reason,
    ).toBe("Fill in {{status_link}} first.");
    expect(
      sendState({ canSend: true, transportConfigured: false, remaining: [] }).reason,
    ).toMatch(/No mail server/);
    expect(sendState({ canSend: true, transportConfigured: true, remaining: [] })).toEqual({
      allowed: true,
      reason: null,
    });
  });
});
```

Run: `cd web; npx vitest run src/lib/email-composer.test.ts`
Expected: FAIL, module not found.

- [ ] **Step 2: Write the helpers**

Create `web/src/lib/email-composer.ts`:

```ts
/**
 * Rules for the email composer, kept pure so they are tested without
 * rendering. The server refuses the same things; this only decides what the
 * buttons say.
 */
const PLACEHOLDER = /\{\{\s*([A-Za-z_]+)\s*\}\}/g;

function placeholdersIn(text: string): string[] {
  return Array.from(text.matchAll(PLACEHOLDER), (match) => match[1]);
}

export function remainingPlaceholders(...texts: string[]): string[] {
  return [...new Set(texts.flatMap(placeholdersIn))];
}

export function unknownPlaceholders(text: string, allowed: readonly string[]): string[] {
  return [...new Set(placeholdersIn(text).filter((name) => !allowed.includes(name)))];
}

export function composeClipboardText(subject: string, body: string): string {
  return `Subject: ${subject.trim()}\n\n${body.trim()}\n`;
}

export function sendState({
  canSend,
  transportConfigured,
  remaining,
}: {
  canSend: boolean;
  transportConfigured: boolean;
  remaining: string[];
}): { allowed: boolean; reason: string | null } {
  if (!canSend) {
    return { allowed: false, reason: "Your account can preview email but not send it." };
  }
  if (remaining.length > 0) {
    return {
      allowed: false,
      reason: `Fill in ${remaining.map((name) => `{{${name}}}`).join(", ")} first.`,
    };
  }
  if (!transportConfigured) {
    return {
      allowed: false,
      reason: "No mail server is configured. Copy the text and send it from your own inbox.",
    };
  }
  return { allowed: true, reason: null };
}
```

- [ ] **Step 3: Write the status link control**

Create `web/src/components/status-link-control.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Check, Copy, Link2, Loader2, RefreshCw, Unlink } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { StatusLink } from "@/lib/domain";

/**
 * Create, copy, replace, or turn off a candidate's status link.
 *
 * Shows the relative path, not an absolute URL, so server and client render
 * the same text; the absolute URL is built only when copying.
 */
export function StatusLinkControl({
  applicationId,
  initial,
}: {
  applicationId: number;
  initial: StatusLink;
}) {
  const [link, setLink] = useState<StatusLink>(initial);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(method: "POST" | "DELETE") {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${applicationId}/status-link`, { method });
      const payload = (await response.json().catch(() => null)) as
        | (StatusLink & { detail?: string })
        | null;
      if (!response.ok || !payload) {
        throw new Error(payload?.detail || `Could not update the link (${response.status})`);
      }
      setLink(payload);
      setCopied(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!link.path) return;
    await navigator.clipboard.writeText(new URL(link.path, window.location.origin).toString());
    setCopied(true);
  }

  return (
    <div className="space-y-2 text-sm">
      <p className="text-xs text-slate-500">
        Anyone with the link sees the candidate&apos;s first name, the job, and the stage list.
        Nothing else.
      </p>
      {link.active && link.path ? (
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={link.path}
            target="_blank"
            rel="noreferrer"
            className="max-w-full truncate font-mono text-xs text-indigo-700 hover:underline"
          >
            {link.path}
          </a>
          <Button type="button" size="sm" variant="outline" onClick={copy} disabled={busy}>
            {copied ? <Check className="mr-1 h-3.5 w-3.5" aria-hidden /> : <Copy className="mr-1 h-3.5 w-3.5" aria-hidden />}
            {copied ? "Copied" : "Copy link"}
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => call("POST")} disabled={busy}>
            <RefreshCw className="mr-1 h-3.5 w-3.5" aria-hidden />
            Replace
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => call("DELETE")} disabled={busy}>
            <Unlink className="mr-1 h-3.5 w-3.5" aria-hidden />
            Turn off
          </Button>
        </div>
      ) : (
        <Button type="button" size="sm" variant="outline" onClick={() => call("POST")} disabled={busy}>
          {busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden /> : <Link2 className="mr-1 h-3.5 w-3.5" aria-hidden />}
          Create status link
        </Button>
      )}
      {link.active ? (
        <p className="text-xs text-slate-400">Replacing the link stops the old one working immediately.</p>
      ) : null}
      {error ? <p className="text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 4: Write the composer**

Create `web/src/components/email-composer.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Loader2, Mail, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { EmailPreview } from "@/lib/domain";
import { composeClipboardText, remainingPlaceholders, sendState } from "@/lib/email-composer";

/**
 * Pick a template, review and edit the filled-in text, then send it or copy
 * it. Copying is always possible; when the account may send and nothing is
 * left unfilled, a copy is also written to the email history.
 */
export function EmailComposer({
  applicationId,
  templates,
  transportConfigured,
  canSend,
}: {
  applicationId: number;
  templates: { key: string; name: string }[];
  transportConfigured: boolean;
  canSend: boolean;
}) {
  const router = useRouter();
  const [templateKey, setTemplateKey] = useState(templates[0]?.key ?? "");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [toAddress, setToAddress] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState<"load" | "send" | "copy" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const remaining = remainingPlaceholders(subject, body);
  const state = sendState({ canSend, transportConfigured, remaining });

  async function load() {
    setBusy("load");
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(
        `/api/applications/${applicationId}/emails/preview?template_key=${encodeURIComponent(templateKey)}`,
      );
      const payload = (await response.json().catch(() => null)) as
        | (EmailPreview & { detail?: string })
        | null;
      if (!response.ok || !payload) {
        throw new Error(payload?.detail || `Could not load the template (${response.status})`);
      }
      setSubject(payload.subject);
      setBody(payload.body);
      setToAddress(payload.to_address ?? null);
      setLoaded(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function record(mode: "send" | "copied") {
    const response = await fetch(`/api/applications/${applicationId}/emails`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_key: templateKey || null, subject, body, mode }),
    });
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    if (!response.ok) {
      throw new Error(payload?.detail || `Could not record the email (${response.status})`);
    }
  }

  async function send() {
    setBusy("send");
    setError(null);
    try {
      await record("send");
      setNotice(`Sent to ${toAddress ?? "the candidate"}.`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function copy() {
    setBusy("copy");
    setError(null);
    try {
      await navigator.clipboard.writeText(composeClipboardText(subject, body));
      if (canSend && remaining.length === 0) {
        await record("copied");
        setNotice("Copied, and noted in the email history.");
        router.refresh();
      } else {
        setNotice("Copied.");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={`template-${applicationId}`} className="text-xs font-medium text-slate-600">
          Template
        </label>
        <select
          id={`template-${applicationId}`}
          value={templateKey}
          onChange={(e) => setTemplateKey(e.target.value)}
          className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm"
        >
          {templates.map((template) => (
            <option key={template.key} value={template.key}>
              {template.name}
            </option>
          ))}
        </select>
        <Button type="button" size="sm" variant="outline" onClick={load} disabled={busy !== null || !templateKey}>
          {busy === "load" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden /> : <Mail className="mr-1 h-3.5 w-3.5" aria-hidden />}
          Use template
        </Button>
      </div>

      {loaded ? (
        <>
          {toAddress ? <p className="text-xs text-slate-500">To: {toAddress}</p> : null}
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={10} aria-label="Message" />
          {state.reason ? <p className="text-xs text-amber-700">{state.reason}</p> : null}
          <div className="flex flex-wrap gap-2">
            {canSend && transportConfigured ? (
              <Button type="button" onClick={send} disabled={!state.allowed || busy !== null}>
                {busy === "send" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : <Send className="mr-2 h-4 w-4" aria-hidden />}
                Send
              </Button>
            ) : null}
            <Button type="button" variant="outline" onClick={copy} disabled={busy !== null}>
              <Copy className="mr-2 h-4 w-4" aria-hidden />
              Copy text
            </Button>
          </div>
        </>
      ) : null}

      {notice ? <p className="text-xs font-medium text-emerald-700">{notice}</p> : null}
      {error ? <p className="text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 5: Write the outreach section and let the timeline hold it**

Create `web/src/components/application-outreach.tsx`:

```tsx
import Link from "next/link";

import { EmailComposer } from "@/components/email-composer";
import { StatusLinkControl } from "@/components/status-link-control";
import type { EmailLogEntry, EmailTemplate, StatusLink } from "@/lib/domain";
import { formatDate } from "@/lib/format";

const LOG_LABELS: Record<string, string> = { sent: "Sent", copied: "Copied", failed: "Failed" };

/** Status link, email composer, and email history for one application. */
export function ApplicationOutreach({
  applicationId,
  statusLink,
  templates,
  transportConfigured,
  emailLog,
  canSend,
}: {
  applicationId: number;
  statusLink: StatusLink | null;
  templates: EmailTemplate[];
  transportConfigured: boolean;
  emailLog: EmailLogEntry[];
  canSend: boolean;
}) {
  return (
    <div className="space-y-4 border-t border-slate-100 pt-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-800">Candidate communication</h3>
        <Link
          href={`/applications/${applicationId}/candidate-view`}
          className="text-xs font-medium text-indigo-700 hover:underline"
        >
          See what the candidate sees
        </Link>
      </div>

      {statusLink ? <StatusLinkControl applicationId={applicationId} initial={statusLink} /> : null}

      <details className="rounded-md border border-slate-200 p-3">
        <summary className="cursor-pointer text-sm text-slate-700">Email the candidate</summary>
        <div className="mt-3">
          <EmailComposer
            applicationId={applicationId}
            templates={templates.map((t) => ({ key: t.key, name: t.name }))}
            transportConfigured={transportConfigured}
            canSend={canSend}
          />
        </div>
      </details>

      {emailLog.length > 0 ? (
        <ul className="space-y-1 text-xs text-slate-500">
          {emailLog.slice(0, 5).map((entry) => (
            <li key={entry.id}>
              <span className="font-medium text-slate-700">{LOG_LABELS[entry.status] ?? entry.status}</span>
              {" · "}
              {entry.subject}
              {" · "}
              {formatDate(entry.created_at)}
              {entry.sent_by_name ? ` · ${entry.sent_by_name}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
```

In `web/src/components/application-timeline.tsx`, add `import type { ReactNode } from "react";`, add `children` to the props:

```tsx
export function ApplicationTimeline({
  application,
  writable,
  children,
}: {
  application: ApplicationDetail;
  writable: boolean;
  children?: ReactNode;
}) {
```

and render `{children}` as the last child of `<CardContent>` (after the `StageActions` block, and after anything Phases B and C added there).

- [ ] **Step 6: Pass the data from the candidate page**

In `web/src/app/(app)/candidates/[id]/page.tsx`, add the imports:

```ts
import { ApplicationOutreach } from "@/components/application-outreach";
```

and add `getEmailLog`, `getEmailTemplates`, `getStatusLink` to the `@/lib/data` import list.

After `details` is computed, add:

```ts
  // Outreach data is optional context: a failure here must not take down the
  // profile, so each piece falls back to empty.
  const [templates, statusLinks, emailLogs] = await Promise.all([
    getEmailTemplates().catch(() => ({ templates: [], transport_configured: false, placeholders: [] })),
    Promise.all(details.map((d) => (writable ? getStatusLink(d.id).catch(() => null) : Promise.resolve(null)))),
    Promise.all(details.map((d) => getEmailLog(d.id).catch(() => []))),
  ]);
```

Change the timeline render to pass the section as children:

```tsx
            details.map((detail, index) => (
              <ApplicationTimeline key={detail.id} application={detail} writable={writable}>
                <ApplicationOutreach
                  applicationId={detail.id}
                  statusLink={statusLinks[index]}
                  templates={templates.templates}
                  transportConfigured={templates.transport_configured}
                  emailLog={emailLogs[index]}
                  canSend={writable}
                />
              </ApplicationTimeline>
            ))
```

(If Phase B or C already passes other props or children to `ApplicationTimeline`, keep them and add `ApplicationOutreach` after them.)

- [ ] **Step 7: Run the checks and look at it**

```powershell
cd web; npx vitest run src/lib/email-composer.test.ts; npm run typecheck; npm run lint; npm test; cd ..
```

Expected: 4 new tests pass; everything clean.

Live, with both dev servers running:
1. As the demo, open any candidate. Expected: "Candidate communication" with the preview link and "Email the candidate"; no status link control; "Use template" fills the first name; the amber note says the account cannot send; "Copy text" copies.
2. As an admin with no SMTP configured: "Create status link" shows `/c/...`; "Use template" on Interview invitation now has no missing placeholders; no Send button (no transport); "Copy text" adds a "Copied" history line.

- [ ] **Step 8: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e13.txt`:

```
feat(web): status link, email composer, and history on the candidate page

Each application's card gains a "Candidate communication" section: a
link to preview the candidate view, the status link control for
writers, a template-based composer (send when a mail server is set up,
copy otherwise), and the last five history entries. The demo can
preview email but not send it. Checked live as the demo and as an
admin without SMTP configured.
```

```powershell
git add web/src/lib/email-composer.ts web/src/lib/email-composer.test.ts web/src/components/status-link-control.tsx web/src/components/email-composer.tsx web/src/components/application-outreach.tsx web/src/components/application-timeline.tsx "web/src/app/(app)/candidates/[id]/page.tsx"
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e13.txt
```

---

### Task 14: Email templates page

**Files:**
- Create: `web/src/components/template-editor.tsx`
- Create: `web/src/app/(app)/email-templates/page.tsx`
- Modify: `web/src/lib/nav.ts`

- [ ] **Step 1: Write the editor**

Create `web/src/components/template-editor.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { EmailTemplate } from "@/lib/domain";
import { unknownPlaceholders } from "@/lib/email-composer";

export function TemplateEditor({
  template,
  placeholders,
  editable,
}: {
  template: EmailTemplate;
  placeholders: string[];
  editable: boolean;
}) {
  const router = useRouter();
  const [name, setName] = useState(template.name);
  const [subject, setSubject] = useState(template.subject);
  const [body, setBody] = useState(template.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  if (!editable) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{template.name}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="font-medium text-slate-800">{template.subject}</p>
          <p className="whitespace-pre-line text-slate-600">{template.body}</p>
        </CardContent>
      </Card>
    );
  }

  async function save() {
    const unknown = unknownPlaceholders(`${subject}\n${body}`, placeholders);
    if (unknown.length > 0) {
      setError(`Unknown placeholder {{${unknown[0]}}}.`);
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const response = await fetch(`/api/email-templates/${template.key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, subject, body }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) {
        throw new Error(
          typeof payload?.detail === "string" ? payload.detail : `Could not save (${response.status})`,
        );
      }
      setSaved(true);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-6 text-sm">
        <Input value={name} onChange={(e) => setName(e.target.value)} aria-label="Template name" />
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
        <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={10} aria-label="Body" />
        <div className="flex items-center gap-3">
          <Button type="button" onClick={save} disabled={busy}>
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : <Save className="mr-2 h-4 w-4" aria-hidden />}
            Save
          </Button>
          {saved ? <span className="text-xs text-emerald-700">Saved.</span> : null}
          {error ? <span className="text-xs font-medium text-rose-700">{error}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Write the page**

Create `web/src/app/(app)/email-templates/page.tsx`:

```tsx
import { PageHeader } from "@/components/page-header";
import { TemplateEditor } from "@/components/template-editor";
import { Card, CardContent } from "@/components/ui/card";
import { getEmailTemplates } from "@/lib/data";
import { TEMPLATES_MANAGE, can } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function EmailTemplatesPage() {
  const [data, user] = await Promise.all([getEmailTemplates(), getUser()]);
  const editable = can(user?.role ?? null, TEMPLATES_MANAGE);

  return (
    <>
      <PageHeader
        title="Email templates"
        description="Starting points for candidate email. Each one is filled in from the application and can be edited before it goes out."
      />
      <Card className="mb-4">
        <CardContent className="p-4 text-sm text-slate-700">
          {data.transport_configured
            ? "Sending is turned on. Messages go out from the address configured on the server."
            : "No mail server is configured, so the composer offers the finished text to copy into your own inbox."}
        </CardContent>
      </Card>
      <p className="mb-6 text-xs text-slate-500">
        Placeholders you can use: {data.placeholders.map((p) => `{{${p}}}`).join(", ")}
      </p>
      <div className="max-w-3xl space-y-6">
        {data.templates.map((template) => (
          <TemplateEditor
            key={template.key}
            template={template}
            placeholders={data.placeholders}
            editable={editable}
          />
        ))}
      </div>
    </>
  );
}
```

- [ ] **Step 3: Add the nav item**

In `web/src/lib/nav.ts`, add `Mail` to the `lucide-react` import and append to the `items` of the group whose `label` is `"Admin"`:

```ts
      { href: "/email-templates", label: "Email templates", icon: Mail, hiddenFor: ["interviewer"] },
```

`hiddenFor` is Phase B's per-item role filter (`visibleGroups` applies it). Interviewers cannot reach the templates API through Phase B's interviewer gate, so the item would only lead them to an error.

- [ ] **Step 4: Check and commit**

Run: `cd web; npm run typecheck; npm run lint; npm test`
Expected: clean.

Live: open `/email-templates` as the demo (read-only cards) and as an admin (editable; saving `{{nickname}}` shows "Unknown placeholder {{nickname}}.").

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e14.txt`:

```
feat(web): email templates page under Admin

Admins and hiring managers edit the four templates in place; everyone
else, including the demo, reads them. The page states plainly whether
a mail server is configured. Unknown placeholders are caught before
the request and again by the API.
```

```powershell
git add web/src/components/template-editor.tsx "web/src/app/(app)/email-templates/page.tsx" web/src/lib/nav.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e14.txt
```

---

### Task 15: Start from an existing job, and Draft with AI

**Files:**
- Modify: `web/src/lib/job-form.ts`, `web/src/lib/job-form.test.ts`
- Create: `web/src/components/copy-from-job.tsx`
- Modify: `web/src/components/job-form.tsx`
- Modify: `web/src/app/(app)/jobs/new/page.tsx`, `web/src/app/(app)/jobs/[id]/edit/page.tsx`

- [ ] **Step 1: Write the failing tests**

Append to `web/src/lib/job-form.test.ts` (merge the new names into its existing `./job-form` import):

```ts
import {
  EMPTY_JOB,
  applyDraft,
  canRequestDraft,
  copyJobValues,
  draftRequestFrom,
  hasWrittenDescription,
} from "./job-form";
import type { Job } from "./domain";

describe("copyJobValues", () => {
  it("copies the role but starts it as a draft with no dates", () => {
    const job = {
      id: 7,
      title: "Data Engineer",
      department: "Data",
      job_overview: "Pipelines.",
      required_qualifications: "SQL",
      skills: ["SQL", "dbt"],
      status: "open",
      application_deadline: "2026-11-01T00:00:00",
      start_date: "2026-12-01T00:00:00",
    } as unknown as Job;
    const values = copyJobValues(job);
    expect(values.title).toBe("Data Engineer");
    expect(values.skills).toBe("SQL, dbt");
    expect(values.status).toBe("draft");
    expect(values.application_deadline).toBe("");
    expect(values.start_date).toBe("");
  });
});

describe("AI draft helpers", () => {
  const values = { ...EMPTY_JOB, title: " Data Engineer ", department: "Data", skills: "SQL, , dbt" };

  it("sends only the structured fields", () => {
    expect(draftRequestFrom(values)).toEqual({
      title: "Data Engineer",
      department: "Data",
      experience_level: "mid",
      location_type: "on_site",
      skills: ["SQL", "dbt"],
    });
  });

  it("needs a title", () => {
    expect(canRequestDraft(values)).toBe(true);
    expect(canRequestDraft({ ...values, title: "  " })).toBe(false);
  });

  it("knows when applying would overwrite text", () => {
    expect(hasWrittenDescription(values)).toBe(false);
    expect(hasWrittenDescription({ ...values, required_qualifications: "SQL" })).toBe(true);
  });

  it("applies the draft to the two description fields only", () => {
    const next = applyDraft(values, { job_overview: "O", required_qualifications: "Q" });
    expect(next.job_overview).toBe("O");
    expect(next.required_qualifications).toBe("Q");
    expect(next.title).toBe(values.title);
  });
});
```

Run: `cd web; npx vitest run src/lib/job-form.test.ts`
Expected: FAIL, the new names are not exported.

- [ ] **Step 2: Add the helpers**

Append to `web/src/lib/job-form.ts`:

```ts
/**
 * "Start from an existing job": the same role, as a new draft. Dates are
 * cleared because they almost never carry over.
 */
export function copyJobValues(job: Job): JobFormValues {
  return { ...jobToFormValues(job), status: "draft", application_deadline: "", start_date: "" };
}

export interface DescriptionDraft {
  job_overview: string;
  required_qualifications: string;
}

/** The only fields sent for an AI draft. No free text, no candidate data. */
export function draftRequestFrom(values: JobFormValues) {
  return {
    title: values.title.trim(),
    department: values.department.trim() || null,
    experience_level: values.experience_level || null,
    location_type: values.location_type || null,
    skills: values.skills
      .split(",")
      .map((skill) => skill.trim())
      .filter(Boolean),
  };
}

export function canRequestDraft(values: JobFormValues): boolean {
  return values.title.trim().length > 0;
}

export function hasWrittenDescription(values: JobFormValues): boolean {
  return Boolean(values.job_overview.trim() || values.required_qualifications.trim());
}

export function applyDraft(values: JobFormValues, draft: DescriptionDraft): JobFormValues {
  return {
    ...values,
    job_overview: draft.job_overview,
    required_qualifications: draft.required_qualifications,
  };
}
```

Run: `cd web; npx vitest run src/lib/job-form.test.ts`
Expected: all pass.

- [ ] **Step 3: Write the picker**

Create `web/src/components/copy-from-job.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";

/**
 * "Start from an existing job." A native select on purpose: it is a one-shot
 * choice that navigates, and the URL (`/jobs/new?from=7`) carries it.
 */
export function CopyFromJob({
  jobs,
  selected,
}: {
  jobs: { id: number; title: string; department: string }[];
  selected: string;
}) {
  const router = useRouter();
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3 text-sm">
      <label htmlFor="copy-from-job" className="font-medium text-slate-700">
        Start from an existing job
      </label>
      <select
        id="copy-from-job"
        value={selected}
        onChange={(e) => router.push(e.target.value ? `/jobs/new?from=${e.target.value}` : "/jobs/new")}
        className="h-9 max-w-md flex-1 rounded-md border border-slate-200 bg-white px-2"
      >
        <option value="">Blank job</option>
        {jobs.map((job) => (
          <option key={job.id} value={String(job.id)}>
            {job.title}
            {job.department ? ` (${job.department})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
```

- [ ] **Step 4: Add "Draft with AI" to the form**

In `web/src/components/job-form.tsx`:

1. Add `Sparkles` to the `lucide-react` import, and add `applyDraft`, `canRequestDraft`, `draftRequestFrom`, `hasWrittenDescription`, and `type DescriptionDraft` to the `@/lib/job-form` import.
2. Add `canDraft?: boolean` to the props (default `false`) next to `initial` and `jobId`.
3. Below the existing `useState` calls, add:

```tsx
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [pendingDraft, setPendingDraft] = useState<DescriptionDraft | null>(null);
  const [drafted, setDrafted] = useState(false);

  async function requestDraft() {
    if (!canRequestDraft(values)) {
      setErrors((current) => ({ ...current, title: "Add a title first. The draft is written from it." }));
      return;
    }
    setDrafting(true);
    setDraftError(null);
    try {
      const response = await fetch("/api/job-drafts/description", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draftRequestFrom(values)),
      });
      const payload = (await response.json().catch(() => null)) as
        | (DescriptionDraft & { detail?: unknown })
        | null;
      if (!response.ok || !payload) {
        throw new Error(readDetail(payload) || `Could not draft a description (${response.status})`);
      }
      const draft = {
        job_overview: payload.job_overview,
        required_qualifications: payload.required_qualifications,
      };
      if (hasWrittenDescription(values)) {
        setPendingDraft(draft);
      } else {
        setValues((current) => applyDraft(current, draft));
        setDrafted(true);
      }
    } catch (err) {
      setDraftError((err as Error).message);
    } finally {
      setDrafting(false);
    }
  }
```

4. Directly above `<Field label="Overview" ...>`, insert:

```tsx
          {canDraft ? (
            <div className="space-y-2 rounded-md border border-indigo-100 bg-indigo-50/50 p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-slate-600">
                  Draft the overview and qualifications from the title, department, level, and
                  skills above. Only those fields are sent. No candidate data is included.
                </p>
                <Button type="button" size="sm" variant="outline" onClick={requestDraft} disabled={drafting}>
                  {drafting ? (
                    <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden />
                  ) : (
                    <Sparkles className="mr-1 h-3.5 w-3.5" aria-hidden />
                  )}
                  Draft with AI
                </Button>
              </div>
              {pendingDraft ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-slate-700">
                    Replace the overview and qualifications you have written?
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => {
                      setValues((current) => applyDraft(current, pendingDraft));
                      setPendingDraft(null);
                      setDrafted(true);
                    }}
                  >
                    Replace
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => setPendingDraft(null)}>
                    Keep mine
                  </Button>
                </div>
              ) : null}
              {drafted ? (
                <p className="text-xs text-indigo-700">Drafted by AI. Review and edit before saving.</p>
              ) : null}
              {draftError ? <p className="text-xs font-medium text-rose-700">{draftError}</p> : null}
            </div>
          ) : null}
```

- [ ] **Step 5: Wire the pages**

Replace the body of `web/src/app/(app)/jobs/new/page.tsx` with:

```tsx
import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { CopyFromJob } from "@/components/copy-from-job";
import { JobForm } from "@/components/job-form";
import { PageHeader } from "@/components/page-header";
import { getJob, listJobs } from "@/lib/data";
import { copyJobValues } from "@/lib/job-form";
import { JOBS_WRITE, can } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * Create a job, blank or copied from an existing one (`?from=<id>`).
 *
 * The redirect is a courtesy; the backend's permission gate is what
 * actually refuses the write.
 */
export default async function NewJobPage({ searchParams }: PageProps<"/jobs/new">) {
  const user = await getUser();
  if (!can(user?.role ?? null, JOBS_WRITE)) redirect("/jobs");

  const { from } = await searchParams;
  const fromId = typeof from === "string" && /^\d+$/.test(from) ? from : null;
  const [source, jobs] = await Promise.all([
    fromId ? getJob(fromId) : Promise.resolve(null),
    listJobs(1, 100),
  ]);

  return (
    <>
      <Link
        href="/jobs"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        All jobs
      </Link>

      <PageHeader
        title="New job"
        description="Open roles are matched against every candidate in the database."
      />

      <div className="max-w-3xl">
        <CopyFromJob
          jobs={jobs.results.map((job) => ({ id: job.id, title: job.title, department: job.department ?? "" }))}
          selected={source ? String(source.id) : ""}
        />
        <JobForm
          key={source ? `from-${source.id}` : "blank"}
          initial={source ? copyJobValues(source) : undefined}
          canDraft
        />
      </div>
    </>
  );
}
```

In `web/src/app/(app)/jobs/[id]/edit/page.tsx`, pass `canDraft` to the form: `<JobForm initial={jobToFormValues(job)} jobId={job.id} canDraft />` (the page already redirects anyone who cannot write jobs).

- [ ] **Step 6: Check it**

Run: `cd web; npm run typecheck; npm run lint; npm test`
Expected: clean, job-form tests pass.

Live as an admin: `/jobs/new`, choose a job in "Start from an existing job" (fields fill, status is Draft, dates empty); clear the overview and qualifications, click "Draft with AI" (with the dev provider chain reachable: both fields fill and the "Drafted by AI" note shows; with it unreachable: the 503 message shows and nothing changes); type into Overview and draft again (the Replace / Keep mine choice appears).

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e15.txt`:

```
feat(web): start a job from an existing one, and draft its description with AI

/jobs/new?from=<id> copies the role as a draft with dates cleared. The
form's "Draft with AI" sends only the structured fields, never
overwrites typed text without asking, and labels the result as an AI
draft to review. Checked live with the provider chain up and down.
```

```powershell
git add web/src/lib/job-form.ts web/src/lib/job-form.test.ts web/src/components/copy-from-job.tsx web/src/components/job-form.tsx "web/src/app/(app)/jobs/new/page.tsx" "web/src/app/(app)/jobs/[id]/edit/page.tsx"
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e15.txt
```

---

### Task 16: The stage editor

**Files:**
- Create: `web/src/lib/stage-editor.ts`, `web/src/lib/stage-editor.test.ts`
- Create: `web/src/components/stage-editor.tsx`
- Create: `web/src/app/(app)/jobs/[id]/stages/page.tsx`
- Modify: `web/src/app/(app)/jobs/[id]/page.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/stage-editor.test.ts`:

```ts
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
```

Run: `cd web; npx vitest run src/lib/stage-editor.test.ts`
Expected: FAIL, module not found.

- [ ] **Step 2: Write the helpers**

Create `web/src/lib/stage-editor.ts`:

```ts
/**
 * The stage editor's rules, pure and tested.
 *
 * Which stages may move comes from the API (`movable`), never from keys
 * hard-coded here, so the server's pinning rule is the only one.
 */
import type { PipelineUpdate, StageOut } from "./domain";

export interface EditableStage {
  key: string;
  name: string;
  description: string;
  enabled: boolean;
  kind: string;
  custom: boolean;
  movable: boolean;
}

export interface PendingStage {
  name: string;
  description: string;
  afterKey: string | null;
}

const FIRST_STAGE = "resume_submitted";

export function toEditable(stages: StageOut[]): EditableStage[] {
  return [...stages]
    .sort((a, b) => a.position - b.position)
    .map((s) => ({
      key: s.key,
      name: s.name,
      description: s.description ?? "",
      enabled: s.enabled,
      kind: s.kind,
      custom: s.custom ?? false,
      movable: s.movable ?? false,
    }));
}

export function moveStage(stages: EditableStage[], key: string, direction: -1 | 1): EditableStage[] {
  const index = stages.findIndex((s) => s.key === key);
  const target = index + direction;
  if (index === -1 || target < 0 || target >= stages.length) return stages;
  if (!stages[index].movable || !stages[target].movable) return stages;
  const next = [...stages];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function placementOptions(stages: EditableStage[]): { key: string; name: string }[] {
  return stages
    .filter((s) => s.key === FIRST_STAGE || s.movable)
    .map((s) => ({ key: s.key, name: s.name }));
}

export function buildUpdate(
  original: EditableStage[],
  edited: EditableStage[],
  added: PendingStage[],
  removed: string[],
): PipelineUpdate {
  const before = new Map(original.map((s) => [s.key, s]));
  const stages = edited
    .filter((s) => {
      const o = before.get(s.key);
      return o && (o.enabled !== s.enabled || o.name !== s.name || o.description !== s.description);
    })
    .map((s) => ({
      key: s.key,
      enabled: s.enabled,
      name: s.name.trim(),
      description: s.description.trim(),
    }));

  const originalOrder = original.filter((s) => s.movable && !removed.includes(s.key)).map((s) => s.key);
  const editedOrder = edited.filter((s) => s.movable).map((s) => s.key);
  const order = editedOrder.join("|") === originalOrder.join("|") ? null : editedOrder;

  return {
    stages,
    order,
    add: added.map((a) => ({
      name: a.name.trim(),
      description: a.description.trim() || null,
      after_key: a.afterKey,
    })),
    remove: removed,
  };
}

export function validateEdits(edited: EditableStage[], added: PendingStage[]): string | null {
  for (const s of edited) {
    if (!s.name.trim()) return "Every stage needs a name.";
    if (s.name.trim().length > 100) return "Stage names must be 100 characters or fewer.";
  }
  if (edited.some((s) => s.key === FIRST_STAGE && !s.enabled)) {
    return "Resume submitted cannot be turned off.";
  }
  if (added.some((a) => !a.name.trim() || a.name.trim().length > 100)) {
    return "New stage names must be between 1 and 100 characters.";
  }
  return null;
}
```

Run: `cd web; npx vitest run src/lib/stage-editor.test.ts`
Expected: 8 passed.

- [ ] **Step 3: Write the editor component**

Create `web/src/components/stage-editor.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, Loader2, Plus, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { StageOut } from "@/lib/domain";
import {
  buildUpdate,
  moveStage,
  placementOptions,
  toEditable,
  validateEdits,
  type EditableStage,
  type PendingStage,
} from "@/lib/stage-editor";

/**
 * Turn stages on and off, rename them, edit what candidates read, reorder
 * the interview stages, and add or remove stages this job added. Saved in
 * one request; the server refuses anything that would strand a candidate.
 */
export function StageEditor({ jobId, stages }: { jobId: number; stages: StageOut[] }) {
  const router = useRouter();
  const original = useMemo(() => toEditable(stages), [stages]);
  const [edited, setEdited] = useState<EditableStage[]>(original);
  const [added, setAdded] = useState<PendingStage[]>([]);
  const [removed, setRemoved] = useState<string[]>([]);
  const [draft, setDraft] = useState<PendingStage>({ name: "", description: "", afterKey: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rounds = edited.filter((s) => s.kind === "round");
  const outcomes = edited.filter((s) => s.kind === "outcome");

  function patch(key: string, change: Partial<EditableStage>) {
    setEdited((current) => current.map((s) => (s.key === key ? { ...s, ...change } : s)));
  }

  function remove(key: string) {
    setEdited((current) => current.filter((s) => s.key !== key));
    setRemoved((current) => [...current, key]);
  }

  function addPending() {
    if (!draft.name.trim()) {
      setError("Give the new stage a name.");
      return;
    }
    setAdded((current) => [...current, { ...draft, name: draft.name.trim() }]);
    setDraft({ name: "", description: "", afterKey: draft.afterKey });
    setError(null);
  }

  async function save() {
    const problem = validateEdits(edited, added);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${jobId}/pipeline`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildUpdate(original, edited, added, removed)),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
      if (!response.ok) {
        throw new Error(
          typeof payload?.detail === "string" ? payload.detail : `Could not save the stages (${response.status})`,
        );
      }
      router.push(`/jobs/${jobId}`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <ol className="space-y-3">
        {rounds.map((stage, index) => (
          <li key={stage.key} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-6 text-xs text-slate-400">{index + 1}</span>
              <Input
                value={stage.name}
                onChange={(e) => patch(stage.key, { name: e.target.value })}
                aria-label={`Name of stage ${index + 1}`}
                className="max-w-xs"
              />
              <label className="flex items-center gap-1.5 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={stage.enabled}
                  disabled={stage.key === "resume_submitted"}
                  onChange={(e) => patch(stage.key, { enabled: e.target.checked })}
                />
                In use
              </label>
              <span className="ml-auto flex gap-1">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-label={`Move ${stage.name} up`}
                  disabled={!stage.movable}
                  onClick={() => setEdited((current) => moveStage(current, stage.key, -1))}
                >
                  <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-label={`Move ${stage.name} down`}
                  disabled={!stage.movable}
                  onClick={() => setEdited((current) => moveStage(current, stage.key, 1))}
                >
                  <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                </Button>
                {stage.custom ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    aria-label={`Remove ${stage.name}`}
                    onClick={() => remove(stage.key)}
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                ) : null}
              </span>
            </div>
            <Textarea
              value={stage.description}
              onChange={(e) => patch(stage.key, { description: e.target.value })}
              rows={2}
              className="mt-2 text-sm"
              aria-label={`What candidates read about ${stage.name}`}
              placeholder="What candidates read about this stage on their status page."
            />
          </li>
        ))}
      </ol>

      <p className="text-xs text-slate-500">
        Resume submitted stays first and the offer stages stay last. Outcomes:{" "}
        {outcomes.map((s) => s.name).join(" and ")}.
      </p>

      <section className="space-y-2 rounded-lg border border-dashed border-slate-300 p-4">
        <h2 className="text-sm font-medium text-slate-800">Add a stage</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="Portfolio review"
            aria-label="New stage name"
            className="max-w-xs"
          />
          <select
            value={draft.afterKey ?? ""}
            onChange={(e) => setDraft({ ...draft, afterKey: e.target.value || null })}
            className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm"
            aria-label="Place the new stage after"
          >
            <option value="">Just before the offer</option>
            {placementOptions(edited).map((option) => (
              <option key={option.key} value={option.key}>
                After {option.name}
              </option>
            ))}
          </select>
          <Button type="button" size="sm" variant="outline" onClick={addPending}>
            <Plus className="mr-1 h-3.5 w-3.5" aria-hidden />
            Add
          </Button>
        </div>
        {added.length > 0 ? (
          <ul className="text-xs text-slate-600">
            {added.map((a, i) => (
              <li key={`${a.name}-${i}`}>Will add: {a.name}</li>
            ))}
          </ul>
        ) : null}
      </section>

      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
      <Button type="button" onClick={save} disabled={busy}>
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : <Save className="mr-2 h-4 w-4" aria-hidden />}
        Save stages
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Write the page and link it from the job page**

Create `web/src/app/(app)/jobs/[id]/stages/page.tsx`:

```tsx
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { StageEditor } from "@/components/stage-editor";
import { getJob, getJobPipeline } from "@/lib/data";
import { JOBS_WRITE, can } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function EditStagesPage({ params }: PageProps<"/jobs/[id]/stages">) {
  const { id } = await params;
  const user = await getUser();
  if (!can(user?.role ?? null, JOBS_WRITE)) redirect(`/jobs/${id}`);

  const [job, pipeline] = await Promise.all([getJob(id), getJobPipeline(id)]);
  if (!job || !pipeline) notFound();

  return (
    <>
      <Link
        href={`/jobs/${job.id}`}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to {job.title}
      </Link>
      <PageHeader
        title="Edit stages"
        description="Turn off rounds this job does not run, rename them, reorder interviews, or add your own."
      />
      <div className="max-w-3xl">
        <StageEditor jobId={job.id} stages={pipeline.stages} />
      </div>
    </>
  );
}
```

In `web/src/app/(app)/jobs/[id]/page.tsx`:

1. Add imports: `import { JOBS_WRITE, can } from "@/lib/permissions";` and `getUser` from `@/lib/session` (merge with the existing session import).
2. Fetch the user alongside the job: if the page has `const [job, writable] = await Promise.all([getJob(id), canWrite()]);`, change it to `const [job, writable, user] = await Promise.all([getJob(id), canWrite(), getUser()]);` and add `const canEditStages = can(user?.role ?? null, JOBS_WRITE);` after the `notFound()` check.
3. Replace the Pipeline card's header with:

```tsx
            <CardHeader className="flex flex-row items-baseline justify-between gap-2">
              <CardTitle className="text-base">Pipeline</CardTitle>
              {canEditStages ? (
                <Link href={`/jobs/${job.id}/stages`} className="text-xs font-medium text-indigo-700 hover:underline">
                  Edit stages
                </Link>
              ) : null}
            </CardHeader>
```

- [ ] **Step 5: Check it**

Run: `cd web; npm run typecheck; npm run lint; npm test`
Expected: clean; 8 stage-editor tests pass.

Live as an admin on a seeded job: open "Edit stages", turn off Case study, move Problem solving up, add "Portfolio review" just before the offer, save. Expected: back on the job page, the board shows the new column order and the new column; a candidate page for that job shows the new stage in the timeline. Then try turning off Hiring manager review while a candidate is there. Expected: the "Move them first" message, nothing saved. As the demo, the "Edit stages" link is absent and `/jobs/<id>/stages` redirects to the job.

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-e16.txt`:

```
feat(web): Edit stages screen for job writers

Closes the Phase A deferral. Writers turn rounds on and off, rename
them, edit the description candidates read, reorder interview stages,
and add or remove their own stages, all saved in one request. Which
stages can move comes from the API, so the pinning rule lives in one
place. Checked live as an admin and the demo, including the refusal
when a candidate is at a stage being turned off.
```

```powershell
git add web/src/lib/stage-editor.ts web/src/lib/stage-editor.test.ts web/src/components/stage-editor.tsx "web/src/app/(app)/jobs/[id]/stages/page.tsx" "web/src/app/(app)/jobs/[id]/page.tsx"
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-e16.txt
```

---

### Task 17: Full verification, PR, deploy, and prod follow-ups

**Files:** none new.

- [ ] **Step 1: Backend, the way CI does it**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
$env:OLLAMA_BASE_URL = "http://localhost:1"
poetry run ruff check backend --select E9,F63,F7,F82 --exclude backend/tests
poetry run python scripts/export_openapi.py --check
poetry run pytest -q -p no:cacheprovider
```

Expected: ruff clean, OpenAPI in sync, suite green (the scratch-database pass already ran in Task 10; rerun it if anything backend changed since).

- [ ] **Step 2: Web**

```powershell
cd web; npm run typecheck; npm run lint; npm test; npm run build; cd ..
```

Then with both dev servers up: `cd web; $env:E2E_BASE_URL = "http://localhost:3000"; npx playwright test`. If anything fails, rerun against `https://recruitiq.io` (minus the new public-status spec, which is not deployed yet) and restart `next dev` before blaming the change.

Expected: clean build; all e2e specs pass.

- [ ] **Step 3: Grep for em dashes in new user-visible text**

```powershell
Select-String -Path backend/alembic/versions/f7b1d4e5a6c7_public_status_and_email.py, backend/services/*.py, backend/routers/*.py, web/src/components/*.tsx, "web/src/app/(public)/c/[token]/page.tsx" -Pattern ([char]0x2014)
```

Expected: no matches.

- [ ] **Step 4: Push and open the PR**

Write `C:\Users\seaso\AppData\Local\Temp\claude\pr-e.md`:

```
## What

ATS Phase E (spec docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md, section 8):

- Candidate status page at /c/<token>: first name, job, department, status, and the stage list with candidate-facing descriptions. No navigation, no session cookie, noindex, no Referer. Staff create, replace, and turn off links; staff and the demo can preview the same view per application.
- Email: four editable templates (interview invitation, resume request, polite close, offer), a composer on the candidate page, SMTP sending when configured and "copy the text" when not, and a history of every send or copy.
- Job form: "Start from an existing job" and "Draft with AI" (structured fields only, scrubbed, through the provider chain).
- Edit stages: turn off, rename, describe, reorder interview stages, add and remove custom stages. Closes the Phase A deferral.

## Why

Candidates can see where they stand without anyone sending an update, the team can send the routine emails from where they already work, and each job can run the process it actually runs.

## Notable decisions

- Resume submitted stays first and the two offer stages stay last; only interview stages move, and new stages land among them.
- Transitions now pass over rounds that already happened instead of re-opening them (needed once order can change). Regression tests included.
- The app shell moved into an (app) route group so the public page renders on its own. URLs are unchanged.
- The new routers are mounted above the pipeline router, because POST /api/applications/{id}/{action} would otherwise swallow /status-link and /emails.

## Verified

- Backend: test_custom_stages (16), test_status_links (9, including the pinned no-leak test at service and HTTP level), test_email (16), test_job_drafts (4); full suite on a scratch database built from migrations alone.
- Migration: upgrade, downgrade, upgrade on a scratch database.
- Web: typecheck, lint, vitest, next build, Playwright including a check that a status link sets no session cookie.
- Live: public page in a private window, candidate-view preview, composer as the demo and as an admin, stage editor including the in-use refusal.

## Prod follow-up (manual, Sean)

- Add to /etc/recruitiq/env: PUBLIC_APP_URL=https://recruitiq.io, then `systemctl restart recruitiq-api`. Without it, status links in emails point at localhost.
- Optional: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM, SMTP_STARTTLS in the same file to turn sending on. Until then the composer offers copy instead.
- Optional: an nginx limit_req on /c/ and /api/public/ to rate-limit token guessing (tokens are 32 random characters, so this is belt and braces).
```

```powershell
git push -u origin ats-candidate-facing
gh pr create --base main --title "feat: candidate status page, email templates, job drafts, and stage editor (ATS Phase E)" --body-file C:\Users\seaso\AppData\Local\Temp\claude\pr-e.md
gh pr checks --watch
```

- [ ] **Step 5: Merge and deploy**

```powershell
gh pr merge --merge --delete-branch
git fetch origin
```

Deploy with the Bash tool:

```bash
ssh root@157.245.233.229 "free -h; pgrep -fa '[d]eploy.sh' || echo no-deploy-running"
ssh root@157.245.233.229 "/opt/recruitiq/app/scripts/deploy.sh"
```

Expected: at least 500M available and no other deploy running first; `==> deployed <sha>` matching `git rev-parse --short origin/main`.

- [ ] **Step 6: Smoke test prod**

```bash
curl -sS -o /dev/null -w "home %{http_code}\n" https://recruitiq.io/
ssh root@157.245.233.229 'curl -sS http://127.0.0.1:8020/health; echo; curl -sS http://127.0.0.1:8020/api/email-templates | head -c 200; echo; curl -sS -o /dev/null -w "public-404 %{http_code}\n" http://127.0.0.1:8020/api/public/status/not-a-real-token-000000'
curl -sS -o /dev/null -w "status-page %{http_code}\n" https://recruitiq.io/c/not-a-real-token-000000
curl -sS -D - -o /dev/null https://recruitiq.io/c/not-a-real-token-000000 | grep -i "set-cookie" || echo "no set-cookie on /c/"
J=$(ssh root@157.245.233.229 'curl -s "http://127.0.0.1:8020/api/jobs/?page_size=1" | grep -o "\"id\":[0-9]*" | head -1 | cut -d: -f2'); curl -sS -o /dev/null -w "job-stages-redirect %{http_code}\n" "https://recruitiq.io/jobs/$J/stages"
```

Expected: home 200; health ok; the templates JSON starts with `{"templates":[{"key":"interview_invite"`; public-404 404; status-page 200 (the "not active" page); "no set-cookie on /c/"; the stages page answers 307 or 200 for the demo (redirect back to the job).

- [ ] **Step 7: Report the manual follow-ups**

Tell Sean, in the final report, the exact env lines from the PR body. Do not edit `/etc/recruitiq/env` from this session: it holds secrets and SMTP credentials are his to choose.

---

## Self-review

**Spec coverage (section 8 Phase E, section 5 rows marked E, the Phase A deferral):**
- Public status page on `job_applications.public_token` showing only first name, job title, department, stage timeline, and descriptions: Tasks 4 to 6 (backend), 12 (page). Pinned test at service and HTTP level (Task 5 `test_public_view_shows_only_the_allowlist`, Task 6 `test_public_payload_over_http_carries_no_internal_details`) checks the exact key set plus the absence of score, email, phone, last name, notes, internal stage notes, interviewer name and email, hiring manager, and recruiter. Covered.
- Tokens unguessable, regenerable, revocable, uniform 404: Tasks 5 and 6. Covered.
- Email templates (interview invite, resume request, polite close, offer) with a log: Tasks 4, 7, 8, 13, 14. SMTP configured from `/etc/recruitiq/env` with a "no transport configured" state that still lets you copy the text: Task 7 settings, Task 8 409, Task 13 composer. Demo cannot send: Task 8 permissions test and the composer's `sendState`. No real addresses in templates or seed. Covered.
- "Start from an existing job": Task 15. Covered.
- Optional AI job description draft through the existing provider chain and de-identification rules, admin and hiring manager only, prompt with no candidate data: Task 9 and Task 15. Covered.
- Custom stages and reordering, plus the admin "Edit stages" control deferred from Phase A: Tasks 1 to 3 (backend), 16 (UI). Covered, with the mid-flight rules made explicit in Task 2.
- Read-only demo keeps working on every new screen: candidate-view preview, email preview, templates page (read-only), job page without "Edit stages". Covered.

**Placeholder scan:** no "TBD" or "TODO". Two steps deliberately describe a move rather than show final code, because the code they move is whatever Phases B to D left behind: Task 12 Step 4 (the shell JSX moved verbatim into `(app)/layout.tsx`) and Task 13 Step 5 (`{children}` placed after anything B or C added to the timeline). Both say exactly what to move and where, and both are followed by a typecheck.

**Type consistency:** `StageOut.custom`/`movable` (Task 3) match `toEditable` (Task 16). `PipelineUpdateRequest` fields `stages`, `order`, `add`, `remove` and `NewStage.after_key` (Task 3) match `buildUpdate` (Task 16). `StatusLinkOut` `active`/`path`/`created_at` (Task 5) match `StatusLinkControl` (Task 13) and the lifecycle test (Task 6). `PublicStatus` keys (Task 5) match `PublicStatusView` and `public-status.ts` (Task 12). `EmailPreview.missing`/`to_address`/`transport_configured` and `EmailLogOut.sent_by_name` (Task 8) match the composer, outreach section, and tests. `EmailTemplatesResponse.placeholders` (Task 8) matches the templates page (Task 14). `JobDescriptionDraft` fields (Task 9) match `DescriptionDraft` and `applyDraft` (Task 15). Permission names `JOBS_WRITE`, `PIPELINE_MOVE`, `TEMPLATES_MANAGE` match the contract in both backend and web.
