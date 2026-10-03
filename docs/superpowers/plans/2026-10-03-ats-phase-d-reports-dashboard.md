# ATS Phase D: Reports and Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give recruiters a Reports page and a working dashboard built entirely from the stage history: a funnel (ever reached vs here now), median time in stage, a "no movement in 7+ days" list, pending feedback, source mix, hires and rejections by quarter, an activity feed, and two assistant tools that answer "where is everyone for this job" and "who is at this stage".

**Architecture:** One read-only service module (`backend/services/reports_service.py`) owns every number. Each public function is a single SQL query over `application_stages` joined to `pipeline_stages` and `job_applications`, takes an explicit `now`, and takes a `Scope` (one job and/or the candidates the viewer may see). A new router serves two GETs: `/api/reports/dashboard` (every viewer, scoped) and `/api/reports/summary` (REPORTS_VIEW holders plus the read-only demo). The assistant gets two thin tools over the same service. The seed script learns to lay out realistic, deterministic stage timestamps so time-in-stage and the attention list have something honest to show.

**Tech Stack:** FastAPI + SQLAlchemy 2 (Postgres `percentile_cont`), pytest with the transactional fixtures in `backend/tests/conftest.py`, Next.js 16 App Router + Tailwind + Vitest, Playwright for the live journey.

**Spec:** `docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md`, section 8 Phase D, the section 5 rows marked D (Dashboard, Reports, Assistant), section 7 terminology.

**Prerequisites:** Phases A, B, and C merged to `main`. This plan only *uses* names Phases B and C define (see "Assumptions about Phases B and C" below); Task 1 verifies they exist before any code is written.

---

## Conventions for every task

- Work on branch `ats-reports-dashboard`, created from `origin/main`.
- Backend tests run from the repo root against the dev database:
  ```powershell
  $env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
  $env:OLLAMA_BASE_URL = "http://localhost:1"
  poetry run pytest backend/tests/test_reports.py -q
  ```
- Web tests run from `web/`: `npm test`, `npm run typecheck`, `npm run lint`.
- Commit with `git commit -F <file>` (never `-m` with a PowerShell here-string). Commit message files go in the session scratchpad; the paths below use `C:\Users\seaso\AppData\Local\Temp\claude\` as a stand-in. No attribution trailers of any kind.
- No em or en dashes in any string a user can read, including tool notes and tool descriptions the assistant can repeat. American spelling. Spec section 7 terms: "No movement in 7+ days" (never "stale"), "Hired" (never "joined"), "Offer declined".
- New endpoints are plain `def`, never `async def` (they use `Depends(get_db)`).
- Every service function takes `now` as a parameter. Only routers and tools call `datetime.utcnow()`. Tests always pass a fixed instant.
- Every service function takes a `Scope`. A query that ignores the scope would show an interviewer candidates they are not assigned to.
- Reset or fixture data shared between route tests is committed, not just flushed (Phase A lesson: a route that rolls back reverts to the last commit and silently drops flushed fixture rows).
- Phase D adds no mutating routes, so `ROUTE_PERMISSIONS` is untouched. No schema change, so no migration.

## Assumptions about Phases B and C

Phases B and C were planned in parallel with this one. Everything below comes from the shared contract; Task 1 checks each item and stops the work if one is missing.

| # | Assumed name | Owner | Used for |
|---|---|---|---|
| 1 | `backend.utils.permissions.REPORTS_VIEW` and `can(role, permission) -> bool` | B | Gate on `/api/reports/summary` |
| 2 | `backend.utils.auth.ROLE_DEMO`, `ROLE_INTERVIEWER` | B | Demo may read Reports; interviewers see only their own pending feedback |
| 3 | `backend.services.access_service.visible_candidate_ids(db, user) -> Optional[set[str]]`: `None` for admin, hiring manager, hiring team, and demo; for an interviewer, the candidates on applications where they have an `interviews` row | B | `Scope.candidate_ids` on every query |
| 4 | ORM models `Interview(id, application_stage_id, interviewer_id, assignment_source, created_at)` and `Feedback(id, interview_id, rating, recommendation, notes, submitted_at)` in `backend/models/models.py`; `User.name` column | B (spec 3.1, 3.2) | Pending feedback list, actor names in the activity feed |
| 5 | `build_assistant_tools(db, user=None)` | B (score visibility in the assistant) | The new tools scope to the viewer. If B left the signature as `build_assistant_tools(db)`, Task 9 Step 4 adds the parameter |
| 6 | `web/src/lib/permissions.ts` exporting `can(role, permission)` and `REPORTS_VIEW`; `web/src/lib/session.ts` `Role` union including `hiring_manager`, `hiring_team`, `interviewer` | B | Hide Reports from interviewers in the UI |
| 7 | `web/src/lib/nav.ts` `NAV_GROUPS` with an `Admin` group; nav items shaped `{ href, label, icon, ... }`; `web/src/components/sidebar.tsx` knows the viewer's role | B | Reports nav item (Phase B settled this: items take `hiddenFor?: Role[]`, filtered by `visibleGroups`; Task 13 uses it) |
| 8 | Backend `GET /api/candidates/export.csv` accepting `job_id`, and a browser-reachable Next route handler at `/api/candidates/export` that forwards the query string with the session token | C | "Export candidates (CSV)" on Reports; D writes no second exporter |

Not assumed: B's seed data. If B seeds interviewers and interviews, the dashboard's pending feedback list shows them; if not, the list renders its empty state. Nothing in D's tests depends on B's seed.

## File structure

| File | Responsibility |
|---|---|
| `backend/services/reports_service.py` | Create: `Scope`, every report query, the dashboard and reports bundles, stage resolution and per-stage listings for the assistant |
| `backend/models/reports.py` | Create: Pydantic response models |
| `backend/routers/reports.py` | Create: `GET /api/reports/dashboard`, `GET /api/reports/summary` |
| `backend/main.py` | Modify: mount the router |
| `backend/services/assistant_tools.py` | Modify: `get_job_pipeline` and `find_candidates_at_stage` tools, two visitor-safe note helpers, `list_pipeline` description points at them |
| `evals/assistant_golden.json` | Modify: two golden cases (the golden test fails if a tool has none) |
| `backend/tests/test_assistant_golden.py` | Modify: new notes join the hygiene list |
| `backend/tests/test_reports.py` | Create: service tests on a fixed timeline, route tests, tool tests |
| `scripts/seed_demo.py` | Modify: `stage_timeline` (pure), `_spread_stage_timeline`, call it from `seed_pipeline`; stop reassigning statuses of candidates already on a pipeline |
| `backend/tests/test_seed_demo.py` | Modify: tests for the timeline layout and the spread's idempotency |
| `openapi.json`, `web/src/lib/schema.d.ts` | Regenerated |
| `web/src/lib/domain.ts` | Modify: type aliases |
| `web/src/lib/data.ts` | Modify: `getDashboard`, `getReport`; remove the now-unused `countByStage` |
| `web/src/lib/reports.ts` + `reports.test.ts` | Create: pure wording and visibility helpers |
| `web/src/components/stage-funnel.tsx` | Create: ever-reached vs here-now bars |
| `web/src/components/attention-list.tsx` | Create: no movement and pending feedback |
| `web/src/components/activity-feed.tsx` | Create: recent pipeline moves |
| `web/src/app/page.tsx` | Modify: dashboard uses the new endpoint; keeps three tiles, Top skills, Recently added |
| `web/src/app/reports/page.tsx` | Create: the Reports page |
| `web/src/lib/nav.ts` | Modify: Reports item at the top of Admin |
| `web/e2e/reports.spec.ts` | Create: demo walk through Reports and the new dashboard cards |

---

### Task 1: Branch and verify the Phase B and C names exist

**Files:** none changed.

- [ ] **Step 1: Create the branch**

```powershell
git fetch origin
git switch -c ats-reports-dashboard origin/main
```

- [ ] **Step 2: Check every assumed name**

```powershell
Select-String -Path backend/utils/permissions.py -Pattern '^REPORTS_VIEW\s*=', '^def can\('
Select-String -Path backend/utils/auth.py -Pattern '^ROLE_DEMO\s*=', '^ROLE_INTERVIEWER\s*='
Select-String -Path backend/services/access_service.py -Pattern '^def visible_candidate_ids\('
Select-String -Path backend/models/models.py -Pattern '^class Interview\(Base\)', '^class Feedback\(Base\)', '^\s+name = Column'
Select-String -Path backend/services/assistant_tools.py -Pattern '^def build_assistant_tools\('
Select-String -Path web/src/lib/permissions.ts -Pattern 'REPORTS_VIEW', 'export function can'
Select-String -Path web/src/lib/nav.ts -Pattern 'NAV_GROUPS', 'Admin'
Select-String -Path backend/routers/candidates.py -Pattern 'export\.csv'
Get-ChildItem -LiteralPath web/src/app/api/candidates/export -ErrorAction SilentlyContinue
```

Expected: every pattern prints at least one line, and the last command lists `route.ts`.

If anything is missing, stop and report which row of the assumptions table failed; do not invent a stand-in. Two known, allowed variations:

- `build_assistant_tools(db)` without `user`: fine, Task 9 Step 4 adds it.
- The Next export route lives at a different path: note the real path; Task 11 Step 4 sets `CANDIDATE_EXPORT_PATH` to it.

- [ ] **Step 3: Read the two B modules you will call**

Read `backend/services/access_service.py` and `backend/utils/permissions.py` in full. Confirm `visible_candidate_ids` returns `None` (not "every id") for unrestricted roles, and that `can("demo", REPORTS_VIEW)` is whatever B decided (this plan does not rely on it; the router lets demo through explicitly).

---

### Task 2: Service skeleton, `Scope`, quarters, event kinds

**Files:**
- Create: `backend/services/reports_service.py`
- Create: `backend/tests/test_reports.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_reports.py`:

```python
"""Reports and dashboard numbers (ATS Phase D).

One job, four applications, every stage timestamp fixed. Every assertion is
computed by hand from the table below and the fixed instant NOW, so nothing
here depends on the day the suite runs or on what else is in the database:
every service call is scoped to this job or to these candidates.

    app  source    history (all 2025)
    A    referral  resume Nov 1-2, HM review Nov 2-4, technical assessment since Nov 4
    B    linkedin  resume Nov 10-13, HM review since Nov 17
    C    referral  hired: resume Sep 1-2, HM review Sep 2-12, five rounds of one day
                   each Sep 12-17, offer Sep 17-18, offer accepted Sep 18 to Oct 5,
                   Hired Oct 5 (offer declined skipped)
    D    (blank)   rejected: resume Jun 1-2, HM review Jun 2 to Sep 25 (failed there),
                   everything later skipped Sep 25

Interviews: Ivy has one on A's technical assessment (no feedback yet) and one
on C's HM review (feedback submitted). Ian has none.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from backend.services import reports_service as rs

NOW = datetime(2025, 11, 20, 12, 0, 0)


def test_quarter_bounds_are_calendar_quarters():
    assert rs.quarter_bounds(NOW) == (datetime(2025, 10, 1), datetime(2026, 1, 1), "Q4 2025")
    assert rs.quarter_bounds(NOW, offset=-1) == (datetime(2025, 7, 1), datetime(2025, 10, 1), "Q3 2025")
    # Crossing a year boundary backwards.
    assert rs.quarter_bounds(datetime(2026, 2, 14), offset=-1) == (
        datetime(2025, 10, 1),
        datetime(2026, 1, 1),
        "Q4 2025",
    )


@pytest.mark.parametrize(
    ("kind", "key", "status", "expected"),
    [
        ("outcome", "hired", "passed", "hired"),
        ("outcome", "offer_declined", "passed", "declined"),
        ("outcome", "hired", "skipped", None),
        ("round", "hm_review", "passed", "passed"),
        ("round", "hm_review", "failed", "rejected"),
        ("round", "hm_review", "skipped", "skipped"),
        ("round", "hm_review", "in_progress", None),
        ("round", "hm_review", "pending", None),
    ],
)
def test_event_kind(kind, key, status, expected):
    assert rs.event_kind(kind, key, status) == expected


def test_scope_normalizes_candidate_ids():
    assert rs.Scope.of().candidate_ids is None
    assert rs.Scope.of(candidate_ids={"b", "a"}).candidate_ids == frozenset({"a", "b"})
    assert rs.Scope.of(candidate_ids=set()).candidate_ids == frozenset()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: FAIL with `ImportError: cannot import name 'reports_service'`

- [ ] **Step 3: Write the skeleton**

Create `backend/services/reports_service.py`:

```python
"""Reports and dashboard numbers (ATS Phase D, spec 2026-10-03 section 8).

Every function is a query over `application_stages`, joined to the pipeline
stage it belongs to and the application it is part of. Nothing is cached,
sampled, estimated, or projected, which is what lets the Reports page say
"every number is a query" and mean it.

Two rules hold throughout:

- `now` is always a parameter. Routers and assistant tools pass
  `datetime.utcnow()`; tests pass a fixed instant, so no assertion depends on
  the day the suite runs.
- `Scope` narrows every query the same way: to one job, and to the candidates
  the viewer may see (`access_service.visible_candidate_ids`, None meaning
  everyone). Every public function takes one, because a query that forgot it
  would show an interviewer people they are not assigned to.

Read only. Nothing here writes, flushes, or commits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import Float, and_, case, cast, distinct, extract, func, literal_column, or_, select
from sqlalchemy.orm import Session, aliased

from backend.models.models import (
    ApplicationStage,
    Candidate,
    Feedback,
    Interview,
    Job,
    JobApplication,
    PipelineStage,
    User,
)
from backend.services import pipeline_service as ps
from backend.utils.auth import ROLE_INTERVIEWER

NO_MOVEMENT_DAYS = 7
LIST_LIMIT = 50
ACTIVITY_LIMIT = 20

# A stage counts as reached once the candidate started it, whatever came of
# it. Skipped stages were never reached.
REACHED = (ps.IN_PROGRESS, ps.PASSED, ps.FAILED)

# Rounds from this position on count toward the dashboard's "In interview or
# later" tile: everything after Resume submitted and Hiring manager review.
INTERVIEW_FROM_POSITION = 3

_DEFAULT_NAMES = {key: name for key, name, _kind, _description in ps.DEFAULT_STAGES}


@dataclass(frozen=True)
class Scope:
    """Which applications a query may count.

    `candidate_ids` None means no restriction; an empty set means nobody.
    """

    job_id: Optional[int] = None
    candidate_ids: Optional[frozenset] = None

    @classmethod
    def of(cls, job_id: Optional[int] = None, candidate_ids: Optional[Iterable[str]] = None) -> "Scope":
        return cls(
            job_id=job_id,
            candidate_ids=None if candidate_ids is None else frozenset(candidate_ids),
        )


def _scoped(query, scope: Scope):
    """Apply the scope. Every query below has job_applications in its FROM."""
    if scope.job_id is not None:
        query = query.filter(JobApplication.job_id == scope.job_id)
    if scope.candidate_ids is not None:
        query = query.filter(JobApplication.candidate_id.in_(sorted(scope.candidate_ids)))
    return query


def _stage_rows(db: Session, *columns):
    """application_stages joined to its stage and its application."""
    return (
        db.query(*columns)
        .select_from(ApplicationStage)
        .join(PipelineStage, PipelineStage.id == ApplicationStage.stage_id)
        .join(JobApplication, JobApplication.id == ApplicationStage.application_id)
    )


def _person(first: Optional[str], last: Optional[str]) -> str:
    return " ".join(part for part in (first, last) if part) or "Unnamed candidate"


def _title(title: Optional[str]) -> str:
    return title or "Untitled job"


def _stage_name(key: str, name: str, scope: Scope) -> str:
    # Across jobs a stage renamed on one job would show whichever name sorts
    # first; the default name is the one everybody recognises. Within one
    # job, that job's own name.
    if scope.job_id is None and key in _DEFAULT_NAMES:
        return _DEFAULT_NAMES[key]
    return name


def quarter_bounds(now: datetime, offset: int = 0) -> tuple[datetime, datetime, str]:
    """[start, end) of the calendar quarter holding `now`, moved by `offset` quarters."""
    index = now.year * 4 + (now.month - 1) // 3 + offset
    year, quarter = divmod(index, 4)
    end_year, end_quarter = divmod(index + 1, 4)
    return (
        datetime(year, quarter * 3 + 1, 1),
        datetime(end_year, end_quarter * 3 + 1, 1),
        f"Q{quarter + 1} {year}",
    )


def event_kind(stage_kind: str, stage_key: str, status: str) -> Optional[str]:
    """What a finished stage row means in the activity feed, or None for no event."""
    if stage_kind == ps.OUTCOME:
        if status != ps.PASSED:
            return None
        return {"hired": "hired", "offer_declined": "declined"}.get(stage_key, "passed")
    return {ps.PASSED: "passed", ps.FAILED: "rejected", ps.SKIPPED: "skipped"}.get(status)
```

- [ ] **Step 4: Run the tests**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: 10 passed

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d2.txt`:

```
feat: reports service skeleton with scope, quarters, and event kinds

Phase D of the ATS blueprint. Every report query will take a Scope (one
job and/or the candidates the viewer may see) and an explicit now, so the
numbers are testable on a fixed timeline and an interviewer can never be
shown someone they are not assigned to.
```

```powershell
git add backend/services/reports_service.py backend/tests/test_reports.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d2.txt
```

---

### Task 3: The fixed timeline fixture and the funnel

**Files:**
- Modify: `backend/services/reports_service.py`
- Modify: `backend/tests/test_reports.py`

- [ ] **Step 1: Add the fixture**

Append to `backend/tests/test_reports.py` (and extend the imports at the top as shown):

```python
from backend.models.models import (
    ApplicationStage,
    Candidate,
    Feedback,
    Interview,
    Job,
    JobApplication,
    User,
)
from backend.services import pipeline_service as ps
from backend.tests.conftest import SEED_EMAIL_DOMAIN

IDS = {name: "00000000-0000-4000-8000-0000000d000%d" % i for i, name in enumerate("ABCD", start=1)}
JOB_TITLE = "Reports Test Analyst"


def d(month: int, day: int) -> datetime:
    return datetime(2025, month, day)


_LATER_THAN_HM = (
    "technical_written",
    "technical_interview",
    "problem_solving",
    "case_study",
    "hr_screen",
    "offer",
    "offer_accepted",
    "offer_declined",
    "hired",
)

# letter -> (source, application status, {stage key: (status, started_at, completed_at)})
# Stages not listed are pending with no timestamps.
HISTORY = {
    "A": (
        "referral",
        "active",
        {
            "resume_submitted": ("passed", d(11, 1), d(11, 2)),
            "hm_review": ("passed", d(11, 2), d(11, 4)),
            "technical_written": ("in_progress", d(11, 4), None),
        },
    ),
    "B": (
        "linkedin",
        "active",
        {
            "resume_submitted": ("passed", d(11, 10), d(11, 13)),
            "hm_review": ("in_progress", d(11, 17), None),
        },
    ),
    "C": (
        "referral",
        "hired",
        {
            "resume_submitted": ("passed", d(9, 1), d(9, 2)),
            "hm_review": ("passed", d(9, 2), d(9, 12)),
            "technical_written": ("passed", d(9, 12), d(9, 13)),
            "technical_interview": ("passed", d(9, 13), d(9, 14)),
            "problem_solving": ("passed", d(9, 14), d(9, 15)),
            "case_study": ("passed", d(9, 15), d(9, 16)),
            "hr_screen": ("passed", d(9, 16), d(9, 17)),
            "offer": ("passed", d(9, 17), d(9, 18)),
            "offer_accepted": ("passed", d(9, 18), d(10, 5)),
            "offer_declined": ("skipped", None, d(10, 5)),
            "hired": ("passed", d(10, 5), d(10, 5)),
        },
    ),
    "D": (
        "",
        "rejected",
        {
            "resume_submitted": ("passed", d(6, 1), d(6, 2)),
            "hm_review": ("failed", d(6, 2), d(9, 25)),
            **{key: ("skipped", None, d(9, 25)) for key in _LATER_THAN_HM},
        },
    ),
}


@pytest.fixture(scope="module")
def timeline(db_session, seed):
    """The job, people, applications, stage rows, and interviews from the docstring.

    Committed, not flushed: a route in this module that rolls back would
    otherwise revert to the last commit and take these rows with it.
    """
    job = Job(
        title=JOB_TITLE,
        department="Analytics",
        job_overview="Exists to give the reports a fixed history.",
        required_qualifications="SQL",
        location="Remote",
        location_type="remote",
        job_type="full_time",
        experience_level="mid",
        status="open",
        skills="SQL",
        job_metadata={},
        views=0,
        applications=4,
    )
    db_session.add(job)
    db_session.flush()
    stages = {s.key: s for s in ps.ensure_job_stages(db_session, job.id)}

    applications = {}
    for letter, (source, app_status, history) in HISTORY.items():
        db_session.add(
            Candidate(
                id=IDS[letter],
                first_name="Report",
                last_name=f"Person {letter}",
                email=f"reports-{letter.lower()}@{SEED_EMAIL_DOMAIN}",
                status="active",
                source=source or None,
                created_at=d(1, 1),
                updated_at=d(1, 1),
            )
        )
        db_session.flush()
        application = JobApplication(
            job_id=job.id,
            candidate_id=IDS[letter],
            status=app_status,
            applied_at=history["resume_submitted"][1],
            updated_at=history["resume_submitted"][1],
            source=source,
        )
        db_session.add(application)
        db_session.flush()
        for key, stage in stages.items():
            status, started, completed = history.get(key, ("pending", None, None))
            db_session.add(
                ApplicationStage(
                    application_id=application.id,
                    stage_id=stage.id,
                    status=status,
                    started_at=started,
                    completed_at=completed,
                )
            )
        applications[letter] = application
    db_session.flush()

    def stage_row(letter: str, key: str) -> ApplicationStage:
        return (
            db_session.query(ApplicationStage)
            .filter(
                ApplicationStage.application_id == applications[letter].id,
                ApplicationStage.stage_id == stages[key].id,
            )
            .one()
        )

    ivy = User(
        email=f"ivy@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role="interviewer",
        name="Ivy Interviewer",
        created_at=d(1, 1),
    )
    ian = User(
        email=f"ian@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role="interviewer",
        name="Ian Interviewer",
        created_at=d(1, 1),
    )
    db_session.add_all([ivy, ian])
    db_session.flush()

    waiting = Interview(
        application_stage_id=stage_row("A", "technical_written").id,
        interviewer_id=ivy.id,
        assignment_source="manual",
        created_at=d(11, 4),
    )
    done = Interview(
        application_stage_id=stage_row("C", "hm_review").id,
        interviewer_id=ivy.id,
        assignment_source="manual",
        created_at=d(9, 2),
    )
    db_session.add_all([waiting, done])
    db_session.flush()
    db_session.add(
        Feedback(
            interview_id=done.id,
            rating=4,
            recommendation="hire",
            notes="Clear thinker.",
            submitted_at=d(9, 12),
        )
    )
    db_session.commit()

    return {
        "job_id": job.id,
        "applications": {letter: app.id for letter, app in applications.items()},
        "ivy": ivy,
        "ian": ian,
    }


def _scope(timeline, **kwargs) -> rs.Scope:
    return rs.Scope.of(job_id=timeline["job_id"], **kwargs)
```

- [ ] **Step 2: Write the failing funnel tests**

Append:

```python
ROUND_KEYS = [key for key, _name, kind, _desc in ps.DEFAULT_STAGES if kind == "round"]


def test_funnel_lists_every_round_in_pipeline_order(db_session, timeline):
    assert [r["key"] for r in rs.stage_funnel(db_session, _scope(timeline))] == ROUND_KEYS


def test_funnel_counts_ever_reached_and_here_now(db_session, timeline):
    rows = {r["key"]: r for r in rs.stage_funnel(db_session, _scope(timeline))}
    counts = {key: (row["ever_reached"], row["currently_here"]) for key, row in rows.items()}
    assert counts["resume_submitted"] == (4, 0)
    # D failed here, which still counts as reached. B is here now.
    assert counts["hm_review"] == (4, 1)
    assert counts["technical_written"] == (2, 1)
    assert counts["offer_accepted"] == (1, 0)
    assert rows["technical_written"]["share_of_applicants"] == 0.5
    assert rows["hm_review"]["name"] == "Hiring manager review"


def test_totals(db_session, timeline):
    assert rs.total_applications(db_session, _scope(timeline)) == 4
    assert rs.hired_applications(db_session, _scope(timeline)) == 1


def test_scope_to_visible_candidates(db_session, timeline):
    only_a = _scope(timeline, candidate_ids={IDS["A"]})
    rows = {r["key"]: r for r in rs.stage_funnel(db_session, only_a)}
    assert rows["resume_submitted"]["ever_reached"] == 1
    assert rs.total_applications(db_session, only_a) == 1
    nobody = _scope(timeline, candidate_ids=set())
    assert rs.total_applications(db_session, nobody) == 0
    assert rs.stage_funnel(db_session, nobody) == []
```

- [ ] **Step 3: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: the four new tests FAIL with `AttributeError: module 'backend.services.reports_service' has no attribute 'stage_funnel'` (or `total_applications`)

- [ ] **Step 4: Implement totals and the funnel**

Append to `backend/services/reports_service.py`:

```python
def total_applications(db: Session, scope: Scope) -> int:
    return _scoped(db.query(func.count(JobApplication.id)), scope).scalar() or 0


def hired_applications(db: Session, scope: Scope) -> int:
    query = db.query(func.count(JobApplication.id)).filter(JobApplication.status == ps.APP_HIRED)
    return _scoped(query, scope).scalar() or 0


def stage_funnel(db: Session, scope: Scope) -> list[dict]:
    """Per round: applications that ever reached it, and those there right now.

    "Reached" means started (in progress, passed, or rejected there); a
    skipped round was never reached. "Here now" counts only active
    applications. Across jobs, rounds group by key in pipeline order.
    """
    ever = func.count(
        distinct(case((ApplicationStage.status.in_(REACHED), ApplicationStage.application_id)))
    )
    here = func.count(
        distinct(
            case(
                (
                    and_(
                        ApplicationStage.status == ps.IN_PROGRESS,
                        JobApplication.status == ps.APP_ACTIVE,
                    ),
                    ApplicationStage.application_id,
                )
            )
        )
    )
    position = func.min(PipelineStage.position)
    query = (
        _stage_rows(db, PipelineStage.key, position, func.min(PipelineStage.name), ever, here)
        .filter(PipelineStage.kind == ps.ROUND)
        .group_by(PipelineStage.key)
        .order_by(position, PipelineStage.key)
    )
    rows = _scoped(query, scope).all()
    total = total_applications(db, scope)
    return [
        {
            "key": key,
            "name": _stage_name(key, name, scope),
            "position": pos,
            "ever_reached": ever_reached,
            "currently_here": currently_here,
            "share_of_applicants": round(ever_reached / total, 3) if total else 0.0,
        }
        for key, pos, name, ever_reached, currently_here in rows
    ]
```

- [ ] **Step 5: Run the tests**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: 14 passed

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d3.txt`:

```
feat: stage funnel query, ever reached vs here now

One grouped query over application_stages. A skipped round does not count
as reached; a round someone was rejected at does. Tested on a fixed
four-application timeline, including scoping to a set of visible
candidates and to nobody at all.
```

```powershell
git add backend/services/reports_service.py backend/tests/test_reports.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d3.txt
```

---

### Task 4: Median time in stage

**Files:**
- Modify: `backend/services/reports_service.py`
- Modify: `backend/tests/test_reports.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reports.py`:

```python
def test_median_time_in_stage(db_session, timeline):
    rows = {r["key"]: r for r in rs.time_in_stage(db_session, _scope(timeline))}
    # Resume submitted took 1 (A), 3 (B), 1 (C), and 1 (D) days.
    assert rows["resume_submitted"]["median_days"] == pytest.approx(1.0)
    assert rows["resume_submitted"]["completed"] == 4
    # HM review: 2 (A), 10 (C), 115 (D, Jun 2 to Sep 25). B is still there.
    assert rows["hm_review"]["median_days"] == pytest.approx(10.0)
    assert rows["hm_review"]["completed"] == 3
    assert rows["offer_accepted"]["median_days"] == pytest.approx(17.0)
    # A is still in technical assessment, so only C's day counts.
    assert rows["technical_written"]["completed"] == 1


def test_median_interpolates_between_two_values(db_session, timeline):
    # A (1 day) and B (3 days) only: percentile_cont gives the midpoint.
    scope = _scope(timeline, candidate_ids={IDS["A"], IDS["B"]})
    rows = {r["key"]: r for r in rs.time_in_stage(db_session, scope)}
    assert rows["resume_submitted"]["median_days"] == pytest.approx(2.0)
    # Nobody in this scope finished technical assessment.
    assert "technical_written" not in rows


def test_zero_length_rows_are_not_time_spent(db_session, timeline):
    # C's Hired outcome starts and ends on the same instant, and outcomes are
    # not rounds anyway; neither shows up as a 0-day median.
    keys = {r["key"] for r in rs.time_in_stage(db_session, _scope(timeline))}
    assert "hired" not in keys and "offer_declined" not in keys
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_reports.py -q -k "median or zero_length"`
Expected: 3 failed, `AttributeError: ... has no attribute 'time_in_stage'`

- [ ] **Step 3: Implement it**

Append to `backend/services/reports_service.py`:

```python
def time_in_stage(db: Session, scope: Scope) -> list[dict]:
    """Median days from entering a round to leaving it, per round.

    Counts rounds that ended (passed, or rejected there) with a real
    duration. Rows whose start and end are the same instant are left out:
    those are history rows written in one go (the Phase A migration backfill
    and the original seed), not time anybody spent. Rounds nobody has
    finished are not listed. Computed in Postgres with percentile_cont, so a
    median of two values is their midpoint.
    """
    days = cast(extract("epoch", ApplicationStage.completed_at - ApplicationStage.started_at), Float) / 86400.0
    position = func.min(PipelineStage.position)
    query = (
        _stage_rows(
            db,
            PipelineStage.key,
            position,
            func.min(PipelineStage.name),
            func.percentile_cont(0.5).within_group(days),
            func.count(ApplicationStage.id),
        )
        .filter(
            PipelineStage.kind == ps.ROUND,
            ApplicationStage.status.in_((ps.PASSED, ps.FAILED)),
            ApplicationStage.started_at.isnot(None),
            ApplicationStage.completed_at > ApplicationStage.started_at,
        )
        .group_by(PipelineStage.key)
        .order_by(position, PipelineStage.key)
    )
    return [
        {
            "key": key,
            "name": _stage_name(key, name, scope),
            "position": pos,
            "median_days": None if median is None else round(float(median), 2),
            "completed": completed,
        }
        for key, pos, name, median, completed in _scoped(query, scope).all()
    ]
```

- [ ] **Step 4: Run the tests**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: 17 passed

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d4.txt`:

```
feat: median time in stage, computed in Postgres

percentile_cont over completed_at minus started_at for rounds that ended.
Zero-length rows (bulk backfill, not real time) are excluded so the
migrated history cannot pull every median to zero. Tested on fixed
durations, including the two-value midpoint.
```

```powershell
git add backend/services/reports_service.py backend/tests/test_reports.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d4.txt
```

---

### Task 5: No movement in 7+ days, and pending feedback

**Files:**
- Modify: `backend/services/reports_service.py`
- Modify: `backend/tests/test_reports.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reports.py`:

```python
def test_no_movement_uses_the_injected_now(db_session, timeline):
    rows, total = rs.no_movement(db_session, _scope(timeline), NOW)
    assert total == 1
    assert [(r["candidate_id"], r["stage_key"], r["days_waiting"]) for r in rows] == [
        (IDS["A"], "technical_written", 16)
    ]
    assert rows[0]["job_title"] == JOB_TITLE
    assert rows[0]["stage_name"] == "Technical assessment"
    # Four days later B (HM review since Nov 17) has crossed the line too,
    # and the longest wait is listed first.
    rows, total = rs.no_movement(db_session, _scope(timeline), datetime(2025, 11, 24, 12, 0))
    assert total == 2
    assert [r["candidate_id"] for r in rows] == [IDS["A"], IDS["B"]]


def test_no_movement_ignores_finished_applications(db_session, timeline):
    # C and D ended months ago but are not "waiting": they have no stage in progress.
    rows, _total = rs.no_movement(db_session, _scope(timeline), datetime(2026, 6, 1))
    assert {r["candidate_id"] for r in rows} == {IDS["A"], IDS["B"]}


def test_pending_feedback(db_session, timeline):
    rows = rs.pending_feedback(db_session, _scope(timeline), NOW)
    assert [
        (r["candidate_id"], r["stage_name"], r["interviewer_name"], r["days_pending"]) for r in rows
    ] == [(IDS["A"], "Technical assessment", "Ivy Interviewer", 16)]


def test_an_interviewer_sees_only_their_own_pending_feedback(db_session, timeline):
    assert len(rs.pending_feedback(db_session, _scope(timeline), NOW, viewer=timeline["ivy"])) == 1
    assert rs.pending_feedback(db_session, _scope(timeline), NOW, viewer=timeline["ian"]) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_reports.py -q -k "no_movement or pending"`
Expected: 4 failed with `AttributeError`

- [ ] **Step 3: Implement them**

Append to `backend/services/reports_service.py`:

```python
def no_movement(
    db: Session,
    scope: Scope,
    now: datetime,
    days: int = NO_MOVEMENT_DAYS,
    limit: int = LIST_LIMIT,
) -> tuple[list[dict], int]:
    """Active applications whose current stage started more than `days` ago.

    Returns (longest waits first, capped at `limit`; total count).
    """
    cutoff = now - timedelta(days=days)
    query = (
        _stage_rows(
            db,
            ApplicationStage.started_at,
            JobApplication.id,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
            PipelineStage.key,
            PipelineStage.name,
        )
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .filter(
            ApplicationStage.status == ps.IN_PROGRESS,
            JobApplication.status == ps.APP_ACTIVE,
            ApplicationStage.started_at.isnot(None),
            ApplicationStage.started_at < cutoff,
        )
    )
    query = _scoped(query, scope)
    total = query.count()
    rows = query.order_by(ApplicationStage.started_at, JobApplication.id).limit(limit).all()
    return (
        [
            {
                "application_id": application_id,
                "candidate_id": candidate_id,
                "candidate_name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_key": stage_key,
                "stage_name": stage_name,
                "since": since,
                "days_waiting": (now - since).days,
            }
            for since, application_id, candidate_id, first, last, job_id, job_title, stage_key, stage_name in rows
        ],
        total,
    )


def pending_feedback(
    db: Session,
    scope: Scope,
    now: datetime,
    viewer: Optional[User] = None,
    limit: int = LIST_LIMIT,
) -> list[dict]:
    """Interviews on a stage the candidate has reached, with no feedback yet.

    Oldest first, by when the stage started. An interviewer sees only their
    own; every other viewer sees all of them. A skipped stage's interview is
    not pending: the round never happened.
    """
    interviewer = aliased(User)
    query = (
        db.query(
            Interview.id,
            interviewer.name,
            JobApplication.id,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
            PipelineStage.name,
            ApplicationStage.started_at,
            Interview.created_at,
        )
        .select_from(Interview)
        .join(ApplicationStage, ApplicationStage.id == Interview.application_stage_id)
        .join(PipelineStage, PipelineStage.id == ApplicationStage.stage_id)
        .join(JobApplication, JobApplication.id == ApplicationStage.application_id)
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .join(interviewer, interviewer.id == Interview.interviewer_id)
        .outerjoin(Feedback, Feedback.interview_id == Interview.id)
        .filter(Feedback.id.is_(None), ApplicationStage.status.in_(REACHED))
    )
    if viewer is not None and viewer.role == ROLE_INTERVIEWER:
        query = query.filter(Interview.interviewer_id == viewer.id)
    rows = (
        _scoped(query, scope)
        .order_by(ApplicationStage.started_at.asc().nulls_last(), Interview.id)
        .limit(limit)
        .all()
    )
    out = []
    for (
        interview_id,
        interviewer_name,
        application_id,
        candidate_id,
        first,
        last,
        job_id,
        job_title,
        stage_name,
        stage_started,
        assigned,
    ) in rows:
        since = stage_started or assigned
        out.append(
            {
                "interview_id": interview_id,
                "interviewer_name": interviewer_name,
                "application_id": application_id,
                "candidate_id": candidate_id,
                "candidate_name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_name": stage_name,
                "days_pending": max(0, (now - since).days) if since else 0,
            }
        )
    return out
```

- [ ] **Step 4: Run the tests**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: 21 passed

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d5.txt`:

```
feat: no movement in 7+ days and pending feedback queries

Both drive the dashboard's attention list. The cutoff comes from the
injected now, tested on both sides of the line. Pending feedback reads
Phase B's interviews and feedback tables; an interviewer only ever sees
their own outstanding interviews.
```

```powershell
git add backend/services/reports_service.py backend/tests/test_reports.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d5.txt
```

---

### Task 6: Source mix and outcomes by quarter

**Files:**
- Modify: `backend/services/reports_service.py`
- Modify: `backend/tests/test_reports.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reports.py`:

```python
def test_source_mix(db_session, timeline):
    # D's blank source groups as "unknown". Ties sort by name.
    assert rs.source_mix(db_session, _scope(timeline)) == [
        {"source": "referral", "applications": 2, "hired": 1},
        {"source": "linkedin", "applications": 1, "hired": 0},
        {"source": "unknown", "applications": 1, "hired": 0},
    ]


def test_outcomes_by_quarter(db_session, timeline):
    this_quarter = rs.outcomes_between(db_session, _scope(timeline), *rs.quarter_bounds(NOW))
    last_quarter = rs.outcomes_between(db_session, _scope(timeline), *rs.quarter_bounds(NOW, offset=-1))
    # C was hired Oct 5 (Q4). D was rejected Sep 25 (Q3).
    assert (this_quarter["label"], this_quarter["hires"], this_quarter["rejections"]) == ("Q4 2025", 1, 0)
    assert this_quarter["offers_declined"] == 0
    assert (last_quarter["label"], last_quarter["hires"], last_quarter["rejections"]) == ("Q3 2025", 0, 1)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_reports.py -q -k "source_mix or outcomes_by"`
Expected: 2 failed with `AttributeError`

- [ ] **Step 3: Implement them**

Append to `backend/services/reports_service.py`:

```python
def source_mix(db: Session, scope: Scope) -> list[dict]:
    """Applications and hires per application source, busiest first.

    The constants are literal SQL, not bound parameters, so the expression in
    SELECT and GROUP BY renders identically and Postgres accepts the grouping.
    """
    source = func.coalesce(
        func.nullif(func.lower(func.trim(JobApplication.source)), literal_column("''")),
        literal_column("'unknown'"),
    )
    applications = func.count(JobApplication.id)
    hired = func.count(case((JobApplication.status == ps.APP_HIRED, JobApplication.id)))
    query = db.query(source, applications, hired).group_by(source).order_by(applications.desc(), source)
    return [
        {"source": name, "applications": count, "hired": hires}
        for name, count, hires in _scoped(query, scope).all()
    ]


def outcomes_between(db: Session, scope: Scope, start: datetime, end: datetime, label: str) -> dict:
    """Hires, rejections, and declined offers recorded in [start, end)."""
    hires = func.count(
        case((and_(PipelineStage.key == "hired", ApplicationStage.status == ps.PASSED), ApplicationStage.id))
    )
    rejections = func.count(case((ApplicationStage.status == ps.FAILED, ApplicationStage.id)))
    declined = func.count(
        case(
            (
                and_(PipelineStage.key == "offer_declined", ApplicationStage.status == ps.PASSED),
                ApplicationStage.id,
            )
        )
    )
    query = _stage_rows(db, hires, rejections, declined).filter(
        ApplicationStage.completed_at >= start, ApplicationStage.completed_at < end
    )
    hired_count, rejected_count, declined_count = _scoped(query, scope).one()
    return {
        "label": label,
        "start": start,
        "end": end,
        "hires": hired_count,
        "rejections": rejected_count,
        "offers_declined": declined_count,
    }
```

- [ ] **Step 4: Run the tests**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: 23 passed

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d6.txt`:

```
feat: source mix and hires/rejections by calendar quarter

Quarter bounds come from the injected now. Rejections are rounds marked
failed; hires and declined offers are their outcome rows. Tested across
the Q3/Q4 boundary on the fixed timeline.
```

```powershell
git add backend/services/reports_service.py backend/tests/test_reports.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d6.txt
```

---

### Task 7: Activity feed and the two bundles

**Files:**
- Modify: `backend/services/reports_service.py`
- Modify: `backend/tests/test_reports.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reports.py`:

```python
def test_activity_newest_first(db_session, timeline):
    events = rs.activity(db_session, _scope(timeline), limit=8)
    assert [(e["kind"], e["candidate_id"], e["stage_name"]) for e in events] == [
        ("passed", IDS["B"], "Resume submitted"),  # Nov 13
        ("applied", IDS["B"], None),  # Nov 10
        ("passed", IDS["A"], "Hiring manager review"),  # Nov 4
        ("passed", IDS["A"], "Resume submitted"),  # Nov 2
        ("applied", IDS["A"], None),  # Nov 1
        # Oct 5: Offer accepted passing at the same instant is folded into the hire.
        ("hired", IDS["C"], "Hired"),
        ("rejected", IDS["D"], "Hiring manager review"),  # Sep 25
        ("passed", IDS["C"], "Offer"),  # Sep 18
    ]
    assert events[0]["job_title"] == JOB_TITLE
    assert events[0]["candidate_name"] == "Report Person B"


def test_activity_leaves_out_automatic_skips(db_session, timeline):
    events = rs.activity(db_session, _scope(timeline), limit=100)
    # D's seven later rounds and C's Offer declined were skipped by the
    # system, not by a person.
    assert not [e for e in events if e["kind"] == "skipped"]


def test_dashboard_bundle(db_session, timeline):
    data = rs.dashboard(db_session, _scope(timeline), NOW)
    assert data["total_applications"] == 4
    # A is at technical assessment (round 3) and C is hired; B at HM review is not counted.
    assert data["interviewing_or_later"] == 2
    assert data["no_movement_total"] == 1
    assert [p["candidate_id"] for p in data["pending_feedback"]] == [IDS["A"]]
    assert data["generated_at"] == NOW


def test_reports_bundle(db_session, timeline):
    data = rs.reports(db_session, _scope(timeline), NOW)
    assert [q["label"] for q in data["quarters"]] == ["Q4 2025", "Q3 2025"]
    assert data["job_id"] == timeline["job_id"]
    assert len(data["funnel"]) == 9
    assert data["no_movement_total"] == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_reports.py -q -k "activity or bundle"`
Expected: 4 failed with `AttributeError`

- [ ] **Step 3: Implement them**

Append to `backend/services/reports_service.py`:

```python
def activity(db: Session, scope: Scope, limit: int = ACTIVITY_LIMIT) -> list[dict]:
    """The latest pipeline moves, newest first, from stage timestamps alone.

    Events: a first stage starting (an application arriving), a round passed
    or rejected, a round a person skipped, and an outcome reached. Two kinds
    of row are bookkeeping rather than events and are left out: stages
    skipped automatically (no changed_by) when an application ends or a
    disabled round is passed over, and the last round passing at the very
    instant the Hired or Offer declined outcome is recorded, where the
    outcome is the event.
    """
    actor = aliased(User)
    outcome = aliased(ApplicationStage)
    outcome_stage = aliased(PipelineStage)
    folded_into_outcome = (
        select(outcome.id)
        .join(outcome_stage, outcome_stage.id == outcome.stage_id)
        .where(
            outcome.application_id == ApplicationStage.application_id,
            outcome_stage.kind == ps.OUTCOME,
            outcome.status == ps.PASSED,
            outcome.completed_at == ApplicationStage.completed_at,
        )
        .exists()
    )
    completed = (
        _stage_rows(
            db,
            ApplicationStage.completed_at,
            ApplicationStage.status,
            PipelineStage.key,
            PipelineStage.kind,
            PipelineStage.name,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
            actor.name,
        )
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .outerjoin(actor, actor.id == ApplicationStage.changed_by)
        .filter(
            ApplicationStage.completed_at.isnot(None),
            or_(
                ApplicationStage.status.in_((ps.PASSED, ps.FAILED)),
                and_(ApplicationStage.status == ps.SKIPPED, ApplicationStage.changed_by.isnot(None)),
            ),
            ~and_(
                PipelineStage.kind == ps.ROUND,
                ApplicationStage.status == ps.PASSED,
                folded_into_outcome,
            ),
        )
    )
    completed = (
        _scoped(completed, scope)
        .order_by(ApplicationStage.completed_at.desc(), ApplicationStage.id.desc())
        .limit(limit)
        .all()
    )

    events = []
    for at, status, key, kind, stage_name, candidate_id, first, last, job_id, job_title, actor_name in completed:
        event = event_kind(kind, key, status)
        if event is None:
            continue
        events.append(
            {
                "at": at,
                "kind": event,
                "candidate_id": candidate_id,
                "candidate_name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_name": stage_name,
                "actor_name": actor_name,
            }
        )

    entered = (
        _stage_rows(
            db,
            ApplicationStage.started_at,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
        )
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .filter(PipelineStage.position == 1, ApplicationStage.started_at.isnot(None))
    )
    entered = (
        _scoped(entered, scope)
        .order_by(ApplicationStage.started_at.desc(), ApplicationStage.id.desc())
        .limit(limit)
        .all()
    )
    for at, candidate_id, first, last, job_id, job_title in entered:
        events.append(
            {
                "at": at,
                "kind": "applied",
                "candidate_id": candidate_id,
                "candidate_name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_name": None,
                "actor_name": None,
            }
        )

    # Stable sort: on an exact tie a completion stays ahead of an arrival.
    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]


def dashboard(db: Session, scope: Scope, now: datetime, viewer: Optional[User] = None) -> dict:
    """Everything the dashboard's pipeline cards need, in one call."""
    funnel = stage_funnel(db, scope)
    waiting, waiting_total = no_movement(db, scope, now, limit=8)
    interviewing = sum(
        row["currently_here"] for row in funnel if row["position"] >= INTERVIEW_FROM_POSITION
    )
    return {
        "generated_at": now,
        "total_applications": total_applications(db, scope),
        "interviewing_or_later": interviewing + hired_applications(db, scope),
        "funnel": funnel,
        "no_movement": waiting,
        "no_movement_total": waiting_total,
        "pending_feedback": pending_feedback(db, scope, now, viewer=viewer, limit=8),
        "activity": activity(db, scope, limit=12),
    }


def reports(db: Session, scope: Scope, now: datetime) -> dict:
    """Everything the Reports page needs, in one call."""
    waiting, waiting_total = no_movement(db, scope, now)
    return {
        "generated_at": now,
        "job_id": scope.job_id,
        "total_applications": total_applications(db, scope),
        "funnel": stage_funnel(db, scope),
        "time_in_stage": time_in_stage(db, scope),
        "no_movement": waiting,
        "no_movement_total": waiting_total,
        "source_mix": source_mix(db, scope),
        "quarters": [
            outcomes_between(db, scope, *quarter_bounds(now)),
            outcomes_between(db, scope, *quarter_bounds(now, offset=-1)),
        ],
    }
```

- [ ] **Step 4: Run the tests**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: 27 passed

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d7.txt`:

```
feat: activity feed and dashboard/reports bundles

The feed is built from stage timestamps only. System bookkeeping (skips
written when an application ends, the last round passing at the instant
of the hire) is folded away so the feed reads as things people did.
```

```powershell
git add backend/services/reports_service.py backend/tests/test_reports.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d7.txt
```

---

### Task 8: Response models, router, route tests, OpenAPI

**Files:**
- Create: `backend/models/reports.py`
- Create: `backend/routers/reports.py`
- Modify: `backend/main.py` (router import line and mount list)
- Modify: `backend/tests/test_reports.py`

- [ ] **Step 1: Write the failing route tests**

Append to `backend/tests/test_reports.py`:

```python
from fastapi.testclient import TestClient

from backend.main import app
from backend.utils.auth import create_access_token


@pytest.fixture(scope="module")
def interviewer_client(override_get_db, timeline):
    token = create_access_token(timeline["ivy"])
    return TestClient(app, raise_server_exceptions=False, headers={"Authorization": f"Bearer {token}"})


def test_summary_for_one_job(admin_client, timeline):
    response = admin_client.get("/api/reports/summary", params={"job_id": timeline["job_id"]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_title"] == JOB_TITLE
    assert body["total_applications"] == 4
    hm = next(t for t in body["time_in_stage"] if t["key"] == "hm_review")
    assert hm["median_days"] == pytest.approx(10.0)
    assert len(body["quarters"]) == 2
    assert {s["source"] for s in body["source_mix"]} == {"referral", "linkedin", "unknown"}


def test_summary_for_an_unknown_job_is_404(admin_client):
    assert admin_client.get("/api/reports/summary", params={"job_id": 99999999}).status_code == 404


def test_the_demo_can_read_reports(demo_client):
    response = demo_client.get("/api/reports/summary")
    assert response.status_code == 200, response.text
    assert "funnel" in response.json()


def test_an_interviewer_cannot_read_reports(interviewer_client):
    response = interviewer_client.get("/api/reports/summary")
    # Phase B's interviewer gate answers before the handler, with its own sentence.
    assert response.status_code == 403


def test_anonymous_callers_cannot_read_reports(client):
    assert client.get("/api/reports/summary").status_code == 401


def test_the_dashboard_is_open_to_everyone(client, demo_client):
    for caller in (client, demo_client):
        response = caller.get("/api/reports/dashboard")
        assert response.status_code == 200, response.text
        assert {"funnel", "no_movement", "pending_feedback", "activity"} <= set(response.json())


def test_an_interviewer_dashboard_counts_only_assigned_candidates(interviewer_client):
    body = interviewer_client.get("/api/reports/dashboard").json()
    # Ivy has interviews on A and C, so only their two applications exist for her.
    assert body["total_applications"] == 2
    assert [p["candidate_id"] for p in body["pending_feedback"]] == [IDS["A"]]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_reports.py -q -k "summary or reports or dashboard_is or interviewer_dashboard"`
Expected: failures with 404 (no route yet)

- [ ] **Step 3: Write the response models**

Create `backend/models/reports.py`:

```python
"""Response shapes for the reports router (ATS Phase D)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FunnelRow(BaseModel):
    key: str
    name: str
    position: int
    ever_reached: int
    currently_here: int
    share_of_applicants: float


class StageTiming(BaseModel):
    key: str
    name: str
    position: int
    median_days: Optional[float] = None
    completed: int


class WaitingApplication(BaseModel):
    application_id: int
    candidate_id: str
    candidate_name: str
    job_id: int
    job_title: str
    stage_key: str
    stage_name: str
    since: datetime
    days_waiting: int


class PendingFeedbackRow(BaseModel):
    interview_id: int
    interviewer_name: Optional[str] = None
    application_id: int
    candidate_id: str
    candidate_name: str
    job_id: int
    job_title: str
    stage_name: str
    days_pending: int


class SourceRow(BaseModel):
    source: str
    applications: int
    hired: int


class QuarterOutcomes(BaseModel):
    label: str
    start: datetime
    end: datetime
    hires: int
    rejections: int
    offers_declined: int


class ActivityEvent(BaseModel):
    at: datetime
    kind: str
    candidate_id: str
    candidate_name: str
    job_id: int
    job_title: str
    stage_name: Optional[str] = None
    actor_name: Optional[str] = None


class DashboardResponse(BaseModel):
    generated_at: datetime
    total_applications: int
    interviewing_or_later: int
    funnel: List[FunnelRow]
    no_movement: List[WaitingApplication]
    no_movement_total: int
    pending_feedback: List[PendingFeedbackRow]
    activity: List[ActivityEvent]


class ReportsResponse(BaseModel):
    generated_at: datetime
    job_id: Optional[int] = None
    job_title: Optional[str] = None
    total_applications: int
    funnel: List[FunnelRow]
    time_in_stage: List[StageTiming]
    no_movement: List[WaitingApplication]
    no_movement_total: int
    source_mix: List[SourceRow]
    quarters: List[QuarterOutcomes]
```

- [ ] **Step 4: Write the router**

Create `backend/routers/reports.py`:

```python
"""Reports and dashboard numbers (ATS Phase D, spec 2026-10-03 section 8).

Reads only, so nothing here needs a ROUTE_PERMISSIONS entry. Plain `def`
handlers: they do sync ORM work and must not run on the event loop
(CLAUDE.md sharp edge).

Who sees what:
- The dashboard numbers are for every viewer, anonymous and demo included,
  narrowed to the candidates that viewer may see. An interviewer's
  dashboard counts only the people they are assigned to.
- The Reports summary needs REPORTS_VIEW (admin, hiring manager, hiring
  team) or the read-only demo role. The demo is let through explicitly
  because a visitor from the portfolio link must be able to see every
  screen; it is synthetic data and the summary carries no contact details
  and no match scores.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models.models import Job, User
from ..models.reports import DashboardResponse, ReportsResponse
from ..services import reports_service as rs
from ..services.access_service import visible_candidate_ids
from ..utils.auth import ROLE_DEMO, get_current_user, get_optional_user
from ..utils.database import get_db
from ..utils.permissions import REPORTS_VIEW, can

router = APIRouter(prefix="/reports")


def reports_reader(user: User = Depends(get_current_user)) -> User:
    if user.role == ROLE_DEMO or can(user.role, REPORTS_VIEW):
        return user
    raise HTTPException(status_code=403, detail="Reports are not available for your role.")


def _visible(db: Session, user: Optional[User]):
    return None if user is None else visible_candidate_ids(db, user)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> DashboardResponse:
    """Funnel, attention list, and activity for the dashboard."""
    scope = rs.Scope.of(candidate_ids=_visible(db, user))
    return DashboardResponse(**rs.dashboard(db, scope, datetime.utcnow(), viewer=user))


@router.get("/summary", response_model=ReportsResponse)
def get_summary(
    job_id: Optional[int] = Query(default=None, description="Limit every number to one job"),
    db: Session = Depends(get_db),
    user: User = Depends(reports_reader),
) -> ReportsResponse:
    """Everything on the Reports page, for all jobs or one."""
    job_title = None
    if job_id is not None:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        job_title = job.title
    scope = rs.Scope.of(job_id=job_id, candidate_ids=_visible(db, user))
    return ReportsResponse(job_title=job_title, **rs.reports(db, scope, datetime.utcnow()))
```

- [ ] **Step 5: Mount it**

In `backend/main.py`, add `reports` to the second `from backend.routers import ...` line (the one that already lists `pipeline`), then add directly below the `pipeline` mount:

```python
app.include_router(reports.router, prefix="/api", tags=["reports"])  # ATS Phase D reports and dashboard numbers
```

Phase B's interviewer gate (`enforce_interviewer_scope` in `backend/services/access_service.py`) answers 403 to an interviewer on any path not in `INTERVIEWER_PATHS`, before the handler runs. Add the dashboard there so the handler's own scoping applies (`test_an_interviewer_dashboard_counts_only_assigned_candidates`). Leave `/api/reports/summary` out: the gate's 403 is the right answer for interviewers, and the handler's REPORTS_VIEW check stays as a second line for any other role without it.

```python
        (r"/api/reports/dashboard", None),  # the handler narrows to visible_candidate_ids
```

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_reports.py -q`
Expected: 34 passed

Run: `poetry run pytest backend/tests/test_auth.py -q`
Expected: all pass (no mutating route was added, so the route walk is unchanged)

- [ ] **Step 7: Regenerate the OpenAPI file and web types**

```powershell
poetry run python scripts/export_openapi.py
poetry run python scripts/export_openapi.py --check
cd web; npm run types:api; cd ..
Select-String -Path web/src/lib/schema.d.ts -Pattern 'DashboardResponse:|ReportsResponse:|ActivityEvent:'
```

Expected: `--check` reports up to date; the three schema names print.

- [ ] **Step 8: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d8.txt`:

```
feat: reports router with dashboard and summary endpoints

GET /api/reports/dashboard is open to every viewer and scoped to the
candidates they may see; GET /api/reports/summary needs REPORTS_VIEW or the
read-only demo, so interviewers get 403 and anonymous callers 401.
Verified with route tests for each role, including an interviewer whose
dashboard counts only their two assigned candidates.
```

```powershell
git add backend/models/reports.py backend/routers/reports.py backend/main.py backend/tests/test_reports.py openapi.json web/src/lib/schema.d.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d8.txt
```

---

### Task 9: Assistant tools for pipeline state

**Files:**
- Modify: `backend/services/reports_service.py`
- Modify: `backend/services/assistant_tools.py`
- Modify: `backend/routers/assistant.py` (only if Step 4 applies)
- Modify: `evals/assistant_golden.json`
- Modify: `backend/tests/test_assistant_golden.py`
- Modify: `backend/tests/test_reports.py`

Memory rules that shape this task: push the intelligence into the tool (stage resolution and "who waited longest" happen in Python, never in a second model call), and write every note as a sentence a visitor could read, because the small local model repeats notes word for word.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reports.py`:

```python
import asyncio


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def tools(db_session, timeline):
    from backend.services.assistant_tools import build_assistant_tools

    return {t.name: t for t in build_assistant_tools(db_session)}


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("HM review", "hm review"),
        ("the hiring manager review stage", "hiring manager review"),
        ("Technical-Interview round", "technical interview"),
        ("  offer_accepted ", "offer accepted"),
    ],
)
def test_normalize_stage_text(typed, expected):
    assert rs.normalize_stage_text(typed) == expected


def test_resolve_stage(db_session, timeline):
    job_id = timeline["job_id"]
    assert rs.resolve_stage(db_session, "HM review", job_id=job_id)[0] == ["hm_review"]
    assert rs.resolve_stage(db_session, "technical", job_id=job_id)[0] == ["technical_written", "technical_interview"]
    assert rs.resolve_stage(db_session, "screening", job_id=job_id)[0] == ["hm_review"]
    keys, stages = rs.resolve_stage(db_session, "astrology", job_id=job_id)
    assert keys == [] and "Resume submitted" in stages.values()


def test_get_job_pipeline_tool(tools, timeline):
    out = _run(tools["get_job_pipeline"].run(job=JOB_TITLE))
    assert (out["job_id"], out["job_title"]) == (timeline["job_id"], JOB_TITLE)
    assert out["in_progress"] == 2
    assert out["stage_counts"] == {"Hiring manager review": 1, "Technical assessment": 1}
    assert out["outcomes"] == {"hired": 1, "rejected": 1, "declined": 0, "withdrawn": 0}
    hm = next(s for s in out["stages"] if s["stage"] == "Hiring manager review")
    assert [c["id"] for c in hm["candidates"]] == [IDS["B"]]


def test_get_job_pipeline_tool_unknown_job(tools):
    out = _run(tools["get_job_pipeline"].run(job="zzz-not-a-job-zzz"))
    assert "error" in out and isinstance(out["open_jobs"], list)


def test_find_candidates_at_stage_tool(tools):
    out = _run(tools["find_candidates_at_stage"].run(stage="technical assessment", job=JOB_TITLE))
    assert out["stages_matched"] == ["Technical assessment"]
    assert out["count"] == 1 and out["candidates"][0]["id"] == IDS["A"]

    interviewing = _run(tools["find_candidates_at_stage"].run(stage="interviewing", job=JOB_TITLE))
    assert "Technical interview" in interviewing["stages_matched"]
    assert [c["id"] for c in interviewing["candidates"]] == [IDS["A"]]


def test_find_candidates_at_an_unknown_stage(tools):
    out = _run(tools["find_candidates_at_stage"].run(stage="astrology"))
    assert "error" in out
    assert "Resume submitted" in out["stages"]
    assert "astrology" in out["note"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_reports.py -q -k "stage or tool"`
Expected: failures with `AttributeError` (no `normalize_stage_text`) and `KeyError: 'get_job_pipeline'`

- [ ] **Step 3: Add stage resolution and per-stage listings to the service**

Append to `backend/services/reports_service.py`:

```python
# The candidate-status words from spec 3.3, which people also use for stages.
STAGE_ALIASES = {
    "new": ("resume_submitted",),
    "applied": ("resume_submitted",),
    "screening": ("hm_review",),
    "interview": ("technical_written", "technical_interview", "problem_solving", "case_study", "hr_screen"),
    "interviewing": ("technical_written", "technical_interview", "problem_solving", "case_study", "hr_screen"),
    "interviews": ("technical_written", "technical_interview", "problem_solving", "case_study", "hr_screen"),
    "offered": ("offer", "offer_accepted"),
}


def normalize_stage_text(text: str) -> str:
    """'the HM-review stage' -> 'hm review'. Keys and names normalize the same way."""
    value = re.sub(r"[\s_\-]+", " ", str(text or "").lower()).strip()
    value = re.sub(r"^the ", "", value)
    value = re.sub(r" (stage|round|step)$", "", value)
    return value.strip()


def resolve_stage(db: Session, text: str, job_id: Optional[int] = None) -> tuple[list[str], dict]:
    """Map what someone typed to round keys.

    Returns (matched keys in pipeline order, every round key -> name). An
    alias wins, then an exact key or name, then every round whose key or
    name contains the words ("technical" matches both technical rounds).
    """
    query = db.query(PipelineStage.key, func.min(PipelineStage.name), func.min(PipelineStage.position)).filter(
        PipelineStage.kind == ps.ROUND
    )
    if job_id is not None:
        query = query.filter(PipelineStage.job_id == job_id)
    rows = query.group_by(PipelineStage.key).order_by(func.min(PipelineStage.position), PipelineStage.key).all()
    stages = {
        key: (_DEFAULT_NAMES.get(key, name) if job_id is None else name) for key, name, _position in rows
    }
    wanted = normalize_stage_text(text)
    if not wanted:
        return [], stages
    if wanted in STAGE_ALIASES:
        return [key for key in STAGE_ALIASES[wanted] if key in stages], stages
    exact = [
        key
        for key, name in stages.items()
        if wanted in (normalize_stage_text(key), normalize_stage_text(name))
    ]
    if exact:
        return exact, stages
    return [
        key
        for key, name in stages.items()
        if wanted in normalize_stage_text(name) or wanted in normalize_stage_text(key)
    ], stages


def candidates_at_stage(
    db: Session, keys: list[str], scope: Scope, now: datetime, limit: int = 25
) -> tuple[list[dict], int]:
    """Active applications in progress at any of `keys`, longest wait first.

    Each entry carries id and name (the candidate) and job_id and job_title,
    the shapes the assistant's link checker reads.
    """
    query = (
        _stage_rows(
            db,
            ApplicationStage.started_at,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
            PipelineStage.name,
        )
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .filter(
            PipelineStage.key.in_(keys),
            ApplicationStage.status == ps.IN_PROGRESS,
            JobApplication.status == ps.APP_ACTIVE,
        )
    )
    query = _scoped(query, scope)
    total = query.count()
    rows = (
        query.order_by(ApplicationStage.started_at.asc().nulls_last(), Candidate.last_name, Candidate.first_name)
        .limit(limit)
        .all()
    )
    return (
        [
            {
                "id": candidate_id,
                "name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_name": stage_name,
                "days_at_stage": (now - started).days if started else None,
            }
            for started, candidate_id, first, last, job_id, job_title, stage_name in rows
        ],
        total,
    )


def job_pipeline_state(
    db: Session,
    job_id: int,
    now: datetime,
    candidate_ids: Optional[Iterable[str]] = None,
    per_stage: int = 10,
) -> dict:
    """Who is at each enabled round of one job, plus outcome counts."""
    scope = Scope.of(job_id=job_id, candidate_ids=candidate_ids)
    rounds = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.job_id == job_id,
            PipelineStage.kind == ps.ROUND,
            PipelineStage.enabled.is_(True),
        )
        .order_by(PipelineStage.position)
        .all()
    )
    stages = []
    for stage in rounds:
        people, total = candidates_at_stage(db, [stage.key], scope, now, limit=per_stage)
        stages.append(
            {
                "stage": stage.name,
                "count": total,
                "candidates": [
                    {"id": p["id"], "name": p["name"], "days_at_stage": p["days_at_stage"]} for p in people
                ],
            }
        )
    status_counts = dict(
        _scoped(db.query(JobApplication.status, func.count(JobApplication.id)), scope)
        .group_by(JobApplication.status)
        .all()
    )
    _waiting, waiting_total = no_movement(db, scope, now, limit=1)
    in_progress = sum(s["count"] for s in stages)
    return {
        "in_progress": in_progress,
        # `count` too, so the golden replay's outcome check reads an empty
        # pipeline the same way it reads an empty search.
        "count": in_progress,
        "stage_counts": {s["stage"]: s["count"] for s in stages if s["count"]},
        "stages": stages,
        "outcomes": {
            status: status_counts.get(status, 0)
            for status in (ps.APP_HIRED, ps.APP_REJECTED, ps.APP_DECLINED, ps.APP_WITHDRAWN)
        },
        "no_movement_7_days": waiting_total,
    }
```

- [ ] **Step 4: Make sure the tool builder knows the viewer**

Open `backend/services/assistant_tools.py`. If `build_assistant_tools` already takes `user` (Phase B), skip to Step 5. Otherwise change its signature to

```python
def build_assistant_tools(db: Session, user=None) -> List[Tool]:
    """Build the tool set bound to this request's DB session and viewer.

    `user` is None for the golden replay and the hygiene checks; the chat
    endpoints pass the signed-in user so the pipeline tools only count the
    candidates that viewer may see.
    """
```

and in `backend/routers/assistant.py`, in both `chat_with_assistant` and `chat_with_assistant_streaming`, add a dependency parameter `user: Optional[User] = Depends(get_optional_user)` (import `get_optional_user` from `..utils.auth`, `User` from `..models.models`, and `Optional` from `typing` if absent), and change both `tools=build_assistant_tools(db)` calls to `tools=build_assistant_tools(db, user)`.

- [ ] **Step 5: Add the tools**

In `backend/services/assistant_tools.py`, add these module-level note helpers directly after `partial_match_note`:

```python
def unknown_stage_note(stage: str) -> str:
    return f"There is no stage called {stage!r} in this ATS. The stages it has are listed in stages."


def nobody_at_stage_note(stage_names: List[str]) -> str:
    return f"Nobody is at {' or '.join(stage_names)} right now."


def more_at_stage_note(total: int, shown: int) -> str:
    return f"{total} people are at this stage. The {shown} who have waited longest are listed."
```

Inside `build_assistant_tools`, directly before `return [`, add:

```python
    def _visible_ids():
        if user is None:
            return None
        from backend.services.access_service import visible_candidate_ids

        return visible_candidate_ids(db, user)

    async def get_job_pipeline(job: str) -> dict:
        from datetime import datetime

        from backend.models.models import JobApplication
        from backend.services import pipeline_service as ps
        from backend.services import reports_service as rs

        job_info = await get_job(job)
        if "error" in job_info:
            return job_info
        # The same lazy repair the job page board does, so an application
        # created by older code still appears. Flushed only: a read tool
        # never commits.
        for application in db.query(JobApplication).filter(JobApplication.job_id == job_info["id"]).all():
            ps.ensure_application_stages(db, application)
        state = rs.job_pipeline_state(db, job_info["id"], datetime.utcnow(), candidate_ids=_visible_ids())
        out = {"job_id": job_info["id"], "job_title": job_info["title"], **state}
        if job_info.get("matched_by") == "semantic":
            out["requested_title"] = job_info["requested_title"]
            out["note"] = job_info["note"]
        elif state["count"] == 0 and not any(state["outcomes"].values()):
            out["note"] = f"Nobody is in the pipeline for {job_info['title']} yet."
        return out

    async def find_candidates_at_stage(stage: str, job: Optional[str] = None, limit: int = 15) -> dict:
        from datetime import datetime

        from backend.services import reports_service as rs

        limit = clamp_limit(limit, default=15)
        job_id = job_title = None
        if job:
            job_info = await get_job(job)
            if "error" in job_info:
                return job_info
            job_id, job_title = job_info["id"], job_info["title"]
        keys, stages = rs.resolve_stage(db, stage, job_id=job_id)
        if not keys:
            return {
                "error": f"No stage called {stage!r}",
                "stages": list(stages.values()),
                "note": unknown_stage_note(stage),
            }
        matched = [stages[key] for key in keys]
        scope = rs.Scope.of(job_id=job_id, candidate_ids=_visible_ids())
        people, total = rs.candidates_at_stage(db, keys, scope, datetime.utcnow(), limit=limit)
        out = {"stage_query": stage, "stages_matched": matched, "count": total, "candidates": people}
        if job_id is not None:
            out["job_id"] = job_id
            out["job_title"] = job_title
        if total == 0:
            out["note"] = nobody_at_stage_note(matched)
        elif total > len(people):
            out["note"] = more_at_stage_note(total, len(people))
        return out
```

Add two entries to the returned list, after the `list_pipeline` Tool:

```python
        Tool(
            name="get_job_pipeline",
            description=(
                "Show where every candidate for one job stands in the hiring process: how many "
                "are at each stage with their names (longest waiting first), how many were hired, "
                "rejected, declined, or withdrew, and how many have had no movement in 7+ days. "
                "Call this for 'where is everyone for X', 'how is the X job going', or 'who is in "
                "the pipeline for X'. An error result means the job was not found: say so and "
                "offer the titles it lists."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "job": {"type": "string", "description": "Job id or title"},
                },
                "required": ["job"],
            },
            run=get_job_pipeline,
        ),
        Tool(
            name="find_candidates_at_stage",
            description=(
                "List the candidates who are at a hiring stage right now, longest waiting first, "
                "across every job or for one job. Call this for 'who is at the HR screen', 'who is "
                "waiting on hiring manager review for X', or 'who is interviewing'. Pass the stage "
                "in the user's own words; stages_matched names the stages it found. An error "
                "result lists the real stage names in stages: offer those."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "The stage in the user's words, e.g. 'HR screen' or 'interviewing'"},
                    "job": {"type": "string", "description": "Optional job id or title to limit the list to one job"},
                    "limit": {"type": "integer", "description": "Max candidates (default 15)"},
                },
                "required": ["stage"],
            },
            run=find_candidates_at_stage,
        ),
```

Change the `list_pipeline` description to:

```python
            description=(
                "Summarize the recruiting pipeline: candidate counts by status, top applied-for "
                "positions, open job count. Call this for 'how many candidates/jobs', pipeline "
                "health, or breakdown questions. For where candidates stand in one job's stages, "
                "use get_job_pipeline; for who is at a named stage, use find_candidates_at_stage."
            ),
```

- [ ] **Step 6: Add the golden cases**

The golden test fails when a tool has no golden question (`test_golden_set_covers_every_tool`). In `evals/assistant_golden.json`, add these two objects to the end of the `cases` array:

```json
    {
      "id": "job-pipeline",
      "question": "Where is everyone in the hiring process for {{cast:job}}?",
      "expected_tools": ["get_job_pipeline"],
      "checks": {
        "numbers_from_results": true,
        "require_link": true,
        "must_mention": ["{{cast:job}}"]
      },
      "replay": {
        "calls": [{"tool": "get_job_pipeline", "arguments": {"job": "{{cast:job}}"}}],
        "reply": {
          "default": "{{link:job:{{cast:job}}}} has {{value:in_progress}} people in progress. By stage: {{dict:stage_counts}}.",
          "empty": "Nobody is in progress for {{link:job:{{cast:job}}}} right now."
        }
      }
    },
    {
      "id": "who-at-stage",
      "question": "Who is at the resume submitted stage right now?",
      "expected_tools": ["find_candidates_at_stage"],
      "checks": {"numbers_from_results": true},
      "replay": {
        "calls": [{"tool": "find_candidates_at_stage", "arguments": {"stage": "resume submitted"}}],
        "reply": {
          "default": "{{value:count}} people are at {{list:stages_matched}}, including {{links:candidates}}.",
          "empty": "Nobody is at {{list:stages_matched}} right now."
        }
      }
    }
```

In `backend/tests/test_assistant_golden.py`, extend the imports from `backend.services.assistant_tools` with `more_at_stage_note, nobody_at_stage_note, unknown_stage_note`, and add three entries to `TestPromptHygiene.NOTES`:

```python
        unknown_stage_note("astrology"),
        nobody_at_stage_note(["Offer", "Offer accepted"]),
        more_at_stage_note(40, 15),
```

- [ ] **Step 7: Run the tests**

Run: `poetry run pytest backend/tests/test_reports.py backend/tests/test_assistant_golden.py -q`
Expected: all pass (test_reports 43; the golden file gains 2 replay cases, 2 safety cases, and the coverage check passes)

- [ ] **Step 8: Export OpenAPI only if a route changed**

If Step 4 changed `backend/routers/assistant.py`, the new `user` dependency does not add a parameter to the schema (it reads the Authorization header), but run the check to be sure:

```powershell
poetry run python scripts/export_openapi.py --check
```

Expected: up to date. If it is not, run the export and `npm run types:api` and add both files to the commit.

- [ ] **Step 9: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d9.txt`:

```
feat: assistant tools for a job's pipeline and who is at a stage

get_job_pipeline and find_candidates_at_stage answer "where is everyone
for X" and "who is at the HR screen" from the same service the Reports
page uses. Stage words are resolved in the tool (aliases from the
candidate statuses, exact names, then partial words), never by a second
model call, and every note reads as a sentence a visitor could see.
Both tools have golden replay cases and their notes are in the hygiene
check.
```

```powershell
git add backend/services/reports_service.py backend/services/assistant_tools.py backend/routers/assistant.py evals/assistant_golden.json backend/tests/test_assistant_golden.py backend/tests/test_reports.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d9.txt
```

(`git add` of an unchanged `backend/routers/assistant.py` is a harmless no-op.)

---

### Task 10: Seed data with realistic stage timestamps

**Files:**
- Modify: `scripts/seed_demo.py` (`seed_candidates` status loop, new `stage_timeline` and `_spread_stage_timeline`, `seed_pipeline`)
- Modify: `backend/tests/test_seed_demo.py`

Why: the Phase A seed and migration wrote every started and completed time as the application's `applied_at`. Time in stage would be empty (zero-length rows are excluded on purpose) and, a week after seeding, every active candidate would sit on the "No movement" list. This task lays out believable durations once, deterministically, and never touches a row a person has moved.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_seed_demo.py`:

```python
from datetime import datetime, timedelta

from scripts.seed_demo import stage_timeline

NOW = datetime(2026, 3, 15, 12, 0, 0)

ROUNDS = [
    "resume_submitted",
    "hm_review",
    "technical_written",
    "technical_interview",
    "problem_solving",
    "case_study",
    "hr_screen",
    "offer",
    "offer_accepted",
]


def _rows(statuses, outcomes=("pending", "pending")):
    rows = [(key, "round", status) for key, status in zip(ROUNDS, statuses)]
    return rows + [("offer_declined", "outcome", outcomes[0]), ("hired", "outcome", outcomes[1])]


def test_timeline_for_an_active_application_is_contiguous():
    rows = _rows(["passed", "passed", "in_progress"] + ["pending"] * 6)
    applied, spans = stage_timeline("cand-1:7", rows, NOW)
    (s0, c0), (s1, c1), (s2, c2) = spans[:3]
    assert applied < s0 < c0 == s1 < c1 == s2 < NOW
    assert c2 is None
    assert all(span == (None, None) for span in spans[3:])


def test_timeline_for_a_rejected_application():
    rows = _rows(["passed", "failed"] + ["skipped"] * 7, outcomes=("skipped", "skipped"))
    applied, spans = stage_timeline("cand-2:7", rows, NOW)
    end = spans[1][1]
    assert spans[0][1] == spans[1][0]
    assert end <= NOW - timedelta(days=2)
    # Skipped rows never started; they ended when the application did.
    assert all(span == (None, end) for span in spans[2:])


def test_timeline_for_a_hire_ends_on_the_outcome():
    rows = _rows(["passed"] * 9, outcomes=("skipped", "passed"))
    applied, spans = stage_timeline("cand-3:7", rows, NOW)
    end = spans[8][1]
    assert spans[10] == (end, end)  # Hired
    assert spans[9] == (None, end)  # Offer declined, skipped
    for earlier, later in zip(spans[:8], spans[1:9]):
        assert earlier[1] == later[0]


def test_timeline_is_deterministic_and_varies_by_application():
    rows = _rows(["passed", "in_progress"] + ["pending"] * 7)
    assert stage_timeline("cand-4:7", rows, NOW) == stage_timeline("cand-4:7", rows, NOW)
    starts = {stage_timeline(f"cand-{i}:7", rows, NOW)[1][1][0] for i in range(20)}
    assert len(starts) > 1


def test_some_active_applications_have_not_moved_in_a_week():
    rows = _rows(["in_progress"] + ["pending"] * 8)
    waits = [(NOW - stage_timeline(f"c{i}:1", rows, NOW)[1][0][0]).days for i in range(200)]
    assert any(w >= 8 for w in waits) and any(w < 7 for w in waits)
    assert max(waits) <= 14


def test_nothing_reached_means_nothing_to_lay_out():
    applied, spans = stage_timeline("cand-5:7", _rows(["pending"] * 9), NOW)
    assert applied is None


def test_spread_rewrites_flat_rows_once_and_never_touches_moved_ones(db_session, seed):
    from backend.models.models import Job, JobApplication
    from backend.services import pipeline_service as ps
    from scripts.seed_demo import _spread_stage_timeline

    job = Job(
        title="Seed Spread Test Role",
        department="QA",
        job_overview="Exists to test the seed's timestamp layout.",
        required_qualifications="None",
        location="Remote",
        location_type="remote",
        job_type="full_time",
        experience_level="mid",
        status="open",
        job_metadata={},
        views=0,
        applications=0,
    )
    db_session.add(job)
    db_session.flush()
    flat_at = datetime(2025, 3, 1, 9, 0, 0)
    apps = []
    for candidate_id in (seed["candidate_ids"][1], seed["candidate_ids"][2]):
        app = JobApplication(job_id=job.id, candidate_id=candidate_id, status="active", applied_at=flat_at, source="direct")
        db_session.add(app)
        db_session.flush()
        ps.ensure_application_stages(db_session, app)
        apps.append(app)
    flat, moved = apps
    ps.advance(db_session, moved)  # a person moved this one: real timestamps now

    when = datetime(2025, 6, 1, 12, 0, 0)
    assert _spread_stage_timeline(db_session, flat, when) is True
    db_session.flush()
    first = sorted(flat.stages, key=lambda r: r.stage.position)[0]
    assert first.started_at > flat.applied_at
    snapshot = sorted((r.stage_id, r.started_at, r.completed_at) for r in flat.stages) + [flat.applied_at]

    assert _spread_stage_timeline(db_session, flat, when) is False
    assert sorted((r.stage_id, r.started_at, r.completed_at) for r in flat.stages) + [flat.applied_at] == snapshot

    before = sorted((r.stage_id, r.started_at, r.completed_at) for r in moved.stages)
    assert _spread_stage_timeline(db_session, moved, when) is False
    assert sorted((r.stage_id, r.started_at, r.completed_at) for r in moved.stages) == before

    db_session.delete(job)
    db_session.commit()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_seed_demo.py -q`
Expected: FAIL with `ImportError: cannot import name 'stage_timeline'`

- [ ] **Step 3: Write the timeline layout**

In `scripts/seed_demo.py`, add `from datetime import datetime, timedelta` to the imports and `PipelineStage` to the models import list. Add these two functions directly above `seed_pipeline`:

```python
def stage_timeline(seed_key: str, rows: list[tuple[str, str, str]], now: datetime):
    """Believable, deterministic timestamps for one seeded application.

    rows: (stage key, stage kind, status) in pipeline order. Returns
    (applied_at, [(started_at, completed_at), ...]) aligned with rows, or
    (None, ...) when nothing was ever reached.

    The application's latest moment is anchored to `now`: the stage it is
    waiting at started 1 to 5 days ago (about a quarter of the time, 8 to 13
    days ago, so "No movement in 7+ days" has honest entries), or, for a
    finished application, its outcome landed 2 to 76 days ago. Earlier rounds
    are laid out backwards from there, each lasting 1 to 6 days plus some
    hours, ending exactly when the next began. Every number comes from
    stable_index, so the same application gets the same shape every run.
    """
    spans: list[tuple] = [(None, None)] * len(rows)
    worked = [
        i
        for i, (_key, kind, status) in enumerate(rows)
        if kind == "round" and status in ("passed", "failed", "in_progress")
    ]
    if not worked:
        return None, spans
    current = next((i for i in worked if rows[i][2] == "in_progress"), None)
    hours = timedelta(hours=stable_index(f"hour-{seed_key}", 9))
    if current is not None:
        if stable_index(f"stuck-{seed_key}", 4) == 0:
            wait = timedelta(days=8 + stable_index(f"wait-{seed_key}", 6))
        else:
            wait = timedelta(days=1 + stable_index(f"wait-{seed_key}", 5))
        anchor = now - wait - hours
    else:
        anchor = now - timedelta(days=2 + stable_index(f"end-{seed_key}", 75)) - hours

    spans = list(spans)
    boundary = anchor
    for index in reversed(worked):
        if index == current:
            spans[index] = (anchor, None)
            continue
        key = rows[index][0]
        duration = timedelta(
            days=1 + stable_index(f"{seed_key}:{key}", 6),
            hours=stable_index(f"{seed_key}:{key}:h", 20),
        )
        spans[index] = (boundary - duration, boundary)
        boundary -= duration

    for index, (_key, kind, status) in enumerate(rows):
        if kind == "outcome" and status == "passed":
            spans[index] = (anchor, anchor)
        elif status == "skipped":
            later = [spans[i][0] for i in worked if i > index]
            spans[index] = (None, later[0] if later else anchor)

    applied_at = spans[worked[0]][0] - timedelta(hours=1 + stable_index(f"applied-{seed_key}", 5))
    return applied_at, spans


def _spread_stage_timeline(db, application: JobApplication, now: datetime) -> bool:
    """Give one seeded application realistic stage timestamps, once.

    Only touches an application whose rows still carry the flat timestamps
    _seed_stage_history and the Phase A migration wrote: every started or
    completed time equal to applied_at. Anything a person has moved has real
    timestamps and is left exactly as it is. A spread application starts its
    first stage an hour or more after applied_at, so it is no longer flat and
    a re-run is a no-op.
    """
    if application.applied_at is None:
        return False
    rows = (
        db.query(ApplicationStage, PipelineStage)
        .join(PipelineStage, PipelineStage.id == ApplicationStage.stage_id)
        .filter(ApplicationStage.application_id == application.id)
        .order_by(PipelineStage.position)
        .all()
    )
    touched = [row for row, _stage in rows if row.status != "pending"]
    if not touched:
        return False
    flat_values = (None, application.applied_at)
    if not all(row.started_at in flat_values and row.completed_at in flat_values for row in touched):
        return False
    applied_at, spans = stage_timeline(
        f"{application.candidate_id}:{application.job_id}",
        [(stage.key, stage.kind, row.status) for row, stage in rows],
        now,
    )
    if applied_at is None:
        return False
    for (row, _stage), (started, completed) in zip(rows, spans):
        row.started_at = started
        row.completed_at = completed
    application.applied_at = applied_at
    return True
```

- [ ] **Step 4: Call it from `seed_pipeline`**

In `seed_pipeline`, add `now = datetime.utcnow()` and `spread = 0` as the first two lines of the function body, and replace

```python
        db.flush()
        _seed_stage_history(db, application, candidate.status or "active")
```

with

```python
        db.flush()
        _seed_stage_history(db, application, candidate.status or "active")
        db.flush()
        spread += _spread_stage_timeline(db, application, now)
```

At the end of `seed_pipeline`, after the final `db.commit()`, add:

```python
    print(f"  stage timelines laid out: {spread}")
```

- [ ] **Step 5: Stop reassigning statuses of candidates already on a pipeline**

In `seed_candidates`, replace the block

```python
    candidates = db.query(Candidate).order_by(Candidate.created_at, Candidate.id).all()
    funnel_rng = random.Random(SEED_FUNNEL)
    for candidate, status in zip(candidates, _weighted_statuses(funnel_rng, len(candidates))):
        if not candidate.status or candidate.status == "active":
            candidate.status = status
    db.commit()
```

with

```python
    candidates = db.query(Candidate).order_by(Candidate.created_at, Candidate.id).all()
    # A candidate on a pipeline gets their status from it (pipeline_service
    # keeps it in sync). Reassigning it here would contradict their board,
    # and the draw shifts for everyone whenever a candidate is added (Phase C
    # added Add candidate and upload intake), so only people with no stage
    # history yet are given a funnel position.
    on_a_pipeline = {
        candidate_id
        for (candidate_id,) in db.query(JobApplication.candidate_id)
        .join(ApplicationStage, ApplicationStage.application_id == JobApplication.id)
        .distinct()
    }
    funnel_rng = random.Random(SEED_FUNNEL)
    for candidate, status in zip(candidates, _weighted_statuses(funnel_rng, len(candidates))):
        if candidate.id in on_a_pipeline:
            continue
        if not candidate.status or candidate.status == "active":
            candidate.status = status
    db.commit()
```

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_seed_demo.py -q`
Expected: all pass (5 existing + 7 new)

- [ ] **Step 7: Verify on a scratch database**

```powershell
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
poetry run python scripts/seed_demo.py --no-embeddings
docker exec recruitiq-db psql -U admin -d st_scratch -t -c "SELECT md5(string_agg(application_id||':'||stage_id||':'||status||':'||coalesce(started_at::text,'-')||':'||coalesce(completed_at::text,'-'), ',' ORDER BY id)) FROM application_stages"
poetry run python scripts/seed_demo.py --no-embeddings
docker exec recruitiq-db psql -U admin -d st_scratch -t -c "SELECT md5(string_agg(application_id||':'||stage_id||':'||status||':'||coalesce(started_at::text,'-')||':'||coalesce(completed_at::text,'-'), ',' ORDER BY id)) FROM application_stages"
docker exec recruitiq-db psql -U admin -d st_scratch -c "SELECT s.key, COUNT(*), ROUND(AVG(EXTRACT(EPOCH FROM a.completed_at - a.started_at)/86400)::numeric, 1) AS avg_days FROM application_stages a JOIN pipeline_stages s ON s.id = a.stage_id WHERE a.status IN ('passed','failed') AND a.completed_at > a.started_at GROUP BY s.key, s.position ORDER BY s.position"
docker exec recruitiq-db psql -U admin -d st_scratch -c "SELECT COUNT(*) AS waiting_7_plus FROM application_stages a JOIN job_applications j ON j.id = a.application_id WHERE a.status = 'in_progress' AND j.status = 'active' AND a.started_at < now() at time zone 'utc' - interval '7 days'"
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
```

Expected: the first run prints `stage timelines laid out: 40`, the second `0`; both md5 lines are identical; durations average between 1 and 7 days per round; `waiting_7_plus` is a minority of the active applications (roughly a quarter), not zero and not all.

- [ ] **Step 8: Verify a clicked board survives a re-run on the dev database**

```powershell
poetry run python scripts/seed_demo.py --no-embeddings
```

Expected on the first dev run: `stage timelines laid out:` close to the number of seeded applications nobody has clicked (dev rows written by the Phase A migration are flat too).

Then start the backend (`cd backend; poetry run python -m uvicorn main:app --port 8010`), take an admin token (as in Phase A's live check: a short script in the scratchpad that prints `create_access_token` for the dev admin), and on one seeded application at Resume submitted:

```bash
curl -s -X POST -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" -d '{}' localhost:8010/api/applications/<id>/advance
curl -s localhost:8010/api/applications/<id> | python -c "import sys,json; d=json.load(sys.stdin); print(d['current_stage_key'], [(s['key'], s['started_at'], s['completed_at']) for s in d['stages'][:3]])"
```

Run `poetry run python scripts/seed_demo.py --no-embeddings` again and repeat the second `curl`. Expected: identical output both times (`hm_review` current, same timestamps), and the candidate's `status` from `GET /api/candidates/<candidate id>` is still `screening`. Put that application back afterwards the way Phase A did (reset its rows with SQL, candidate status `active`).

- [ ] **Step 9: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d10.txt`:

```
feat: seed lays out realistic, deterministic stage timestamps

The original seed and the Phase A backfill stamped every stage with the
application date, so time in stage was empty and, a week later, every
active candidate looked stuck. Flat applications now get contiguous
rounds of 1 to 6 days anchored to the seed run, about a quarter waiting
8 to 13 days, finished ones ending 2 to 76 days back. Anything a person
has moved keeps its real timestamps, and a re-run is a no-op.

Also stops the seed reassigning the status of candidates who are already
on a pipeline: the weighted draw shifts whenever a candidate is added,
which would contradict their board.

Verified: unit tests for the layout and its idempotency; a scratch
database seeded twice gives byte-identical stage history; on dev a
clicked application kept its stage and timestamps across a re-run.
```

```powershell
git add scripts/seed_demo.py backend/tests/test_seed_demo.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d10.txt
```

---

### Task 11: Web types, data helpers, and pure report helpers

**Files:**
- Modify: `web/src/lib/domain.ts`
- Modify: `web/src/lib/data.ts`
- Create: `web/src/lib/reports.ts`
- Test: `web/src/lib/reports.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/reports.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  CANDIDATE_EXPORT_PATH,
  activityPredicate,
  canViewReports,
  daysLabel,
  exportHref,
  formatDays,
  formatShare,
  funnelWidth,
} from "./reports";

describe("formatDays", () => {
  it("says so when nothing has finished", () => {
    expect(formatDays(null)).toBe("No completed stages yet");
    expect(formatDays(undefined)).toBe("No completed stages yet");
  });

  it("rounds short medians to a tenth and long ones to whole days", () => {
    expect(formatDays(0.4)).toBe("Under a day");
    expect(formatDays(1)).toBe("1 day");
    expect(formatDays(2.46)).toBe("2.5 days");
    expect(formatDays(12.6)).toBe("13 days");
  });
});

describe("small formatters", () => {
  it("formats shares, day counts, and bar widths", () => {
    expect(formatShare(0.5)).toBe("50%");
    expect(formatShare(0)).toBe("0%");
    expect(daysLabel(1)).toBe("1 day");
    expect(daysLabel(16)).toBe("16 days");
    expect(funnelWidth(5, 10)).toBe("50%");
    expect(funnelWidth(3, 0)).toBe("0%");
  });
});

describe("exportHref", () => {
  it("passes the job filter through to the CSV export", () => {
    expect(exportHref()).toBe(CANDIDATE_EXPORT_PATH);
    expect(exportHref(7)).toBe(`${CANDIDATE_EXPORT_PATH}?job_id=7`);
  });
});

describe("activityPredicate", () => {
  const base = { job_title: "Data Engineer", stage_name: "HR screen" };

  it("reads as plain English for every kind", () => {
    expect(activityPredicate({ ...base, kind: "applied", stage_name: null })).toBe(
      "applied to Data Engineer",
    );
    expect(activityPredicate({ ...base, kind: "passed" })).toBe("passed HR screen for Data Engineer");
    expect(activityPredicate({ ...base, kind: "skipped" })).toBe(
      "skipped HR screen for Data Engineer",
    );
    expect(activityPredicate({ ...base, kind: "rejected" })).toBe(
      "was rejected at HR screen for Data Engineer",
    );
    expect(activityPredicate({ ...base, kind: "hired" })).toBe("was hired as Data Engineer");
    expect(activityPredicate({ ...base, kind: "declined" })).toBe(
      "declined the offer for Data Engineer",
    );
  });
});

describe("canViewReports", () => {
  it("lets the demo and the hiring roles in, and keeps interviewers out", () => {
    expect(canViewReports("demo")).toBe(true);
    expect(canViewReports("admin")).toBe(true);
    expect(canViewReports("hiring_manager")).toBe(true);
    expect(canViewReports("hiring_team")).toBe(true);
    expect(canViewReports("interviewer")).toBe(false);
    expect(canViewReports(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd web; npx vitest run src/lib/reports.test.ts`
Expected: FAIL, cannot resolve `./reports`

- [ ] **Step 3: Add the type aliases**

In `web/src/lib/domain.ts`, after the ATS Phase A aliases (`export type ApplicationStage = ...`), add:

```ts
/** ATS Phase D: the dashboard's pipeline cards and the Reports page. */
export type Dashboard = Schemas["DashboardResponse"];
export type Report = Schemas["ReportsResponse"];
export type FunnelRow = Schemas["FunnelRow"];
export type StageTiming = Schemas["StageTiming"];
export type WaitingApplication = Schemas["WaitingApplication"];
export type PendingFeedbackRow = Schemas["PendingFeedbackRow"];
export type ActivityEvent = Schemas["ActivityEvent"];
export type SourceRow = Schemas["SourceRow"];
export type QuarterOutcomes = Schemas["QuarterOutcomes"];
```

- [ ] **Step 4: Write the pure helpers**

Create `web/src/lib/reports.ts`. If Task 1 found the export route at a different path, use that path for `CANDIDATE_EXPORT_PATH`.

```ts
/**
 * Wording, visibility, and small arithmetic for the dashboard and Reports.
 *
 * Pure so it can be unit tested without rendering. Every number handed to
 * these functions came from a query in reports_service.py; nothing here
 * invents one.
 */
import type { ActivityEvent } from "./domain";
import { can, REPORTS_VIEW } from "./permissions";
import type { Role } from "./session";

/** Phase C's CSV export route handler. Reports links to it rather than exporting twice. */
export const CANDIDATE_EXPORT_PATH = "/api/candidates/export";

/**
 * Reports are for the hiring roles, and for the read-only demo so a visitor
 * sees every screen. Interviewers are out: they work from their own list.
 */
export function canViewReports(role: Role | null | undefined): boolean {
  if (!role) return false;
  return role === "demo" || can(role, REPORTS_VIEW);
}

export function formatDays(days: number | null | undefined): string {
  if (days === null || days === undefined) return "No completed stages yet";
  if (days < 1) return "Under a day";
  const rounded = days < 10 ? Math.round(days * 10) / 10 : Math.round(days);
  return `${rounded} ${rounded === 1 ? "day" : "days"}`;
}

export function formatShare(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function daysLabel(days: number): string {
  return days === 1 ? "1 day" : `${days} days`;
}

export function funnelWidth(value: number, largest: number): string {
  return `${largest > 0 ? (value / largest) * 100 : 0}%`;
}

export function exportHref(jobId?: number | null): string {
  return jobId ? `${CANDIDATE_EXPORT_PATH}?job_id=${jobId}` : CANDIDATE_EXPORT_PATH;
}

/** The part of an activity line after the candidate's name. */
export function activityPredicate(
  event: Pick<ActivityEvent, "kind" | "job_title"> & { stage_name?: string | null },
): string {
  const stage = event.stage_name ?? "a stage";
  switch (event.kind) {
    case "applied":
      return `applied to ${event.job_title}`;
    case "passed":
      return `passed ${stage} for ${event.job_title}`;
    case "skipped":
      return `skipped ${stage} for ${event.job_title}`;
    case "rejected":
      return `was rejected at ${stage} for ${event.job_title}`;
    case "hired":
      return `was hired as ${event.job_title}`;
    case "declined":
      return `declined the offer for ${event.job_title}`;
    default:
      return `moved forward for ${event.job_title}`;
  }
}
```

- [ ] **Step 5: Add the data helpers and drop `countByStage`**

In `web/src/lib/data.ts`, add `Dashboard` and `Report` to the type import from `./domain`. Delete the `countByStage` function and its doc comment (the dashboard was its only caller; check with `Select-String -Path web/src -Pattern countByStage` after the next task, expected no matches). Append:

```ts
/** The dashboard's pipeline cards (ATS Phase D): funnel, attention list, activity. */
export async function getDashboard(): Promise<Dashboard> {
  return apiFetch<Dashboard>("/api/reports/dashboard", { token: await getToken() });
}

/**
 * Everything on the Reports page, for every job or one. Throws ApiError 403
 * for an interviewer; the page checks the role before calling.
 */
export async function getReport(jobId?: number): Promise<Report> {
  return apiFetch<Report>("/api/reports/summary", {
    token: await getToken(),
    query: { job_id: jobId },
  });
}
```

- [ ] **Step 6: Run the tests**

Run: `cd web; npx vitest run src/lib/reports.test.ts`
Expected: 6 tests pass. (`npm run typecheck` will fail until Task 12 replaces the dashboard's `countByStage` call; that is expected here.)

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d11.txt`:

```
feat(web): report types, data helpers, and wording helpers

Pure, tested helpers decide who sees Reports (hiring roles and the demo,
never interviewers) and how medians, shares, and activity read. The CSV
link reuses Phase C's export.
```

```powershell
git add web/src/lib/domain.ts web/src/lib/data.ts web/src/lib/reports.ts web/src/lib/reports.test.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d11.txt
```

---

### Task 12: Dashboard funnel, attention list, and activity

**Files:**
- Create: `web/src/components/stage-funnel.tsx`
- Create: `web/src/components/attention-list.tsx`
- Create: `web/src/components/activity-feed.tsx`
- Modify: `web/src/app/page.tsx`

- [ ] **Step 1: Write the funnel component**

Create `web/src/components/stage-funnel.tsx`:

```tsx
import type { FunnelRow } from "@/lib/domain";
import { formatShare, funnelWidth } from "@/lib/reports";

/**
 * Each round twice: how many applications ever reached it (light bar) and
 * how many are there right now (dark bar), on one shared scale. A stage
 * people move through quickly reads as a wide light bar with a thin dark one.
 * The numbers are printed beside the bars, so the bars can stay aria-hidden.
 */
export function StageFunnel({ rows, showShare = false }: { rows: FunnelRow[]; showShare?: boolean }) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No applications yet.</p>;
  }
  const largest = Math.max(1, ...rows.map((row) => row.ever_reached));

  return (
    <div className="space-y-3">
      <ul className="space-y-2.5">
        {rows.map((row) => (
          <li key={row.key} className="flex items-center gap-3">
            <span className="w-28 shrink-0 truncate text-sm text-slate-600 sm:w-40" title={row.name}>
              {row.name}
            </span>
            <span className="relative h-3 flex-1 overflow-hidden rounded-full bg-slate-100" aria-hidden>
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-indigo-200"
                style={{ width: funnelWidth(row.ever_reached, largest) }}
              />
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-indigo-600"
                style={{ width: funnelWidth(row.currently_here, largest) }}
              />
            </span>
            <span className="w-28 shrink-0 text-right text-xs text-slate-500 tabular-nums">
              <span className="font-medium text-slate-900">{row.currently_here}</span> here ·{" "}
              {row.ever_reached} reached
            </span>
            {showShare ? (
              <span className="w-10 shrink-0 text-right text-xs text-slate-500 tabular-nums">
                {formatShare(row.share_of_applicants)}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 rounded-full bg-indigo-600" aria-hidden />
          Here now
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 rounded-full bg-indigo-200" aria-hidden />
          Ever reached
        </span>
        {showShare ? <span>Percent is the share of all applicants who reached the stage.</span> : null}
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Write the attention list**

Create `web/src/components/attention-list.tsx`:

```tsx
import Link from "next/link";

import type { PendingFeedbackRow, WaitingApplication } from "@/lib/domain";
import { daysLabel } from "@/lib/reports";

/**
 * The two things that go quiet without anyone noticing: candidates who have
 * not moved in a week, and interviews nobody wrote feedback for.
 */
export function AttentionList({
  waiting,
  waitingTotal,
  pending,
  reportsHref,
}: {
  waiting: WaitingApplication[];
  waitingTotal: number;
  pending: PendingFeedbackRow[];
  reportsHref?: string;
}) {
  if (waiting.length === 0 && pending.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Nothing needs attention. Every active candidate moved in the last 7 days and no feedback is
        outstanding.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {waiting.length > 0 ? (
        <section>
          <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
            No movement in 7+ days ({waitingTotal})
          </h3>
          <ul className="divide-y divide-slate-100 text-sm">
            {waiting.map((row) => (
              <li
                key={row.application_id}
                className="flex items-baseline justify-between gap-3 py-2 first:pt-0"
              >
                <span className="min-w-0">
                  <Link href={`/candidates/${row.candidate_id}`} className="font-medium hover:underline">
                    {row.candidate_name}
                  </Link>
                  <span className="block truncate text-xs text-slate-500">
                    {row.stage_name} · {row.job_title}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-amber-700 tabular-nums">
                  {daysLabel(row.days_waiting)}
                </span>
              </li>
            ))}
          </ul>
          {reportsHref && waitingTotal > waiting.length ? (
            <Link href={reportsHref} className="mt-2 inline-block text-xs text-indigo-600 hover:underline">
              See all {waitingTotal} on Reports
            </Link>
          ) : null}
        </section>
      ) : null}

      {pending.length > 0 ? (
        <section>
          <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Feedback not yet submitted
          </h3>
          <ul className="divide-y divide-slate-100 text-sm">
            {pending.map((row) => (
              <li
                key={row.interview_id}
                className="flex items-baseline justify-between gap-3 py-2 first:pt-0"
              >
                <span className="min-w-0">
                  <Link href={`/candidates/${row.candidate_id}`} className="font-medium hover:underline">
                    {row.candidate_name}
                  </Link>
                  <span className="block truncate text-xs text-slate-500">
                    {row.stage_name} · {row.interviewer_name ?? "Unnamed interviewer"}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-slate-500 tabular-nums">
                  {daysLabel(row.days_pending)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 3: Write the activity feed**

Create `web/src/components/activity-feed.tsx`:

```tsx
import Link from "next/link";

import type { ActivityEvent } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { activityPredicate } from "@/lib/reports";

/** The latest pipeline moves, newest first, straight from the stage history. */
export function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-slate-500">No pipeline activity yet.</p>;
  }
  return (
    <ol className="space-y-3 text-sm">
      {events.map((event, index) => (
        <li
          key={`${event.at}-${event.candidate_id}-${event.kind}-${index}`}
          className="flex items-baseline justify-between gap-3"
        >
          <span className="min-w-0">
            <Link href={`/candidates/${event.candidate_id}`} className="font-medium hover:underline">
              {event.candidate_name}
            </Link>{" "}
            <span className="text-slate-600">{activityPredicate(event)}</span>
            {event.actor_name ? (
              <span className="block text-xs text-slate-400">by {event.actor_name}</span>
            ) : null}
          </span>
          <time dateTime={event.at} className="shrink-0 text-xs text-slate-400">
            {formatDate(event.at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 4: Rewire the dashboard**

Replace `web/src/app/page.tsx` with:

```tsx
import Link from "next/link";
import { Briefcase, TrendingUp, Users } from "lucide-react";

import { ActivityFeed } from "@/components/activity-feed";
import { AttentionList } from "@/components/attention-list";
import { DashboardIntro } from "@/components/dashboard-intro";
import { ErrorState } from "@/components/page-header";
import { StageBadge } from "@/components/stage-badge";
import { StageFunnel } from "@/components/stage-funnel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getDashboard, getSkillsBreakdown, listCandidates, listJobs } from "@/lib/data";
import { fullName } from "@/lib/domain";
import type { Dashboard } from "@/lib/domain";
import { canViewReports } from "@/lib/reports";
import { getUser } from "@/lib/session";

// The dashboard reads live counts; nothing here is safe to prerender.
export const dynamic = "force-dynamic";

function Stat({
  label,
  value,
  icon: Icon,
  tint,
}: {
  label: string;
  value: string | number;
  icon: typeof Users;
  tint: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-6">
        <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${tint}`}>
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        <span>
          <span className="block text-2xl font-semibold tabular-nums">{value}</span>
          <span className="block text-sm text-slate-500">{label}</span>
        </span>
      </CardContent>
    </Card>
  );
}

export default async function DashboardPage() {
  let candidates;
  let jobs;
  let skills: Record<string, number>;
  let dashboard: Dashboard;
  let user;

  try {
    // In parallel: the dashboard is the first paint a visitor sees, and
    // serialising these is the difference between a snappy load and a
    // noticeable one.
    [candidates, jobs, skills, dashboard, user] = await Promise.all([
      listCandidates({ pageSize: 12 }),
      listJobs(),
      getSkillsBreakdown(),
      getDashboard(),
      getUser(),
    ]);
  } catch (error) {
    return (
      <>
        <DashboardIntro />
        <ErrorState
          title="Could not load the dashboard"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  const topSkills = Object.entries(skills)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 12);
  const maxSkill = Math.max(1, ...topSkills.map(([, n]) => n));

  const openJobs = jobs.results.filter((j) => j.status === "open").length;
  const recent = [...candidates.results]
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    .slice(0, 6);

  return (
    <>
      <DashboardIntro />

      {/* An h2, not PageHeader: the intro above owns the page's h1. */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold tracking-tight text-slate-900">Dashboard</h2>
        <p className="mt-1 text-sm text-slate-600">
          Live counts from the database. Every number below is a query over candidates,
          applications, and their stage history, not a fixture.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Candidates"
          value={candidates.total}
          icon={Users}
          tint="bg-indigo-50 text-indigo-600"
        />
        <Stat
          label="Open roles"
          value={openJobs}
          icon={Briefcase}
          tint="bg-emerald-50 text-emerald-600"
        />
        <Stat
          label="In interview or later"
          value={dashboard.interviewing_or_later}
          icon={TrendingUp}
          tint="bg-violet-50 text-violet-600"
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <StageFunnel rows={dashboard.funnel} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Needs attention</CardTitle>
          </CardHeader>
          <CardContent>
            <AttentionList
              waiting={dashboard.no_movement}
              waitingTotal={dashboard.no_movement_total}
              pending={dashboard.pending_feedback}
              reportsHref={canViewReports(user?.role) ? "/reports" : undefined}
            />
          </CardContent>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            <ActivityFeed events={dashboard.activity} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            {/* This widget answered 404 for its entire existence before Phase 3a
                moved the route above /{candidate_id}. */}
            <CardTitle>Top skills</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {topSkills.length === 0 ? (
              <p className="text-sm text-slate-500">No skills recorded yet.</p>
            ) : (
              topSkills.map(([skill, count]) => (
                <div key={skill} className="flex items-center gap-3">
                  <span className="w-36 shrink-0 truncate text-sm text-slate-600" title={skill}>
                    {skill}
                  </span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <span
                      className="block h-full rounded-full bg-blue-500"
                      style={{ width: `${(count / maxSkill) * 100}%` }}
                    />
                  </span>
                  <span className="w-8 text-right text-sm font-medium tabular-nums">{count}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Recently added</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-slate-100">
          {recent.map((candidate) => (
            <Link
              key={candidate.id}
              href={`/candidates/${candidate.id}`}
              className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0 hover:bg-slate-50"
            >
              <span className="min-w-0">
                <span className="block truncate font-medium">{fullName(candidate)}</span>
                <span className="block truncate text-sm text-slate-500">
                  {candidate.current_position ?? candidate.position_applied ?? "No role listed"}
                </span>
              </span>
              <StageBadge status={candidate.status} />
            </Link>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
```

The card titled "Pipeline" keeps its name on purpose: `e2e/demo-journey.spec.ts` asserts it.

- [ ] **Step 5: Type check, lint, tests**

Run: `cd web; npm run typecheck; npm run lint; npm test`
Expected: clean; all tests pass. Then `Select-String -Path web/src/lib/*.ts, web/src/app/*.tsx -Pattern countByStage` prints nothing.

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d12.txt`:

```
feat(web): dashboard funnel by stage, attention list, and activity feed

The Pipeline card now shows each round's ever-reached and here-now counts
from the stage history instead of candidate statuses, next to a Needs
attention card (no movement in 7+ days, feedback not yet submitted) and a
Recent activity feed. The three tiles, Top skills, and Recently added
stay; the third tile now counts from the pipeline too.
```

```powershell
git add web/src/components/stage-funnel.tsx web/src/components/attention-list.tsx web/src/components/activity-feed.tsx web/src/app/page.tsx
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d12.txt
```

---

### Task 13: Reports page, nav item, e2e

**Files:**
- Create: `web/src/app/reports/page.tsx`
- Modify: `web/src/lib/nav.ts`
- Create: `web/e2e/reports.spec.ts`

- [ ] **Step 1: Write the page**

Create `web/src/app/reports/page.tsx`:

```tsx
import Link from "next/link";
import { Download } from "lucide-react";

import { JobPicker } from "@/components/job-picker";
import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { StageFunnel } from "@/components/stage-funnel";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { getReport, listJobs } from "@/lib/data";
import type { Report } from "@/lib/domain";
import { formatDate, humanize } from "@/lib/format";
import { canViewReports, daysLabel, exportHref, formatDays } from "@/lib/reports";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export const metadata = { title: "Reports · RecruitIQ" };

const QUERY_NOTE =
  "Every number on this page is a query over applications and their stage history, run when " +
  "the page loads. Nothing is estimated, sampled, or projected.";

function first(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw?.trim() || undefined;
}

/**
 * Funnel, time in stage, outcomes, sources, and the no-movement list, for all
 * jobs or one. Open to the hiring roles and to the read-only demo; an
 * interviewer is told plainly instead of seeing an error.
 */
export default async function ReportsPage({ searchParams }: PageProps<"/reports">) {
  const params = await searchParams;
  const jobParam = first(params.job);
  const jobId = jobParam && /^\d+$/.test(jobParam) ? Number(jobParam) : undefined;

  const user = await getUser();
  if (user && !canViewReports(user.role)) {
    return (
      <>
        <PageHeader title="Reports" />
        <EmptyState
          title="Reports are not available for your role"
          detail="Your assigned candidates and the feedback you owe are on the Interviews page."
        />
      </>
    );
  }

  let report: Report;
  let jobs;
  try {
    [report, jobs] = await Promise.all([getReport(jobId), listJobs()]);
  } catch (error) {
    if (error instanceof ApiError && error.isNotFound) {
      return (
        <>
          <PageHeader title="Reports" />
          <EmptyState title="That job does not exist" detail="Pick another job, or show all jobs." />
        </>
      );
    }
    return (
      <>
        <PageHeader title="Reports" />
        <ErrorState
          title="Could not load reports"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  const [thisQuarter, lastQuarter] = report.quarters;

  return (
    <>
      <PageHeader
        title="Reports"
        description={QUERY_NOTE}
        actions={
          <a href={exportHref(jobId)} className={buttonVariants({ variant: "outline" })}>
            <Download className="mr-1.5 h-4 w-4" aria-hidden />
            Export candidates (CSV)
          </a>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <JobPicker
          jobs={jobs.results.map((job) => ({
            id: job.id,
            title: job.title,
            department: job.department ?? "",
          }))}
          selected={jobId ? String(jobId) : ""}
          basePath="/reports"
          label="Filter by job"
          pendingLabel="Running the queries..."
        />
        {jobId ? (
          <Link href="/reports" className="text-sm text-indigo-600 hover:underline">
            Show all jobs
          </Link>
        ) : null}
      </div>

      <p className="mb-4 text-sm text-slate-600">
        {report.job_title ?? "All jobs"}: {report.total_applications} applications.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Funnel</CardTitle>
          </CardHeader>
          <CardContent>
            <StageFunnel rows={report.funnel} showShare />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Hires and rejections</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Quarter</TableHead>
                  <TableHead className="text-right">Hires</TableHead>
                  <TableHead className="text-right">Rejections</TableHead>
                  <TableHead className="text-right">Offers declined</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[thisQuarter, lastQuarter].map((quarter, index) => (
                  <TableRow key={quarter.label}>
                    <TableCell>
                      {quarter.label}
                      <span className="ml-2 text-xs text-slate-400">
                        {index === 0 ? "this quarter" : "last quarter"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{quarter.hires}</TableCell>
                    <TableCell className="text-right tabular-nums">{quarter.rejections}</TableCell>
                    <TableCell className="text-right tabular-nums">{quarter.offers_declined}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Time in stage</CardTitle>
          </CardHeader>
          <CardContent>
            {report.time_in_stage.length === 0 ? (
              <p className="text-sm text-slate-500">
                No stage has been completed yet, so there is no time to measure.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stage</TableHead>
                    <TableHead className="text-right">Median</TableHead>
                    <TableHead className="text-right">Completed</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.time_in_stage.map((row) => (
                    <TableRow key={row.key}>
                      <TableCell>{row.name}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatDays(row.median_days)}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.completed}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <p className="mt-3 text-xs text-slate-500">
              Median days from entering a stage to leaving it, over applications that finished
              the stage. Stages nobody has finished are left out.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Where applicants come from</CardTitle>
          </CardHeader>
          <CardContent>
            {report.source_mix.length === 0 ? (
              <p className="text-sm text-slate-500">No applications yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Source</TableHead>
                    <TableHead className="text-right">Applications</TableHead>
                    <TableHead className="text-right">Hired</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.source_mix.map((row) => (
                    <TableRow key={row.source}>
                      <TableCell>{humanize(row.source)}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.applications}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.hired}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>No movement in 7+ days</CardTitle>
        </CardHeader>
        <CardContent>
          {report.no_movement.length === 0 ? (
            <p className="text-sm text-slate-500">Every active candidate moved in the last 7 days.</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Candidate</TableHead>
                    <TableHead>Job</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Since</TableHead>
                    <TableHead className="text-right">Waiting</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.no_movement.map((row) => (
                    <TableRow key={row.application_id}>
                      <TableCell>
                        <Link href={`/candidates/${row.candidate_id}`} className="font-medium hover:underline">
                          {row.candidate_name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Link href={`/jobs/${row.job_id}`} className="hover:underline">
                          {row.job_title}
                        </Link>
                      </TableCell>
                      <TableCell>{row.stage_name}</TableCell>
                      <TableCell>{formatDate(row.since)}</TableCell>
                      <TableCell className="text-right tabular-nums">{daysLabel(row.days_waiting)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {report.no_movement_total > report.no_movement.length ? (
                <p className="mt-3 text-xs text-slate-500">
                  Showing the {report.no_movement.length} longest waits of {report.no_movement_total}.
                </p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <p className="mt-6 text-xs text-slate-400">Queried {formatDate(report.generated_at)}.</p>
    </>
  );
}
```

- [ ] **Step 2: Add the nav item**

Phase B's `web/src/lib/nav.ts` gives each item an optional `hiddenFor?: Role[]` and filters it in `visibleGroups(role)`, which the sidebar already uses. Add `BarChart3` to its `lucide-react` import and insert this as the first item of the `Admin` group:

```ts
      { href: "/reports", label: "Reports", icon: BarChart3, hiddenFor: ["interviewer"] },
```

Hide it by role rather than by `REPORTS_VIEW`: the demo holds `reports.view` in Phase B's table, so either rule shows it to the demo, and `hiddenFor` is the shape every other nav item already uses. `canViewReports` in `@/lib/reports` stays the page's own guard.

- [ ] **Step 3: Write the e2e spec**

Create `web/e2e/reports.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

/**
 * Reports and the new dashboard cards as the auto-signed-in demo user. Like
 * the main journey, assertions target real seeded data (stage names, counts)
 * rather than headings alone, which would pass against an empty database.
 */
test("the demo user sees Reports with live numbers and the query note", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Reports", level: 1 })).toBeVisible();
  await expect(page.getByText(/Every number on this page is a query/)).toBeVisible();
  await expect(page.getByText("Could not load reports", { exact: true })).toHaveCount(0);
  for (const title of [
    "Funnel",
    "Hires and rejections",
    "Time in stage",
    "Where applicants come from",
    "No movement in 7+ days",
  ]) {
    await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText("Resume submitted").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Export candidates/ })).toBeVisible();
});

test("the dashboard shows the stage funnel, attention list, and activity", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Pipeline", { exact: true })).toBeVisible();
  await expect(page.getByText("Needs attention", { exact: true })).toBeVisible();
  await expect(page.getByText("Recent activity", { exact: true })).toBeVisible();
  await expect(page.getByText("Resume submitted").first()).toBeVisible();
});

test("the Reports nav item is there for the demo", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await expect(page).toHaveURL(/\/reports$/);
});
```

- [ ] **Step 4: Type check, lint, unit tests, build**

Run: `cd web; npm run typecheck; npm run lint; npm test; npm run build`
Expected: clean; `/reports` appears in the build's route list.

- [ ] **Step 5: Check it live**

Start the backend (`cd backend; poetry run python -m uvicorn main:app --port 8010`) and the web dev server (`cd web; npm run dev`). As the demo (no cookie needed):

- `http://localhost:3000/`: Pipeline card shows nine rounds with both bars; Needs attention lists a handful of people (the seed spread put about a quarter of active applications past 7 days); Recent activity reads as sentences with dates.
- `http://localhost:3000/reports`: all five cards populated; medians between 1 and 7 days; picking a job in the filter changes every number and the CSV link gains `?job_id=`; the CSV link downloads a file (Phase C's export).
- With an interviewer token in the `recruitiq_session` cookie (mint one the way Phase A minted an admin token, for a user with role `interviewer`): `/reports` shows "Reports are not available for your role", there is no Reports nav item, and the dashboard counts only that interviewer's assigned candidates.

Take screenshots at desktop and 390px width with a scratch Playwright script in `web/` (as in Phase A; delete it afterwards) and look at them: no horizontal page scroll on mobile, the funnel labels truncate rather than wrap.

Then run the e2e against the dev servers:

```powershell
cd web; $env:E2E_BASE_URL = "http://localhost:3000"; npx playwright test
```

Expected: all pass (the existing 9 plus the 3 new ones). If anything fails, re-run against `https://recruitiq.io` only for the specs that exist in prod; a rotted `next dev` fakes failures, so restart it before blaming the code.

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-d13.txt`:

```
feat(web): Reports page and nav item

Funnel with share of applicants, hires and rejections for this quarter and
last, median time in stage, source mix, and the full no-movement list,
filterable by job, with the CSV export from Phase C. The page says every
number is a query, because it is. Interviewers get a plain "not available"
instead of an error and no nav item; the demo sees the whole page.

Verified: typecheck, lint, vitest, build, Playwright (new reports spec plus
the existing journey), and live as the demo and as an interviewer.
```

```powershell
git add web/src/app/reports/page.tsx web/src/lib/nav.ts web/e2e/reports.spec.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-d13.txt
```

---

### Task 14: Full verification, PR, deploy

**Files:** none new.

- [ ] **Step 1: Backend, the way CI does it**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
$env:OLLAMA_BASE_URL = "http://localhost:1"
poetry run ruff check backend --select E9,F63,F7,F82 --exclude backend/tests
poetry run python scripts/export_openapi.py --check
```

Expected: ruff clean, OpenAPI in sync.

- [ ] **Step 2: Full suite on a database built from migrations alone**

No schema changed, but CI runs on an empty migrated database and this phase's tests must not lean on dev data:

```powershell
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
poetry run pytest -q
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
```

Run it in the background (about 8 minutes) and write the PR body meanwhile. Expected: green apart from the two embedding tests known to fail only under the unreachable-Ollama env. Anything else red is this branch's to fix.

- [ ] **Step 3: Push and open the PR**

Write `C:\Users\seaso\AppData\Local\Temp\claude\pr-d.md`:

```
## What

ATS Phase D: a Reports page and a working dashboard, both built from the stage history. Funnel (ever reached vs here now), median time in stage, no movement in 7+ days, pending feedback, source mix, hires and rejections by quarter, an activity feed, and two assistant tools (`get_job_pipeline`, `find_candidates_at_stage`). Spec: docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md section 8 Phase D.

## Why

Phases A to C made RecruitIQ move candidates; nothing yet told a recruiter how the pipeline is doing or what is stuck. Every number is a query and the page says so.

## Decisions worth a look

- Time in stage excludes zero-length rows: those are bulk backfill (Phase A migration, original seed), not time anybody spent.
- The demo role is let into Reports explicitly (portfolio visitors see every screen); interviewers get 403 and no nav item.
- Hires and rejections show this quarter and last quarter side by side, both real queries, so a quiet quarter is not an empty card.
- The seed now lays out realistic, deterministic stage timestamps once, and never touches anything a person has moved. It also stops reassigning statuses of candidates already on a pipeline.

## Verified

- backend: test_reports.py on a fixed four-application timeline with an injected now (funnel, medians via percentile_cont including the two-value midpoint, both sides of the 7-day line, quarter boundary, activity folding, every role on both endpoints); golden replay for both new tools; full suite on a database built from migrations alone
- seed: two runs on a scratch DB give byte-identical stage history; a clicked dev application survives a re-run
- web: typecheck, lint, vitest, build, Playwright (existing journey plus reports spec)
- live: demo and interviewer against the dev backend, desktop and 390px

## Prod follow-up

Needs Sean's go-ahead (rewrites timestamps on seeded rows nobody has moved): run `scripts/seed_demo.py --no-embeddings` on the droplet so prod's Phase A backfill rows get realistic timestamps. Until then prod Reports shows "No completed stages yet" for time in stage and lists every active seeded candidate under no movement, which is accurate for flat data. No migration, no re-embed.
```

```powershell
git push -u origin ats-reports-dashboard
gh pr create --base main --title "feat: reports page, dashboard funnel, and pipeline assistant tools (ATS Phase D)" --body-file C:\Users\seaso\AppData\Local\Temp\claude\pr-d.md
gh pr checks --watch
```

- [ ] **Step 4: Merge and deploy**

```powershell
gh pr merge --merge --delete-branch
git fetch origin
```

Deploy with the Bash tool:

```bash
ssh root@157.245.233.229 "free -h; pgrep -fa '[d]eploy.sh' || echo no-deploy-running"
ssh root@157.245.233.229 "/opt/recruitiq/app/scripts/deploy.sh"
```

Expected: at least 500M available; `==> deployed <sha>` matching `git rev-parse --short origin/main`.

- [ ] **Step 5: Smoke test prod**

```bash
curl -sS -o /dev/null -w "home %{http_code}\n" https://recruitiq.io/
curl -sS -o /dev/null -w "reports %{http_code}\n" https://recruitiq.io/reports
ssh root@157.245.233.229 'curl -sS http://127.0.0.1:8020/health; echo; curl -s http://127.0.0.1:8020/api/reports/dashboard | head -c 300; echo; T=$(curl -s -X POST http://127.0.0.1:8020/auth/demo | grep -o "\"access_token\":\"[^\"]*" | cut -d\" -f4); curl -s -H "Authorization: Bearer $T" http://127.0.0.1:8020/api/reports/summary | head -c 300; echo'
J=$(ssh root@157.245.233.229 'curl -s "http://127.0.0.1:8020/api/jobs/?page_size=1" | grep -o "\"id\":[0-9]*" | head -1 | cut -d: -f2'); curl -sS -o /dev/null -w "reports for job $J %{http_code}\n" "https://recruitiq.io/reports?job=$J"
```

Expected: 200, 200, health ok, a dashboard body starting `{"generated_at":`, a summary body starting `{"generated_at":`, and 200 for the filtered page. The job id is looked up, never hard-coded (prod has no job 1).

- [ ] **Step 6: Report the pending follow-up**

Do not run the prod seed. Report it as pending, with the command for when Sean says yes:

```bash
ssh root@157.245.233.229 "sudo -u recruitiq bash -c 'set -a; . /etc/recruitiq/env; set +a; cd /opt/recruitiq/app && .venv/bin/python scripts/seed_demo.py --no-embeddings'"
```

---

## Self-review

**Spec coverage (section 8 Phase D, section 5 rows marked D):**
- Reports: funnel ever reached vs here (Task 3), median time in stage (Task 4), no-movement list (Task 5), source mix and hires/rejections this quarter (Task 6), CSV export of the filtered list via Phase C's endpoint (Tasks 11 and 13). Covered.
- Dashboard: funnel by stage, needs-attention list with no movement and pending feedback, activity feed from `application_stages` timestamps, three tiles kept, nothing dropped (Tasks 5, 7, 12). Covered.
- "No PDF, no scheduling, no fabricated trend lines": none built; the quarter card compares two real quarters only. Covered.
- Acceptance "every number on Reports is a query over application_stages and the page says so": every Reports number comes from reports_service queries over `application_stages` joined to `job_applications`. Source mix and total applications read `job_applications` columns, so the page note says "applications and their stage history" rather than claiming one table. Covered, worded accurately.
- Assistant row (B, D): pipeline state for a job (`get_job_pipeline`) and who is at a stage (`find_candidates_at_stage`), both scoped to the viewer and covered by golden cases. Pending feedback as an assistant tool is Phase B's per the spec's Phase B scope. Covered.
- Roles: REPORTS_VIEW gate plus explicit demo access; interviewer dashboard scoped by `visible_candidate_ids`; interviewer pending feedback limited to their own. Covered (Tasks 5, 8, 13).

**Placeholder scan:** no "TBD", "TODO", "similar to", or "add validation". Two steps branch on what Phase B shipped (Task 9 Step 4, Task 13 Step 2); each gives the exact code for both branches and Task 1 decides which applies.

**Type consistency:** `Scope.of(job_id=, candidate_ids=)` is used the same way in the router, the tools, and the tests. Dict keys returned by the service match the Pydantic models field for field (`FunnelRow.position`, `WaitingApplication.days_waiting`, `PendingFeedbackRow.days_pending`, `QuarterOutcomes.offers_declined`, `ActivityEvent.actor_name`). `quarter_bounds` returns `(start, end, label)`, matching `outcomes_between(db, scope, start, end, label)`. Web aliases name the generated schemas exactly (`DashboardResponse`, `ReportsResponse`, `FunnelRow`, `StageTiming`, `WaitingApplication`, `PendingFeedbackRow`, `ActivityEvent`, `SourceRow`, `QuarterOutcomes`); none of these names existed in `openapi.json` before this phase. Tool result shapes keep the link checker's conventions: candidates as `{id, name}`, jobs as `{job_id, job_title}`, stages never as `{id, name}`.

**Test count check:** test_reports.py ends at 43 tests (10 after Task 2, 14 after Task 3, 17 after Task 4, 21 after Task 5, 23 after Task 6, 27 after Task 7, 34 after Task 8, 43 after Task 9: 4 normalize parametrizations, resolve, two get_job_pipeline, two find_candidates).
