# ATS Phase B: Team and Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four staff roles (Admin, Hiring manager, Hiring team, Interviewer) with the spec's permission matrix, interviewers assigned to stages (by hand or by default), a feedback form, interviewers confined to the candidates they interview and kept from the AI score until they have given feedback, plus Team, Settings, and Interviews pages and a grouped sidebar.

**Architecture:** One permission table (`backend/utils/permissions.py`) drives three consumers: the app-wide write gate (`enforce_read_only`, through `ROUTE_PERMISSIONS`), per-route `require(...)` checks, and a generated JSON copy the web app reads. A second app-wide gate (`enforce_interviewer_scope` in `backend/services/access_service.py`) is default-deny for the interviewer role: only an allowlist of paths is reachable, and paths that name a candidate, resume, or application are checked against `visible_candidate_ids`. Roles are resolved from the database once per request (`request_identity`), so a role change or a deleted account takes effect on the next request rather than when a 24-hour token expires. Interview and feedback logic lives in `backend/services/feedback_service.py`; `pipeline_service` calls a new `on_stage_entered` hook so default interviewers are assigned when an application reaches a round.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic (backend), Next.js 16 App Router + Tailwind + Vitest + Playwright (web), pytest with the transactional fixtures in `backend/tests/conftest.py`.

**Spec:** `docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md` (sections 3.1, 3.2, 5 rows marked B, 6, 8 Phase B). **Prerequisite:** Phase A merged (`c32a66d` on `main`).

---

## Conventions for every task

- Work on branch `ats-team-feedback`, created from `origin/main`.
- Backend tests run from the repo root with the dev database:
  ```powershell
  $env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
  $env:OLLAMA_BASE_URL = "http://localhost:1"
  poetry run pytest backend/tests/test_team_access.py -q
  ```
- The dev database must be at the new head before any test in this plan runs: Task 1 Step 6 upgrades it.
- Web tests run from `web/`: `npm test`, `npm run typecheck`, `npm run lint`.
- Commit messages are written to a file in the scratchpad (`$S` below) and committed with `git commit -F`. Never `git commit -m` with a PowerShell here-string. No attribution trailers of any kind.
  ```powershell
  $S = "C:\Users\seaso\AppData\Local\Temp\claude\phase-b"; New-Item -ItemType Directory -Force $S | Out-Null
  ```
- Write files with the Edit/Write tools or `[IO.File]::WriteAllText`. `Set-Content -Encoding utf8` adds a BOM to Python files.
- No em dashes in any string a user can read. American spelling. Spec section 7 terms: "Hiring manager", "Hiring team", "Feedback" (never "feedbacks"), "Interviewer".
- New endpoints that use `Depends(get_db)` are plain `def`, never `async def`.
- Any reset fixture between route tests must `commit()`, not `flush()` (a 409 in a route rolls the shared session back to its last commit).

## Decisions this plan makes (the spec left them open)

1. **Roles come from the database, not the token claim.** `request_identity` looks the user up once per request for any non-demo token. Demo tokens skip the query (the demo role never changes and is most of the traffic).
2. **Interviewers are default-deny for reads too.** Rather than auditing forty legacy read routes one by one, an interviewer can reach only `INTERVIEWER_PATHS`. Anything else is 403 with a plain sentence. A route-walk test proves it, the same way `test_auth.py` proves the write gate.
3. **Interviewers do not get the assistant, Matching, Upload, or the trace tools** in Phase B. Each would need its own scoping and score hiding; the 403 is honest, and the sidebar hides those items for the role. Recommended roles on a candidate page appear once the interviewer has submitted feedback (the match-jobs endpoint checks `can_see_score`).
4. **Other people's feedback follows the score rule.** An interviewer sees colleagues' feedback on a candidate only after submitting their own, so nobody anchors on someone else's verdict. Their own feedback is always visible to them.
5. **Feedback is final once submitted.** A second submit is 409. Editing can come later; this keeps the reveal rule honest.
6. **Read permissions for the demo role.** `score.before_feedback` and `reports.view` are granted to `demo` so the public demo keeps every screen. The demo role holds no write permission, and the write gate refuses it regardless.
7. **One extra permission, `profile.edit`**, for Settings (every staff role). It is the only permission Phase B adds beyond the contract list.
8. **`users.timezone`** joins `users.name`; Settings stores it (free text matching an IANA-style pattern; the web offers a fixed list). Nothing else reads it in Phase B.
9. **Invites:** a hiring manager may invite any role except admin. The temporary password (16 URL-safe characters) is returned once in the response and shown once in the UI. No email is sent (spec: email arrives in Phase E).
10. **Deleting a user** is refused when they have submitted feedback ("Change their role instead"), because feedback is history. Pending interviews are removed, `application_stages.changed_by` is cleared, and jobs' manager and recruiter links are set to null by the foreign key.
11. **Anonymous and demo reads are unchanged.** The public demo still lets anyone read the synthetic dataset. Interviewer scoping limits what an interviewer's own session shows; closing anonymous reads for a private deployment is a separate setting and is not part of this phase (flagged in the PR).
12. **`jobs.hiring_manager_id` / `recruiter_id`** are accepted (validated against the team) and returned by the jobs API, and the seed fills `hiring_manager_id`. The job form picker for them waits for Phase E's job-form work; until then the job page keeps showing the free-text `hiring_manager` and `recruiter` fields.

## File structure

| File | Responsibility |
|---|---|
| `backend/alembic/versions/d5f9b2c3e4a5_team_roles_interviews_feedback.py` | Create: users.name/timezone, jobs FKs, `interviews`, `feedback`, `stage_default_interviewers` |
| `backend/models/models.py` | Modify: columns on `User` and `Job`; `Interview`, `Feedback`, `StageDefaultInterviewer`; relationships on `ApplicationStage` and `PipelineStage` |
| `backend/utils/auth.py` | Modify: role constants, `STAFF_ROLES`, `request_identity`, rewritten `enforce_read_only` |
| `backend/utils/permissions.py` | Create: permission constants, `ROLE_PERMISSIONS`, `ROLE_LABELS`, `can`, `require`, `ROUTE_PERMISSIONS`, `route_permission` |
| `backend/services/access_service.py` | Create: `visible_candidate_ids`, `can_see_score`, `request_user`, `INTERVIEWER_PATHS`, `enforce_interviewer_scope` |
| `backend/services/feedback_service.py` | Create: assign, unassign, defaults, submit, pending, visibility, feedback policy text |
| `backend/services/pipeline_service.py` | Modify: `on_stage_entered` hook called when a round starts |
| `backend/models/feedback.py`, `backend/models/team.py` | Create: Pydantic shapes |
| `backend/models/user.py` | Modify: five roles, `name` on `UserResponse` |
| `backend/models/job.py` | Modify: `hiring_manager_id`, `recruiter_id` on create/update and response |
| `backend/routers/feedback.py` | Create: interviews, feedback, default interviewers |
| `backend/routers/team.py` | Create: users list, invite, role, delete, me, password |
| `backend/routers/interviews.py` | Delete: the in-memory mock |
| `backend/routers/candidates.py`, `pipeline.py`, `enhanced_matching.py`, `resume.py`, `jobs.py`, `transparency.py` | Modify: scoping, score check, save permission, FK validation, feedback policy card |
| `backend/services/assistant_tools.py`, `evals/assistant_golden.json` | Modify: `list_pending_feedback` tool and its golden question |
| `backend/main.py` | Modify: second app-wide dependency, mount `team` and `feedback`, drop `interviews` |
| `scripts/export_permissions.py` | Create: writes `web/src/lib/role-permissions.json`, `--check` mode |
| `scripts/create_admin.py` | Modify: `--role` and `--name` |
| `scripts/seed_demo.py` | Modify: `seed_team`, `seed_interviews` |
| `backend/tests/conftest.py` | Modify: staff users and clients, `scoped_application` |
| `backend/tests/test_auth.py` | Modify: staff-role route walk |
| `backend/tests/test_permissions.py`, `test_team_access.py`, `test_feedback.py`, `test_team.py` | Create |
| `web/src/lib/permissions.ts` + test, `role-permissions.json` | Create |
| `web/src/lib/session.ts` + test | Modify: roles, `name`, `canWrite` meaning, `hasPermission` |
| `web/src/lib/guards.ts` | Create: `redirectInterviewer` |
| `web/src/lib/nav.ts` + test, `web/src/components/sidebar.tsx` | Create; `web/src/components/nav.tsx` deleted |
| `web/src/app/layout.tsx`, `web/src/components/session-badge.tsx` | Modify: sidebar layout, role label |
| `web/src/lib/forward.ts` + test | Create: one forwarder for the new proxy routes |
| `web/src/app/api/team/**`, `web/src/app/api/interviews/**`, `web/src/app/api/applications/[id]/interviews/route.ts`, `web/src/app/api/jobs/[id]/stages/[stage]/default-interviewers/route.ts` | Create: proxy routes |
| `web/src/lib/domain.ts`, `web/src/lib/data.ts` | Modify: new types and fetchers |
| `web/src/app/team/page.tsx`, `settings/page.tsx`, `interviews/page.tsx` (+ `loading.tsx` each) | Create |
| `web/src/components/team-invite-form.tsx`, `team-member-actions.tsx`, `settings-form.tsx`, `password-form.tsx`, `interview-panel.tsx`, `assign-interviewer.tsx`, `feedback-form.tsx`, `default-interviewers-editor.tsx` | Create |
| `web/src/app/page.tsx`, `jobs/**`, `candidates/[id]/page.tsx`, `matching/page.tsx`, `upload/page.tsx`, `assistant/page.tsx`, `transparency/page.tsx` | Modify: permissions, guards, panels |
| `web/e2e/header-layout.spec.ts`, `web/e2e/team-screens.spec.ts` | Modify / Create |
| `openapi.json`, `web/src/lib/schema.d.ts`, `backend/tests/golden/api_response_shapes.json` | Regenerated |

---

### Task 1: Branch, migration, and ORM models

**Files:**
- Create: `backend/alembic/versions/d5f9b2c3e4a5_team_roles_interviews_feedback.py`
- Modify: `backend/models/models.py`
- Test: `backend/tests/test_feedback.py` (new)

- [ ] **Step 1: Create the branch**

```powershell
git fetch origin
git switch -c ats-team-feedback origin/main
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_feedback.py`:

```python
"""Interviews, feedback, and default interviewers (ATS Phase B).

Uses `scoped_application` from conftest (its own job and application) so the
seeded application that test_pipeline relies on is never touched.
"""
from __future__ import annotations

import pytest

from backend.models.models import (
    ApplicationStage,
    Feedback,
    Interview,
    PipelineStage,
    StageDefaultInterviewer,
    User,
)


def test_models_import_and_map():
    assert Interview.__tablename__ == "interviews"
    assert Feedback.__tablename__ == "feedback"
    assert StageDefaultInterviewer.__tablename__ == "stage_default_interviewers"
    assert "interviews" in ApplicationStage.__mapper__.relationships
    assert "default_interviewers" in PipelineStage.__mapper__.relationships
    assert "name" in User.__table__.columns
    assert "timezone" in User.__table__.columns
```

- [ ] **Step 3: Run it to verify it fails**

Run: `poetry run pytest backend/tests/test_feedback.py -q`
Expected: FAIL with `ImportError: cannot import name 'Feedback'`

- [ ] **Step 4: Write the migration**

Create `backend/alembic/versions/d5f9b2c3e4a5_team_roles_interviews_feedback.py`:

```python
"""team roles, interviews, feedback, stage default interviewers

ATS Phase B (spec 2026-10-03 sections 3.1, 3.2, 8). Adds users.name and
users.timezone, jobs.hiring_manager_id and jobs.recruiter_id, and the three
tables that turn interview assignments and feedback into rows.

No backfill. Existing users keep their role (admin and demo are both still
valid) and have no name until they set one in Settings. users.role is a
plain varchar, so the four staff roles need no type change.

Revision ID: d5f9b2c3e4a5
Revises: c4e8a1b2d3f4
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5f9b2c3e4a5"
down_revision: Union[str, None] = "c4e8a1b2d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("timezone", sa.String(64), nullable=True))

    op.add_column(
        "jobs",
        sa.Column(
            "hiring_manager_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_jobs_hiring_manager_id"),
            nullable=True,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "recruiter_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_jobs_recruiter_id"),
            nullable=True,
        ),
    )

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_stage_id",
            sa.Integer(),
            sa.ForeignKey("application_stages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("interviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assignment_source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "application_stage_id", "interviewer_id", name="uq_interview_stage_interviewer"
        ),
    )
    op.create_index("ix_interviews_application_stage_id", "interviews", ["application_stage_id"])
    op.create_index("ix_interviews_interviewer_id", "interviews", ["interviewer_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "interview_id",
            sa.Integer(),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("recommendation", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
    )

    op.create_table(
        "stage_default_interviewers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pipeline_stage_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_stages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("pipeline_stage_id", "user_id", name="uq_stage_default_interviewer"),
    )
    op.create_index(
        "ix_stage_default_interviewers_pipeline_stage_id",
        "stage_default_interviewers",
        ["pipeline_stage_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage_default_interviewers_pipeline_stage_id", table_name="stage_default_interviewers"
    )
    op.drop_table("stage_default_interviewers")
    op.drop_table("feedback")
    op.drop_index("ix_interviews_interviewer_id", table_name="interviews")
    op.drop_index("ix_interviews_application_stage_id", table_name="interviews")
    op.drop_table("interviews")
    op.drop_constraint("fk_jobs_recruiter_id", "jobs", type_="foreignkey")
    op.drop_constraint("fk_jobs_hiring_manager_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "recruiter_id")
    op.drop_column("jobs", "hiring_manager_id")
    op.drop_column("users", "timezone")
    op.drop_column("users", "name")
```

- [ ] **Step 5: Add the ORM models**

In `backend/models/models.py`, extend the sqlalchemy import line (it ends with `Index, Boolean` after Phase A):

```python
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Table, UniqueConstraint, event, Float, Index, Boolean, SmallInteger, CheckConstraint
```

In `class Job`, directly after `recruiter = Column(String(255), nullable=True)`, add:

```python
    # ATS Phase B: optional links to team members. The free-text columns
    # above stay for display and seed data (spec 3.2).
    hiring_manager_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recruiter_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
```

In `class User`, directly after `role = Column(String(20), nullable=False, default="demo")`, add:

```python
    # ATS Phase B. Roles: admin, hiring_manager, hiring_team, interviewer, demo.
    name = Column(String(100), nullable=True)
    timezone = Column(String(64), nullable=True)
```

and update the `User` docstring's first paragraph to read:

```python
    """An operator of the platform.

    Five roles (ATS Phase B): admin, hiring_manager, hiring_team, and
    interviewer are staff; demo is the read-only public account, created on
    demand by POST /auth/demo so a visitor following a link never meets a
    login screen. What each role may do lives in backend/utils/permissions.py.
    """
```

In `class PipelineStage`, after `job = relationship("Job", back_populates="pipeline_stages")`, add:

```python
    default_interviewers = relationship(
        "StageDefaultInterviewer", cascade="all, delete-orphan", back_populates="stage"
    )
```

In `class ApplicationStage`, after `stage = relationship("PipelineStage")`, add:

```python
    interviews = relationship(
        "Interview",
        back_populates="application_stage",
        cascade="all, delete-orphan",
        order_by="Interview.id",
    )
```

Append at the end of the file:

```python
# ====================================================================
# Interviews and feedback (ATS Phase B, spec 2026-10-03 section 3.1)
# ====================================================================


class Interview(Base):
    """One interviewer assigned to one stage of one application."""
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True)
    application_stage_id = Column(
        Integer, ForeignKey("application_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assignment_source = Column(String(20), nullable=False, default="manual")  # manual or default
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("application_stage_id", "interviewer_id", name="uq_interview_stage_interviewer"),
    )

    application_stage = relationship("ApplicationStage", back_populates="interviews")
    interviewer = relationship("User")
    feedback = relationship(
        "Feedback", back_populates="interview", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Interview(stage_row={self.application_stage_id}, interviewer={self.interviewer_id})>"


class Feedback(Base):
    """What one interviewer thought. Never read by the scorer (transparency page)."""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    interview_id = Column(
        Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    rating = Column(SmallInteger, nullable=False)
    recommendation = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),)

    interview = relationship("Interview", back_populates="feedback")


class StageDefaultInterviewer(Base):
    """Assigned automatically when an application enters this stage."""
    __tablename__ = "stage_default_interviewers"

    id = Column(Integer, primary_key=True)
    pipeline_stage_id = Column(
        Integer, ForeignKey("pipeline_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("pipeline_stage_id", "user_id", name="uq_stage_default_interviewer"),
    )

    stage = relationship("PipelineStage", back_populates="default_interviewers")
    user = relationship("User")
```

- [ ] **Step 6: Verify on a scratch database, then upgrade dev**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$dev = $env:POSTGRES_CONN
$env:POSTGRES_CONN = $dev -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; poetry run alembic downgrade -1; poetry run alembic upgrade head; cd ..
docker exec recruitiq-db psql -U admin -d st_scratch -c "\d interviews" -c "\d feedback" -c "\d stage_default_interviewers" -c "\d users"
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
$env:POSTGRES_CONN = $dev
cd backend; poetry run alembic upgrade head; cd ..
```

Expected: each `\d` lists the columns above; `users` shows `name` and `timezone`; downgrade and re-upgrade both succeed; the dev upgrade prints `Running upgrade c4e8a1b2d3f4 -> d5f9b2c3e4a5`.

- [ ] **Step 7: Run the test**

Run: `poetry run pytest backend/tests/test_feedback.py -q`
Expected: 1 passed

- [ ] **Step 8: Commit**

Write `$S\commit-b1.txt`:

```
feat: schema for team roles, interviews, and feedback

ATS Phase B. users gain name and timezone, jobs gain optional links to a
hiring manager and recruiter, and three tables hold interview
assignments, feedback, and per-stage default interviewers. Verified:
upgrade, downgrade, upgrade on a scratch database, then upgrade on dev.
```

```powershell
git add backend/alembic/versions/d5f9b2c3e4a5_team_roles_interviews_feedback.py backend/models/models.py backend/tests/test_feedback.py
git commit -F "$S\commit-b1.txt"
```

---

### Task 2: The permission table

**Files:**
- Modify: `backend/utils/auth.py` (role constants only in this task)
- Create: `backend/utils/permissions.py`
- Test: `backend/tests/test_permissions.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_permissions.py`:

```python
"""The permission matrix (spec 2026-10-03 section 8, Phase B), pinned cell by cell.

Written out by hand on purpose: if someone edits ROLE_PERMISSIONS, this test
says which promise in the spec they just broke.
"""
from __future__ import annotations

import pytest

from backend.utils import permissions as p
from backend.utils.auth import (
    ROLE_ADMIN,
    ROLE_DEMO,
    ROLE_HIRING_MANAGER,
    ROLE_HIRING_TEAM,
    ROLE_INTERVIEWER,
    STAFF_ROLES,
)

ADMIN, HM, TEAM, INT, DEMO = ROLE_ADMIN, ROLE_HIRING_MANAGER, ROLE_HIRING_TEAM, ROLE_INTERVIEWER, ROLE_DEMO

# (permission, roles that have it). Spec table rows, then the contract rows.
MATRIX = [
    (p.JOBS_WRITE, {ADMIN, HM}),
    (p.CANDIDATES_ADD, {ADMIN, HM, TEAM}),
    (p.PIPELINE_MOVE, {ADMIN, HM, TEAM}),
    (p.FEEDBACK_SUBMIT, {ADMIN, HM, TEAM, INT}),
    (p.USERS_INVITE, {ADMIN, HM}),
    (p.USERS_CHANGE_ROLE, {ADMIN}),
    (p.DELETE_RECORDS, {ADMIN}),
    (p.SCORE_BEFORE_FEEDBACK, {ADMIN, HM, TEAM, DEMO}),
    (p.REPORTS_VIEW, {ADMIN, HM, TEAM, DEMO}),
    (p.TEMPLATES_MANAGE, {ADMIN, HM}),
    (p.PROFILE_EDIT, {ADMIN, HM, TEAM, INT}),
]


@pytest.mark.parametrize(("permission", "holders"), MATRIX, ids=[m[0] for m in MATRIX])
def test_matrix_cell_by_cell(permission, holders):
    for role in (ADMIN, HM, TEAM, INT, DEMO):
        assert p.can(role, permission) is (role in holders), (role, permission)


def test_every_permission_is_in_the_matrix():
    assert {m[0] for m in MATRIX} == set(p.ALL_PERMISSIONS)


def test_unknown_and_missing_roles_can_do_nothing():
    for permission in p.ALL_PERMISSIONS:
        assert not p.can(None, permission)
        assert not p.can("", permission)
        assert not p.can("superuser", permission)


def test_staff_roles_are_the_four_non_demo_roles():
    assert set(STAFF_ROLES) == {ADMIN, HM, TEAM, INT}


def test_demo_holds_no_write_permission():
    writes = set(p.ALL_PERMISSIONS) - {p.SCORE_BEFORE_FEEDBACK, p.REPORTS_VIEW}
    assert not (p.ROLE_PERMISSIONS[DEMO] & writes)


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/api/jobs", p.JOBS_WRITE),
        ("PUT", "/api/jobs/12", p.JOBS_WRITE),
        ("DELETE", "/api/jobs/12", p.DELETE_RECORDS),
        ("PUT", "/api/jobs/12/pipeline", p.JOBS_WRITE),
        ("PUT", "/api/jobs/12/stages/hm_review/default-interviewers", p.JOBS_WRITE),
        ("POST", "/api/jobs/12/apply", p.CANDIDATES_ADD),
        ("POST", "/api/candidates", p.CANDIDATES_ADD),
        ("DELETE", "/api/candidates/abc", p.DELETE_RECORDS),
        ("POST", "/api/resume/save-candidate", p.CANDIDATES_ADD),
        ("POST", "/api/applications/7/advance", p.PIPELINE_MOVE),
        ("POST", "/api/applications/7/interviews", p.PIPELINE_MOVE),
        ("DELETE", "/api/interviews/3", p.PIPELINE_MOVE),
        ("POST", "/api/interviews/3/feedback", p.FEEDBACK_SUBMIT),
        ("POST", "/api/team/users", p.USERS_INVITE),
        ("PUT", "/api/team/users/abc/role", p.USERS_CHANGE_ROLE),
        ("DELETE", "/api/team/users/abc", p.DELETE_RECORDS),
        ("PUT", "/api/team/me", p.PROFILE_EDIT),
        ("PUT", "/api/team/me/password", p.PROFILE_EDIT),
        # Not listed: stays admin-only.
        ("POST", "/api/jobs/12/track-view", None),
        ("POST", "/api/cache/clear", None),
        ("POST", "/api/applications/7/promote", None),
    ],
)
def test_route_permission(method, path, expected):
    assert p.route_permission(method, path) == expected
```

- [ ] **Step 2: Run it to verify it fails**

Run: `poetry run pytest backend/tests/test_permissions.py -q`
Expected: FAIL with `ImportError: cannot import name 'permissions'`

- [ ] **Step 3: Add the role constants**

In `backend/utils/auth.py`, replace

```python
ROLE_ADMIN = "admin"
ROLE_DEMO = "demo"
```

with

```python
ROLE_ADMIN = "admin"
ROLE_HIRING_MANAGER = "hiring_manager"
ROLE_HIRING_TEAM = "hiring_team"
ROLE_INTERVIEWER = "interviewer"
ROLE_DEMO = "demo"

# ATS Phase B: the four roles a person on the team can hold. `demo` is the
# public read-only account and is never a staff role.
STAFF_ROLES = (ROLE_ADMIN, ROLE_HIRING_MANAGER, ROLE_HIRING_TEAM, ROLE_INTERVIEWER)
```

- [ ] **Step 4: Write the permission module**

Create `backend/utils/permissions.py`:

```python
"""Who may do what (ATS Phase B, spec 2026-10-03 section 8, Phase B).

One table, read by three consumers:

- the app-wide write gate, `enforce_read_only`, through ROUTE_PERMISSIONS;
- routes that need the acting user and a finer check, through `require`;
- the web app, which hides controls a role cannot use. Its copy,
  web/src/lib/role-permissions.json, is generated from this module by
  scripts/export_permissions.py and a test fails if it drifts.

Two read permissions (`score.before_feedback`, `reports.view`) are granted to
the demo role on purpose: the public demo shows every screen. The demo role
holds no write permission, and the write gate refuses it every write anyway.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from fastapi import Depends, HTTPException, status

from backend.models.models import User
from backend.utils.auth import (
    ROLE_ADMIN,
    ROLE_DEMO,
    ROLE_HIRING_MANAGER,
    ROLE_HIRING_TEAM,
    ROLE_INTERVIEWER,
    get_current_user,
)

JOBS_WRITE = "jobs.write"
CANDIDATES_ADD = "candidates.add"
PIPELINE_MOVE = "pipeline.move"
FEEDBACK_SUBMIT = "feedback.submit"
USERS_INVITE = "users.invite"
USERS_CHANGE_ROLE = "users.change_role"
DELETE_RECORDS = "records.delete"
SCORE_BEFORE_FEEDBACK = "score.before_feedback"
REPORTS_VIEW = "reports.view"
TEMPLATES_MANAGE = "templates.manage"
PROFILE_EDIT = "profile.edit"

ALL_PERMISSIONS = (
    JOBS_WRITE,
    CANDIDATES_ADD,
    PIPELINE_MOVE,
    FEEDBACK_SUBMIT,
    USERS_INVITE,
    USERS_CHANGE_ROLE,
    DELETE_RECORDS,
    SCORE_BEFORE_FEEDBACK,
    REPORTS_VIEW,
    TEMPLATES_MANAGE,
    PROFILE_EDIT,
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_ADMIN: frozenset(ALL_PERMISSIONS),
    ROLE_HIRING_MANAGER: frozenset(
        {
            JOBS_WRITE,
            CANDIDATES_ADD,
            PIPELINE_MOVE,
            FEEDBACK_SUBMIT,
            USERS_INVITE,
            SCORE_BEFORE_FEEDBACK,
            REPORTS_VIEW,
            TEMPLATES_MANAGE,
            PROFILE_EDIT,
        }
    ),
    ROLE_HIRING_TEAM: frozenset(
        {
            CANDIDATES_ADD,
            PIPELINE_MOVE,
            FEEDBACK_SUBMIT,
            SCORE_BEFORE_FEEDBACK,
            REPORTS_VIEW,
            PROFILE_EDIT,
        }
    ),
    ROLE_INTERVIEWER: frozenset({FEEDBACK_SUBMIT, PROFILE_EDIT}),
    ROLE_DEMO: frozenset({SCORE_BEFORE_FEEDBACK, REPORTS_VIEW}),
}

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "Admin",
    ROLE_HIRING_MANAGER: "Hiring manager",
    ROLE_HIRING_TEAM: "Hiring team",
    ROLE_INTERVIEWER: "Interviewer",
    ROLE_DEMO: "Read-only demo",
}


def can(role: Optional[str], permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role or "", frozenset())


def role_label(role: Optional[str]) -> str:
    return ROLE_LABELS.get(role or "", role or "Signed out")


def require(permission: str) -> Callable[..., User]:
    """A dependency that returns the acting user, or 403 in plain English."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not can(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role ({role_label(user.role)}) cannot do this.",
            )
        return user

    return dependency


# (method, path pattern, permission). Paths are matched after the trailing
# slash is stripped, with `fullmatch`. A mutating route that matches nothing
# here stays admin-only: forgetting to list a new route denies it rather than
# exposing it. Later phases append their own rows in their own plans.
ROUTE_PERMISSIONS: list[tuple[str, re.Pattern[str], str]] = [
    (method, re.compile(pattern), permission)
    for method, pattern, permission in [
        ("POST", r"/api/jobs", JOBS_WRITE),
        ("PUT", r"/api/jobs/\d+", JOBS_WRITE),
        ("DELETE", r"/api/jobs/\d+", DELETE_RECORDS),
        ("PUT", r"/api/jobs/\d+/pipeline", JOBS_WRITE),
        ("PUT", r"/api/jobs/\d+/stages/[a-z0-9_]+/default-interviewers", JOBS_WRITE),
        ("POST", r"/api/jobs/\d+/apply", CANDIDATES_ADD),
        ("POST", r"/api/candidates", CANDIDATES_ADD),
        ("PUT", r"/api/candidates/[^/]+", CANDIDATES_ADD),
        ("DELETE", r"/api/candidates/[^/]+", DELETE_RECORDS),
        ("POST", r"/api/candidates/[^/]+/(upload-resume|parsed-resume)", CANDIDATES_ADD),
        ("POST", r"/api/resume/(save-candidate|confirm)", CANDIDATES_ADD),
        ("POST", r"/api/applications/\d+/(advance|skip|reject|decline)", PIPELINE_MOVE),
        ("POST", r"/api/applications/\d+/interviews", PIPELINE_MOVE),
        ("DELETE", r"/api/interviews/\d+", PIPELINE_MOVE),
        ("POST", r"/api/interviews/\d+/feedback", FEEDBACK_SUBMIT),
        ("POST", r"/api/team/users", USERS_INVITE),
        ("PUT", r"/api/team/users/[^/]+/role", USERS_CHANGE_ROLE),
        ("DELETE", r"/api/team/users/[^/]+", DELETE_RECORDS),
        ("PUT", r"/api/team/me", PROFILE_EDIT),
        ("PUT", r"/api/team/me/password", PROFILE_EDIT),
    ]
]


def route_permission(method: str, path: str) -> Optional[str]:
    """The permission a mutating request needs, or None for admin-only."""
    normalized = path.rstrip("/") or "/"
    for route_method, pattern, permission in ROUTE_PERMISSIONS:
        if route_method == method and pattern.fullmatch(normalized):
            return permission
    return None
```

- [ ] **Step 5: Run the tests**

Run: `poetry run pytest backend/tests/test_permissions.py -q`
Expected: all pass (11 matrix cells, 4 single tests, 21 route cases).

- [ ] **Step 6: Commit**

Write `$S\commit-b2.txt`:

```
feat: permission table for the four staff roles

One table drives the write gate, per-route checks, and (next) the web
app. Unlisted mutating routes stay admin-only, so a forgotten route is
denied rather than exposed. Every cell of the spec's matrix is pinned by
a test that names the broken promise when it fails.
```

```powershell
git add backend/utils/auth.py backend/utils/permissions.py backend/tests/test_permissions.py
git commit -F "$S\commit-b2.txt"
```

---

### Task 3: The write gate reads roles from the database and the permission table

**Files:**
- Modify: `backend/utils/auth.py` (`request_identity`, `enforce_read_only`)
- Modify: `backend/tests/conftest.py` (staff users, clients, `scoped_application`)
- Modify: `backend/tests/test_auth.py` (staff-role route walk)

- [ ] **Step 1: Add the staff fixtures to conftest**

In `backend/tests/conftest.py` (it already imports `Job`, `JobApplication`, `User`, `hash_password`, and `create_access_token`), add after `ADMIN_PASSWORD = "contract-suite-admin-password"`:

```python
STAFF_PASSWORD = "contract-suite-staff-password"
STAFF_ROLES_UNDER_TEST = ("hiring_manager", "hiring_team", "interviewer")
```

Append after the `demo_client` fixture:

```python
@pytest.fixture(scope="session")
def staff_users(db_session: Session) -> dict:
    """One user per non-admin staff role (ATS Phase B), keyed by role."""
    users = {}
    for role in STAFF_ROLES_UNDER_TEST:
        user = User(
            email=f"{role.replace('_', '-')}@{SEED_EMAIL_DOMAIN}",
            name=f"Test {role.replace('_', ' ').title()}",
            hashed_password=hash_password(STAFF_PASSWORD),
            role=role,
            created_at=SEED_EPOCH,
        )
        db_session.add(user)
        users[role] = user
    # Commit, not flush: a handler that rolls back on an error would otherwise
    # take these users with it, and every later staff test would get a 401.
    db_session.commit()
    return users


def _client_for(user: User) -> TestClient:
    return TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Authorization": f"Bearer {create_access_token(user)}"},
    )


@pytest.fixture(scope="session")
def hiring_manager_client(override_get_db, seed, staff_users):
    return _client_for(staff_users["hiring_manager"])


@pytest.fixture(scope="session")
def hiring_team_client(override_get_db, seed, staff_users):
    return _client_for(staff_users["hiring_team"])


@pytest.fixture(scope="session")
def interviewer_client(override_get_db, seed, staff_users):
    return _client_for(staff_users["interviewer"])


@pytest.fixture(scope="module")
def scoped_application(db_session: Session, seed):
    """A job and an application of their own, for interview and scoping tests.

    Kept off the seeded application on purpose: test_pipeline expects that one
    to have no stage rows when each of its tests starts. Removed (with every
    interview and feedback row, by cascade) when the module finishes.
    """
    from backend.services import pipeline_service as ps

    job = Job(
        title="Scope Test Engineer",
        department="Engineering",
        job_overview="Exists for interview and access tests.",
        required_qualifications="Python",
        location="Remote",
        location_type="remote",
        job_type="full_time",
        experience_level="mid",
        status="open",
        skills="Python",
        job_metadata={},
        views=0,
        applications=1,
        created_at=SEED_EPOCH,
        updated_at=SEED_EPOCH,
    )
    db_session.add(job)
    db_session.flush()
    application = JobApplication(
        job_id=job.id,
        candidate_id=seed["candidate_ids"][2],
        status="active",
        applied_at=SEED_EPOCH,
        updated_at=SEED_EPOCH,
        source="direct",
    )
    db_session.add(application)
    db_session.flush()
    ps.start_application(db_session, application)
    db_session.commit()

    yield {
        "job_id": job.id,
        "application_id": application.id,
        "candidate_id": seed["candidate_ids"][2],
    }

    db_session.rollback()
    leftover = db_session.get(Job, job.id)
    if leftover is not None:
        db_session.delete(leftover)
    db_session.commit()
```

- [ ] **Step 2: Write the failing gate tests**

In `backend/tests/test_auth.py`, extend the imports:

```python
from backend.tests.conftest import ADMIN_PASSWORD, SEED_EMAIL_DOMAIN, STAFF_ROLES_UNDER_TEST
from backend.utils.permissions import can, route_permission
```

Append at the end of the file:

```python
# --- staff roles (ATS Phase B) ---------------------------------------------


def _staff_cases():
    """(role, method, path) for every mutating route the role is NOT granted."""
    cases = []
    for role in STAFF_ROLES_UNDER_TEST:
        for method, path in MUTATING_ROUTES:
            permission = route_permission(method, _concrete(path))
            if permission is not None and can(role, permission):
                continue
            cases.append((role, method, path))
    return cases


STAFF_DENIED = _staff_cases()


def test_the_staff_walk_covers_something_for_every_role():
    roles = {role for role, _, _ in STAFF_DENIED}
    assert roles == set(STAFF_ROLES_UNDER_TEST)


@pytest.mark.parametrize(
    ("role", "method", "path"),
    STAFF_DENIED,
    ids=[f"{r} {m} {p}" for r, m, p in STAFF_DENIED],
)
def test_staff_roles_are_refused_routes_they_are_not_granted(
    role, method, path, hiring_manager_client, hiring_team_client, interviewer_client
):
    client = {
        "hiring_manager": hiring_manager_client,
        "hiring_team": hiring_team_client,
        "interviewer": interviewer_client,
    }[role]
    response = client.request(method, _concrete(path))
    assert response.status_code == 403, (
        f"{role} {method} {path} was not refused (got {response.status_code})"
    )


def test_a_granted_route_passes_the_gate_for_a_hiring_manager(hiring_manager_client, seed):
    # 404 or 422 means the gate let it through to the handler.
    response = hiring_manager_client.put("/api/jobs/999999", json={})
    assert response.status_code in (404, 422)


def test_a_role_change_takes_effect_on_the_next_request(db_session, staff_users, client):
    """The role comes from the database, not from the token's claim."""
    from backend.models.models import User

    user = User(
        email=f"demoted@{SEED_EMAIL_DOMAIN}", name="Soon Demoted", role="hiring_manager"
    )
    db_session.add(user)
    db_session.commit()  # commit, not flush: a handler rollback must not undo it
    token = create_access_token(user)  # claim says hiring_manager
    headers = {"Authorization": f"Bearer {token}"}

    assert client.put("/api/jobs/999999", json={}, headers=headers).status_code in (404, 422)

    user.role = "interviewer"
    db_session.commit()
    assert client.put("/api/jobs/999999", json={}, headers=headers).status_code == 403

    db_session.delete(user)
    db_session.commit()
    assert client.put("/api/jobs/999999", json={}, headers=headers).status_code == 401
```

- [ ] **Step 3: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_auth.py -q -k "staff or granted or role_change"`
Expected: FAIL. Staff roles get 403 today (the gate admits only admin), so `test_a_granted_route_passes...` fails with 403, and `test_a_role_change...` fails on its first assertion.

- [ ] **Step 4: Rewrite the gate**

In `backend/utils/auth.py`, add after `current_role` (keep `current_role`; other code may import it):

```python
def request_identity(request: Request, db: Session) -> tuple[Optional[str], Optional[User]]:
    """(role, user) for this request, read from the database.

    The token's role claim is what was true when it was issued; a role change
    or a deleted account must take effect on the next request, not when a
    24-hour token expires. Demo tokens skip the lookup: the demo role cannot
    change and the public demo is most of the traffic, so `user` is None for
    them. An unreadable token counts as anonymous here; whether that is fatal
    is the route's business. Cached on `request.state` so both app-wide gates
    and the handlers share one query.
    """
    cached = getattr(request.state, "identity", None)
    if cached is not None:
        return cached

    identity: tuple[Optional[str], Optional[User]] = (None, None)
    token = bearer_token(request)
    if token:
        try:
            claims = decode_access_token(token)
        except HTTPException:
            claims = None
        if claims is not None:
            if claims.get("role") == ROLE_DEMO:
                identity = (ROLE_DEMO, None)
            else:
                user = db.query(User).filter(User.id == claims.get("sub")).first()
                if user is not None:
                    identity = (user.role, user)
    request.state.identity = identity
    return identity
```

Replace the whole `enforce_read_only` function with:

```python
def enforce_read_only(request: Request, db: Session = Depends(get_db)) -> None:
    """Writes need a role that the permission table grants. Installed app-wide.

    The UI also hides mutating controls, but a hidden button is not an access
    control: anyone can POST straight at the API. This is the gate; the UI is
    courtesy (spec section 2).

    Anonymous callers are refused (401), not just the demo role (403). `/docs`
    is deliberately public, and Swagger UI's "Try it out" sends requests with
    no Authorization header at all.

    ATS Phase B: admin may write anything. The other staff roles may write
    only where `ROUTE_PERMISSIONS` grants them; a route missing from that
    table is admin-only, so a forgotten route is denied rather than exposed.
    """
    if request.method not in MUTATING_METHODS:
        return
    path = request.url.path.rstrip("/") or "/"
    if path in READ_ONLY_POST_PATHS:
        return

    role, _ = request_identity(request, db)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to modify data",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if role == ROLE_ADMIN:
        return
    if role == ROLE_DEMO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This is a read-only demo account. Sign in as an administrator to "
                "change data."
            ),
        )

    # Imported here: permissions imports this module for the role constants.
    from backend.utils.permissions import can, role_label, route_permission

    permission = route_permission(request.method, path)
    if permission is not None and can(role, permission):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Your role ({role_label(role)}) cannot make this change. "
            "Ask an administrator if you need it."
        ),
    )
```

- [ ] **Step 5: Run the auth suite**

Run: `poetry run pytest backend/tests/test_auth.py backend/tests/test_permissions.py -q`
Expected: all pass. The demo and anonymous walks are unchanged; the staff walk adds one case per (role, unlisted route).

- [ ] **Step 6: Commit**

Write `$S\commit-b3.txt`:

```
feat: write gate grants staff roles from the permission table

Roles are now read from the database once per request, so demoting or
deleting someone takes effect immediately instead of when their token
expires; demo tokens skip the lookup. A route walk proves every staff
role is refused each mutating route it is not granted, and a test
demotes a hiring manager mid-session to show the next write is refused.
```

```powershell
git add backend/utils/auth.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -F "$S\commit-b3.txt"
```

---
### Task 4: Access rules, interview and feedback service, pipeline hook

**Files:**
- Create: `backend/services/access_service.py` (the two rules; the gate comes in Task 6)
- Create: `backend/services/feedback_service.py`
- Modify: `backend/services/pipeline_service.py`
- Test: `backend/tests/test_feedback.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_feedback.py`:

```python
from backend.models.models import Candidate, JobApplication
from backend.services import feedback_service as fs
from backend.services import pipeline_service as ps
from backend.services.access_service import can_see_score, visible_candidate_ids


@pytest.fixture(autouse=True)
def _fresh(db_session, scoped_application):
    """Every test starts with the scoped application at stage 1, nobody assigned.

    Commits rather than flushes: a route that hits a 409 rolls the session
    back to its last commit (the Phase A lesson).
    """
    yield
    db_session.rollback()
    application = db_session.get(JobApplication, scoped_application["application_id"])
    for row in list(application.stages):
        db_session.delete(row)  # interviews and feedback go with it (cascade)
    for stage in ps.ensure_job_stages(db_session, application.job_id):
        stage.default_interviewers.clear()
        stage.enabled = True
    application.status = "active"
    db_session.flush()
    db_session.expire(application)
    ps.start_application(db_session, db_session.get(JobApplication, scoped_application["application_id"]))
    db_session.commit()


@pytest.fixture
def application(db_session, scoped_application) -> JobApplication:
    return db_session.get(JobApplication, scoped_application["application_id"])


def _row(application, key):
    return next(r for r in application.stages if r.stage.key == key)


def test_assign_is_idempotent_and_refuses_outcomes(db_session, application, staff_users):
    interviewer = staff_users["interviewer"]
    first = fs.assign(db_session, _row(application, "resume_submitted"), interviewer)
    again = fs.assign(db_session, _row(application, "resume_submitted"), interviewer)
    assert first.id == again.id
    assert first.assignment_source == "manual"
    with pytest.raises(fs.FeedbackError):
        fs.assign(db_session, _row(application, "hired"), interviewer)


def test_assign_refuses_people_outside_the_team(db_session, application):
    with pytest.raises(fs.FeedbackError) as caught:
        fs.assign(db_session, _row(application, "hm_review"), None)
    assert caught.value.status_code == 422


def test_default_interviewers_are_assigned_when_the_stage_starts(db_session, application, staff_users):
    stages = {s.key: s for s in ps.ensure_job_stages(db_session, application.job_id)}
    fs.set_default_interviewers(db_session, stages["hm_review"], [staff_users["interviewer"].id])
    ps.advance(db_session, application)
    row = _row(application, "hm_review")
    assert [(i.interviewer_id, i.assignment_source) for i in row.interviews] == [
        (staff_users["interviewer"].id, "default")
    ]


def test_feedback_is_for_the_assignee_once(db_session, application, staff_users):
    interviewer, colleague = staff_users["interviewer"], staff_users["hiring_team"]
    interview = fs.assign(db_session, _row(application, "resume_submitted"), interviewer)
    with pytest.raises(fs.FeedbackError) as not_theirs:
        fs.submit_feedback(db_session, interview, colleague, 4, "hire", "")
    assert not_theirs.value.status_code == 403
    fs.submit_feedback(db_session, interview, interviewer, 4, "hire", "  Clear thinker.  ")
    assert interview.feedback.notes == "Clear thinker."
    with pytest.raises(fs.FeedbackError) as twice:
        fs.submit_feedback(db_session, interview, interviewer, 5, "strong_hire", "")
    assert twice.value.status_code == 409


def test_feedback_waits_for_the_stage_to_start(db_session, application, staff_users):
    interview = fs.assign(db_session, _row(application, "technical_interview"), staff_users["interviewer"])
    with pytest.raises(fs.FeedbackError):
        fs.submit_feedback(db_session, interview, staff_users["interviewer"], 3, "hire", "")


def test_unassign_keeps_submitted_feedback_on_record(db_session, application, staff_users):
    interview = fs.assign(db_session, _row(application, "resume_submitted"), staff_users["interviewer"])
    fs.submit_feedback(db_session, interview, staff_users["interviewer"], 2, "no_hire", "")
    with pytest.raises(fs.FeedbackError):
        fs.unassign(db_session, interview)


def test_pending_feedback_lists_started_stages_only(db_session, application, staff_users):
    now = fs.assign(db_session, _row(application, "resume_submitted"), staff_users["interviewer"])
    later = fs.assign(db_session, _row(application, "case_study"), staff_users["interviewer"])
    pending = fs.pending_feedback(db_session, staff_users["interviewer"].id)
    assert now in pending and later not in pending
    assert fs.interview_state(now) == "waiting"
    assert fs.interview_state(later) == "upcoming"


def test_visibility_rules(db_session, application, staff_users, seed):
    interviewer = staff_users["interviewer"]
    assert visible_candidate_ids(db_session, staff_users["hiring_team"]) is None
    assert visible_candidate_ids(db_session, None) is None
    assert application.candidate_id not in visible_candidate_ids(db_session, interviewer)

    interview = fs.assign(db_session, _row(application, "resume_submitted"), interviewer)
    assert visible_candidate_ids(db_session, interviewer) == {application.candidate_id}
    assert not can_see_score(db_session, interviewer, application.candidate_id)
    assert can_see_score(db_session, staff_users["hiring_team"], application.candidate_id)
    assert can_see_score(db_session, None, application.candidate_id)

    fs.submit_feedback(db_session, interview, interviewer, 4, "hire", "")
    assert can_see_score(db_session, interviewer, application.candidate_id)


def test_display_name_never_falls_back_to_an_email(db_session, staff_users):
    from backend.models.models import User

    nameless = User(email="private.person@example.com", role="admin")
    assert fs.display_name(nameless) == "Admin"
    assert "@" not in fs.display_name(nameless)
    assert fs.display_name(staff_users["interviewer"]) == "Test Interviewer"
    assert fs.display_name(None) == "Former team member"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_feedback.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.feedback_service'`

- [ ] **Step 3: Write the access rules**

Create `backend/services/access_service.py`:

```python
"""What a signed-in person may see (ATS Phase B, spec 2026-10-03 section 8).

Two rules from the spec:

- An interviewer sees only the candidates they interview
  (`visible_candidate_ids`). Every other role sees everyone.
- An interviewer does not see a candidate's AI score, or colleagues'
  feedback on them, until they have submitted their own feedback on that
  candidate (`can_see_score`).

`enforce_interviewer_scope` (added below the rules) is installed app-wide
next to the write gate. Later phases that list or export candidates must
filter through `visible_candidate_ids` and must not expose a score where
`can_see_score` is False.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from backend.models.models import ApplicationStage, Feedback, Interview, JobApplication, User
from backend.utils.auth import ROLE_INTERVIEWER
from backend.utils.permissions import SCORE_BEFORE_FEEDBACK, can

SCORE_HIDDEN_DETAIL = "Submit your feedback on this candidate to see their match scores."


def visible_candidate_ids(db: Session, user: Optional[User]) -> Optional[set[str]]:
    """None means no restriction. An interviewer gets the candidates they interview."""
    if user is None or user.role != ROLE_INTERVIEWER:
        return None
    rows = (
        db.query(JobApplication.candidate_id)
        .join(ApplicationStage, ApplicationStage.application_id == JobApplication.id)
        .join(Interview, Interview.application_stage_id == ApplicationStage.id)
        .filter(Interview.interviewer_id == user.id)
        .distinct()
        .all()
    )
    return {candidate_id for (candidate_id,) in rows}


def can_see_score(db: Session, user: Optional[User], candidate_id: str) -> bool:
    """False only for a role without `score.before_feedback` that has not yet
    submitted feedback on any of this candidate's interviews."""
    if user is None or can(user.role, SCORE_BEFORE_FEEDBACK):
        return True
    submitted = (
        db.query(Feedback.id)
        .join(Interview, Feedback.interview_id == Interview.id)
        .join(ApplicationStage, Interview.application_stage_id == ApplicationStage.id)
        .join(JobApplication, ApplicationStage.application_id == JobApplication.id)
        .filter(Interview.interviewer_id == user.id, JobApplication.candidate_id == candidate_id)
        .first()
    )
    return submitted is not None


def request_user(request: Request) -> Optional[User]:
    """The staff User behind this request, as resolved by the app-wide gates.

    None for anonymous callers and for the demo role (which has no per-user
    restrictions). Handlers use this instead of a second token lookup.
    """
    identity = getattr(request.state, "identity", None)
    return identity[1] if identity else None
```

- [ ] **Step 4: Write the interview and feedback service**

Create `backend/services/feedback_service.py`:

```python
"""Interview assignments and feedback (ATS Phase B, spec 2026-10-03 section 3.1).

Like pipeline_service, these mutate the session and never commit, so a router
composes them and commits once. Feedback is shown to people and never read by
the scorer; the transparency page publishes FEEDBACK_USED_FOR and
FEEDBACK_NEVER_USED_FOR, and test_feedback pins that the scoring modules do
not mention feedback at all.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from backend.models.models import (
    ApplicationStage,
    Candidate,
    Feedback,
    Interview,
    PipelineStage,
    StageDefaultInterviewer,
    User,
)
from backend.services import pipeline_service as ps
from backend.services.access_service import can_see_score
from backend.utils.auth import STAFF_ROLES
from backend.utils.permissions import role_label

MANUAL = "manual"
DEFAULT = "default"

RECOMMENDATIONS = ("strong_hire", "hire", "no_hire", "strong_no_hire")

FEEDBACK_USED_FOR = [
    "Shown to the hiring team on the candidate's page, next to the stage it was given for.",
    "Counted on the Interviews page so nobody's feedback is forgotten.",
]
FEEDBACK_NEVER_USED_FOR = [
    "The match score. The ranker reads the candidate's profile and the job, never feedback.",
    "Search ranking, including the assistant's candidate search.",
    "Moving a candidate. Only a person presses Advance, Skip, Reject, or Decline.",
]

# Stage-row statuses at which the interview has happened (or is happening),
# so feedback is due.
_STARTED = (ps.IN_PROGRESS, ps.PASSED, ps.FAILED)


class FeedbackError(Exception):
    """A request the rules refuse. `status_code` is what the router returns."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def display_name(user: Optional[User]) -> str:
    """A person's name for screens other people see. Never their email: the
    demo can see these names, and a real admin account may have no name."""
    if user is None:
        return "Former team member"
    return user.name or role_label(user.role)


def candidate_name(candidate: Optional[Candidate]) -> str:
    if candidate is None:
        return "Unnamed candidate"
    return " ".join(p for p in (candidate.first_name, candidate.last_name) if p) or "Unnamed candidate"


def _team_member(user: Optional[User]) -> User:
    if user is None or user.role not in STAFF_ROLES:
        raise FeedbackError("Choose someone on the team.", 422)
    return user


def assign(db: Session, row: ApplicationStage, user: Optional[User], source: str = MANUAL) -> Interview:
    """Put `user` on this stage of this application. Idempotent."""
    user = _team_member(user)
    if row.stage.kind != ps.ROUND:
        raise FeedbackError("Interviewers are assigned to rounds, not outcomes.")
    if row.application.status in ps.TERMINAL:
        raise FeedbackError(f"This application is already {row.application.status}.")
    if row.status == ps.SKIPPED:
        raise FeedbackError("That stage was skipped for this candidate.")
    existing = next((i for i in row.interviews if i.interviewer_id == user.id), None)
    if existing is not None:
        return existing
    interview = Interview(interviewer_id=user.id, assignment_source=source, created_at=datetime.utcnow())
    row.interviews.append(interview)
    db.flush()
    return interview


def unassign(db: Session, interview: Interview) -> None:
    if interview.feedback is not None:
        raise FeedbackError("Feedback has been submitted for this interview, so it stays on the record.")
    db.delete(interview)
    db.flush()


def apply_default_interviewers(db: Session, row: ApplicationStage) -> list[Interview]:
    """Called by pipeline_service.on_stage_entered when an application starts a round."""
    defaults = (
        db.query(StageDefaultInterviewer)
        .filter(StageDefaultInterviewer.pipeline_stage_id == row.stage_id)
        .order_by(StageDefaultInterviewer.id)
        .all()
    )
    out = []
    for default in defaults:
        if default.user is None or default.user.role not in STAFF_ROLES:
            continue
        out.append(assign(db, row, default.user, source=DEFAULT))
    return out


def set_default_interviewers(db: Session, stage: PipelineStage, user_ids: Iterable[str]) -> list[User]:
    """Replace the stage's default interviewers. Applies to applications that
    enter the stage from now on; nobody already there is reassigned."""
    if stage.kind != ps.ROUND:
        raise FeedbackError("Default interviewers belong to rounds, not outcomes.")
    users = [_team_member(db.get(User, user_id)) for user_id in dict.fromkeys(user_ids)]
    stage.default_interviewers.clear()
    db.flush()
    for user in users:
        stage.default_interviewers.append(StageDefaultInterviewer(user_id=user.id))
    db.flush()
    return users


def submit_feedback(
    db: Session,
    interview: Interview,
    user: User,
    rating: int,
    recommendation: str,
    notes: Optional[str],
) -> Feedback:
    if interview.interviewer_id != user.id:
        raise FeedbackError("Only the assigned interviewer can submit this feedback.", 403)
    if interview.feedback is not None:
        raise FeedbackError("Feedback for this interview has already been submitted.")
    if interview.application_stage.status not in _STARTED:
        raise FeedbackError("This stage has not started yet, so there is nothing to give feedback on.")
    if recommendation not in RECOMMENDATIONS:
        raise FeedbackError("Choose one of the four recommendations.", 422)
    if not 1 <= int(rating) <= 5:
        raise FeedbackError("A rating is from 1 to 5.", 422)
    feedback = Feedback(
        rating=int(rating),
        recommendation=recommendation,
        notes=(notes or "").strip() or None,
        submitted_at=datetime.utcnow(),
    )
    interview.feedback = feedback
    db.flush()
    return feedback


def interview_state(interview: Interview) -> str:
    """upcoming, waiting (for feedback), submitted, or skipped."""
    if interview.feedback is not None:
        return "submitted"
    status = interview.application_stage.status
    if status in _STARTED:
        return "waiting"
    if status == ps.SKIPPED:
        return "skipped"
    return "upcoming"


def pending_feedback(db: Session, interviewer_id: Optional[str] = None) -> list[Interview]:
    """Interviews whose stage has started and that have no feedback yet, oldest first."""
    query = (
        db.query(Interview)
        .join(ApplicationStage, Interview.application_stage_id == ApplicationStage.id)
        .outerjoin(Feedback, Feedback.interview_id == Interview.id)
        .filter(Feedback.id.is_(None), ApplicationStage.status.in_(_STARTED))
    )
    if interviewer_id is not None:
        query = query.filter(Interview.interviewer_id == interviewer_id)
    return query.order_by(ApplicationStage.started_at, Interview.id).all()


def can_view_feedback(db: Session, viewer: Optional[User], interview: Interview) -> bool:
    """Your own feedback always; colleagues' under the same rule as the score."""
    if viewer is not None and interview.interviewer_id == viewer.id:
        return True
    return can_see_score(db, viewer, interview.application_stage.application.candidate_id)
```

- [ ] **Step 5: Add the pipeline hook**

In `backend/services/pipeline_service.py`, add this function directly above `def start_application`:

```python
def on_stage_entered(db: Session, row: ApplicationStage) -> None:
    """Runs whenever an application starts a round (ATS Phase B: default interviewers)."""
    if row.application.status in TERMINAL:
        return
    # Imported here: feedback_service imports this module.
    from backend.services import feedback_service

    feedback_service.apply_default_interviewers(db, row)
```

In `ensure_application_stages`, replace

```python
    now = datetime.utcnow()
    started = any(row.status != PENDING for row in existing.values())
    for stage in stages:
        if stage.id in existing:
            continue
        row = ApplicationStage(application_id=application.id, stage_id=stage.id, status=PENDING)
        if not started and stage.kind == ROUND and stage.enabled:
            row.status = IN_PROGRESS
            row.started_at = application.applied_at or now
            started = True
        db.add(row)
    db.flush()
    db.refresh(application)
```

with

```python
    now = datetime.utcnow()
    started = any(row.status != PENDING for row in existing.values())
    entered: Optional[ApplicationStage] = None
    for stage in stages:
        if stage.id in existing:
            continue
        row = ApplicationStage(application_id=application.id, stage_id=stage.id, status=PENDING)
        if not started and stage.kind == ROUND and stage.enabled:
            row.status = IN_PROGRESS
            row.started_at = application.applied_at or now
            started = True
            entered = row
        db.add(row)
    db.flush()
    if entered is not None:
        on_stage_entered(db, entered)
    db.refresh(application)
```

In `advance`, replace

```python
    nxt.status = IN_PROGRESS
    nxt.started_at = now
    sync_candidate_status(db, application)


def skip(
```

with

```python
    nxt.status = IN_PROGRESS
    nxt.started_at = now
    on_stage_entered(db, nxt)
    sync_candidate_status(db, application)


def skip(
```

and in `skip`, replace its last three lines

```python
    nxt.status = IN_PROGRESS
    nxt.started_at = now
    sync_candidate_status(db, application)
```

with

```python
    nxt.status = IN_PROGRESS
    nxt.started_at = now
    on_stage_entered(db, nxt)
    sync_candidate_status(db, application)
```

(The `skip` body is the only remaining place with those three lines once `advance` is edited, so the Edit is unique if done in this order.)

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_feedback.py backend/tests/test_pipeline.py -q`
Expected: all pass. test_pipeline is unchanged: no job there has default interviewers, so the hook does nothing.

- [ ] **Step 7: Commit**

Write `$S\commit-b4.txt`:

```
feat: interview assignment, feedback, and the two visibility rules

feedback_service owns assigning, default interviewers, and submitting;
access_service owns the spec's two rules: interviewers see only the
candidates they interview, and see a score (or colleagues' feedback)
only after giving their own. Pipeline transitions now call a hook when
a round starts, which assigns that stage's default interviewers.
Feedback is final once submitted and stays on record if someone is
unassigned. Names shown to others never fall back to an email.
```

```powershell
git add backend/services/access_service.py backend/services/feedback_service.py backend/services/pipeline_service.py backend/tests/test_feedback.py
git commit -F "$S\commit-b4.txt"
```

---

### Task 5: Interview and feedback routes; delete the mock router

**Files:**
- Create: `backend/models/team.py` (only `MessageOut` is needed now; Task 7 fills the rest)
- Create: `backend/models/feedback.py`
- Create: `backend/routers/feedback.py`
- Delete: `backend/routers/interviews.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_feedback.py`

- [ ] **Step 1: Write the failing route tests**

Append to `backend/tests/test_feedback.py`:

```python
def _assign(client, application_id, stage_key, user):
    return client.post(
        f"/api/applications/{application_id}/interviews",
        json={"stage_key": stage_key, "interviewer_id": user.id},
    )


def test_hiring_team_can_assign_and_the_interviewer_can_give_feedback(
    hiring_team_client, interviewer_client, scoped_application, staff_users
):
    app_id = scoped_application["application_id"]
    assigned = _assign(hiring_team_client, app_id, "resume_submitted", staff_users["interviewer"])
    assert assigned.status_code == 201, assigned.text
    interview = assigned.json()
    assert interview["state"] == "waiting"
    assert interview["interviewer_name"] == "Test Interviewer"

    given = interviewer_client.post(
        f"/api/interviews/{interview['id']}/feedback",
        json={"rating": 4, "recommendation": "hire", "notes": "Solid fundamentals."},
    )
    assert given.status_code == 200, given.text
    assert given.json()["feedback"]["rating"] == 4

    again = interviewer_client.post(
        f"/api/interviews/{interview['id']}/feedback",
        json={"rating": 5, "recommendation": "strong_hire"},
    )
    assert again.status_code == 409


def test_assignment_needs_pipeline_permission(interviewer_client, demo_client, scoped_application, staff_users):
    app_id = scoped_application["application_id"]
    assert _assign(interviewer_client, app_id, "hm_review", staff_users["interviewer"]).status_code == 403
    assert _assign(demo_client, app_id, "hm_review", staff_users["interviewer"]).status_code == 403


def test_feedback_validation(hiring_team_client, interviewer_client, scoped_application, staff_users):
    interview = _assign(
        hiring_team_client, scoped_application["application_id"], "resume_submitted", staff_users["interviewer"]
    ).json()
    for bad in ({"rating": 0, "recommendation": "hire"}, {"rating": 3, "recommendation": "maybe"}):
        response = interviewer_client.post(f"/api/interviews/{interview['id']}/feedback", json=bad)
        assert response.status_code == 422


def test_someone_elses_interview_is_403(hiring_team_client, scoped_application, staff_users):
    interview = _assign(
        hiring_team_client, scoped_application["application_id"], "resume_submitted", staff_users["interviewer"]
    ).json()
    response = hiring_team_client.post(
        f"/api/interviews/{interview['id']}/feedback", json={"rating": 3, "recommendation": "hire"}
    )
    assert response.status_code == 403


def test_colleagues_feedback_is_hidden_until_you_give_yours(
    hiring_team_client, interviewer_client, scoped_application, staff_users
):
    app_id = scoped_application["application_id"]
    theirs = _assign(hiring_team_client, app_id, "resume_submitted", staff_users["hiring_team"]).json()
    mine = _assign(hiring_team_client, app_id, "resume_submitted", staff_users["interviewer"]).json()
    hiring_team_client.post(
        f"/api/interviews/{theirs['id']}/feedback", json={"rating": 2, "recommendation": "no_hire"}
    )

    before = {i["id"]: i for i in interviewer_client.get(f"/api/applications/{app_id}/interviews").json()}
    assert before[theirs["id"]]["feedback"] is None
    assert before[theirs["id"]]["feedback_hidden"] is True

    interviewer_client.post(f"/api/interviews/{mine['id']}/feedback", json={"rating": 4, "recommendation": "hire"})
    after = {i["id"]: i for i in interviewer_client.get(f"/api/applications/{app_id}/interviews").json()}
    assert after[theirs["id"]]["feedback"]["recommendation"] == "no_hire"


def test_unassign_route(hiring_team_client, scoped_application, staff_users):
    interview = _assign(
        hiring_team_client, scoped_application["application_id"], "hm_review", staff_users["interviewer"]
    ).json()
    assert hiring_team_client.delete(f"/api/interviews/{interview['id']}").status_code == 200
    assert hiring_team_client.delete(f"/api/interviews/{interview['id']}").status_code == 404


def test_default_interviewer_routes(
    hiring_manager_client, hiring_team_client, admin_client, scoped_application, staff_users
):
    job_id = scoped_application["job_id"]
    path = f"/api/jobs/{job_id}/stages/hm_review/default-interviewers"
    body = {"user_ids": [staff_users["interviewer"].id]}
    assert hiring_team_client.put(path, json=body).status_code == 403
    saved = hiring_manager_client.put(path, json=body)
    assert saved.status_code == 200, saved.text
    hm_review = next(s for s in saved.json()["stages"] if s["stage_key"] == "hm_review")
    assert [u["id"] for u in hm_review["users"]] == [staff_users["interviewer"].id]

    moved = admin_client.post(f"/api/applications/{scoped_application['application_id']}/advance", json={})
    assert moved.status_code == 200
    interviews = admin_client.get(f"/api/applications/{scoped_application['application_id']}/interviews").json()
    assert [(i["stage_key"], i["assignment_source"]) for i in interviews] == [("hm_review", "default")]


def test_interview_lists(hiring_team_client, interviewer_client, demo_client, scoped_application, staff_users):
    _assign(hiring_team_client, scoped_application["application_id"], "resume_submitted", staff_users["interviewer"])
    mine = interviewer_client.get("/api/interviews", params={"scope": "mine"}).json()["items"]
    assert [i["candidate_id"] for i in mine] == [scoped_application["candidate_id"]]
    assert mine[0]["score_visible"] is False
    assert interviewer_client.get("/api/interviews", params={"scope": "all"}).status_code == 403
    pending = hiring_team_client.get("/api/interviews", params={"scope": "pending"}).json()["items"]
    assert any(i["candidate_id"] == scoped_application["candidate_id"] for i in pending)
    assert demo_client.get("/api/interviews", params={"scope": "all"}).status_code == 200
    assert demo_client.get("/api/interviews", params={"scope": "mine"}).json()["items"] == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_feedback.py -q -k "assign or feedback or default_interviewer or lists or colleagues"`
Expected: FAIL. `POST /api/applications/{id}/interviews` answers 404 "Unknown action 'interviews'" (the Phase A transition route catches it).

- [ ] **Step 3: Write the Pydantic shapes**

Create `backend/models/team.py`:

```python
"""Request and response shapes for the team router (ATS Phase B)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

StaffRole = Literal["admin", "hiring_manager", "hiring_team", "interviewer"]


class MessageOut(BaseModel):
    message: str


class TeamMember(BaseModel):
    id: str
    # Omitted (null) for viewers who cannot invite people: the demo can see
    # the team page, and a real administrator's address must not be public.
    email: Optional[str] = None
    name: Optional[str] = None
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamListResponse(BaseModel):
    members: List[TeamMember]


class InviteRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    role: StaffRole


class InviteResponse(BaseModel):
    member: TeamMember
    temporary_password: str


class RoleChangeRequest(BaseModel):
    role: StaffRole


class ProfileResponse(TeamMember):
    timezone: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    timezone: Optional[str] = Field(default=None, max_length=64)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12, max_length=128)
```

Create `backend/models/feedback.py`:

```python
"""Request and response shapes for interviews and feedback (ATS Phase B)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Recommendation = Literal["strong_hire", "hire", "no_hire", "strong_no_hire"]
InterviewState = Literal["upcoming", "waiting", "submitted", "skipped"]


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    recommendation: Recommendation
    notes: str = Field(default="", max_length=5000)


class FeedbackOut(BaseModel):
    rating: int
    recommendation: str
    notes: Optional[str] = None
    submitted_at: datetime


class InterviewOut(BaseModel):
    id: int
    application_id: int
    stage_key: str
    stage_name: str
    stage_status: str
    state: InterviewState
    interviewer_id: str
    interviewer_name: str
    assignment_source: str
    feedback: Optional[FeedbackOut] = None
    # True when feedback exists but this viewer may not read it yet.
    feedback_hidden: bool = False


class InterviewListItem(InterviewOut):
    candidate_id: str
    candidate_name: str
    job_id: int
    job_title: str
    score_visible: bool


class InterviewListResponse(BaseModel):
    items: List[InterviewListItem]


class AssignRequest(BaseModel):
    stage_key: str = Field(min_length=1, max_length=50)
    interviewer_id: str = Field(min_length=1, max_length=36)


class TeamMemberBrief(BaseModel):
    id: str
    name: str
    role: str


class StageDefaults(BaseModel):
    stage_key: str
    stage_name: str
    users: List[TeamMemberBrief]


class DefaultInterviewersResponse(BaseModel):
    job_id: int
    stages: List[StageDefaults]


class DefaultInterviewersRequest(BaseModel):
    user_ids: List[str] = Field(default_factory=list, max_length=20)
```

- [ ] **Step 4: Write the router**

Create `backend/routers/feedback.py`:

```python
"""Interviews, feedback, and default interviewers (ATS Phase B).

Plain `def` handlers: they do sync ORM work (CLAUDE.md sharp edge). Writes
are gated app-wide by `enforce_read_only` through ROUTE_PERMISSIONS; the
handlers that need the acting user take it from `require(...)`, which restates
the permission where the route is defined.

Mounted *before* the pipeline router in main.py: Phase A's
`POST /applications/{id}/{action}` would otherwise swallow
`POST /applications/{id}/interviews` as an unknown action.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..models.feedback import (
    AssignRequest,
    DefaultInterviewersRequest,
    DefaultInterviewersResponse,
    FeedbackIn,
    FeedbackOut,
    InterviewListItem,
    InterviewListResponse,
    InterviewOut,
    StageDefaults,
    TeamMemberBrief,
)
from ..models.models import Candidate, Interview, Job, JobApplication, User
from ..models.team import MessageOut
from ..services import feedback_service as fs
from ..services import pipeline_service as ps
from ..services.access_service import can_see_score, request_user
from ..utils.auth import ROLE_INTERVIEWER, request_identity
from ..utils.database import get_db
from ..utils.permissions import FEEDBACK_SUBMIT, JOBS_WRITE, PIPELINE_MOVE, require

router = APIRouter()

_STATE_ORDER = {"waiting": 0, "upcoming": 1, "submitted": 2, "skipped": 3}


def _refuse(db: Session, exc: fs.FeedbackError) -> None:
    db.rollback()
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


def _application_or_404(db: Session, application_id: int) -> JobApplication:
    application = db.get(JobApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _interview_or_404(db: Session, interview_id: int) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


def _interview_out(db: Session, interview: Interview, viewer: Optional[User]) -> InterviewOut:
    row = interview.application_stage
    feedback = interview.feedback
    visible = fs.can_view_feedback(db, viewer, interview)
    return InterviewOut(
        id=interview.id,
        application_id=row.application_id,
        stage_key=row.stage.key,
        stage_name=row.stage.name,
        stage_status=row.status,
        state=fs.interview_state(interview),
        interviewer_id=interview.interviewer_id,
        interviewer_name=fs.display_name(interview.interviewer),
        assignment_source=interview.assignment_source,
        feedback=(
            FeedbackOut(
                rating=feedback.rating,
                recommendation=feedback.recommendation,
                notes=feedback.notes,
                submitted_at=feedback.submitted_at,
            )
            if feedback is not None and visible
            else None
        ),
        feedback_hidden=feedback is not None and not visible,
    )


def _list_item(db: Session, interview: Interview, viewer: Optional[User]) -> InterviewListItem:
    application = interview.application_stage.application
    job = db.get(Job, application.job_id)
    return InterviewListItem(
        **_interview_out(db, interview, viewer).model_dump(),
        candidate_id=application.candidate_id,
        candidate_name=fs.candidate_name(db.get(Candidate, application.candidate_id)),
        job_id=application.job_id,
        job_title=job.title if job else "",
        score_visible=can_see_score(db, viewer, application.candidate_id),
    )


def _brief(user: User) -> TeamMemberBrief:
    return TeamMemberBrief(id=user.id, name=fs.display_name(user), role=user.role)


def _defaults(db: Session, job: Job) -> DefaultInterviewersResponse:
    stages = ps.ensure_job_stages(db, job.id)
    return DefaultInterviewersResponse(
        job_id=job.id,
        stages=[
            StageDefaults(
                stage_key=stage.key,
                stage_name=stage.name,
                users=[_brief(d.user) for d in stage.default_interviewers if d.user is not None],
            )
            for stage in stages
            if stage.kind == ps.ROUND and stage.enabled
        ],
    )


@router.get("/applications/{application_id}/interviews", response_model=list[InterviewOut])
def list_application_interviews(
    application_id: int, request: Request, db: Session = Depends(get_db)
) -> list[InterviewOut]:
    """Everyone assigned to this application, stage by stage, with feedback
    where the viewer may read it."""
    application = _application_or_404(db, application_id)
    rows = ps.ensure_application_stages(db, application)
    viewer = request_user(request)
    out = [_interview_out(db, interview, viewer) for row in rows for interview in row.interviews]
    db.commit()
    return out


@router.post(
    "/applications/{application_id}/interviews",
    response_model=InterviewOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_interviewer(
    application_id: int,
    payload: AssignRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require(PIPELINE_MOVE)),
) -> InterviewOut:
    application = _application_or_404(db, application_id)
    rows = ps.ensure_application_stages(db, application)
    row = next((r for r in rows if r.stage.key == payload.stage_key), None)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No stage named '{payload.stage_key}' on this job.")
    try:
        interview = fs.assign(db, row, db.get(User, payload.interviewer_id))
    except fs.FeedbackError as exc:
        _refuse(db, exc)
    db.commit()
    return _interview_out(db, interview, actor)


@router.delete("/interviews/{interview_id}", response_model=MessageOut)
def unassign_interviewer(
    interview_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require(PIPELINE_MOVE)),
) -> MessageOut:
    interview = _interview_or_404(db, interview_id)
    name = fs.display_name(interview.interviewer)
    try:
        fs.unassign(db, interview)
    except fs.FeedbackError as exc:
        _refuse(db, exc)
    db.commit()
    return MessageOut(message=f"Removed {name} from this stage.")


@router.post("/interviews/{interview_id}/feedback", response_model=InterviewOut)
def submit_feedback(
    interview_id: int,
    payload: FeedbackIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require(FEEDBACK_SUBMIT)),
) -> InterviewOut:
    interview = _interview_or_404(db, interview_id)
    try:
        fs.submit_feedback(db, interview, actor, payload.rating, payload.recommendation, payload.notes)
    except fs.FeedbackError as exc:
        _refuse(db, exc)
    db.commit()
    return _interview_out(db, interview, actor)


@router.get("/interviews", response_model=InterviewListResponse)
def list_interviews(
    request: Request,
    scope: Literal["mine", "pending", "all"] = Query("mine"),
    db: Session = Depends(get_db),
) -> InterviewListResponse:
    """`mine` for anyone signed in, `pending` and `all` for everyone but interviewers."""
    role, user = request_identity(request, db)
    if role == ROLE_INTERVIEWER and scope != "mine":
        raise HTTPException(status_code=403, detail="Interviewers see their own interviews.")
    if scope == "pending":
        interviews = fs.pending_feedback(db)
    elif scope == "mine":
        if user is None:
            return InterviewListResponse(items=[])
        interviews = db.query(Interview).filter(Interview.interviewer_id == user.id).all()
    else:
        interviews = db.query(Interview).order_by(Interview.created_at.desc()).limit(200).all()
    items = [_list_item(db, interview, user) for interview in interviews]
    if scope != "pending":
        items.sort(key=lambda i: (_STATE_ORDER.get(i.state, 9), i.candidate_name))
    return InterviewListResponse(items=items)


@router.get("/jobs/{job_id}/default-interviewers", response_model=DefaultInterviewersResponse)
def get_default_interviewers(job_id: int, db: Session = Depends(get_db)) -> DefaultInterviewersResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    out = _defaults(db, job)
    db.commit()
    return out


@router.put(
    "/jobs/{job_id}/stages/{stage_key}/default-interviewers",
    response_model=DefaultInterviewersResponse,
)
def set_default_interviewers(
    job_id: int,
    stage_key: str,
    payload: DefaultInterviewersRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require(JOBS_WRITE)),
) -> DefaultInterviewersResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    stage = next((s for s in ps.ensure_job_stages(db, job.id) if s.key == stage_key), None)
    if stage is None:
        raise HTTPException(status_code=404, detail=f"No stage named '{stage_key}' on this job.")
    try:
        fs.set_default_interviewers(db, stage, payload.user_ids)
    except fs.FeedbackError as exc:
        _refuse(db, exc)
    db.commit()
    return _defaults(db, job)
```

- [ ] **Step 5: Mount it and delete the mock**

```powershell
git rm backend/routers/interviews.py
```

In `backend/main.py`, change the router import line

```python
from backend.routers import auth, tasks, interviews, pitches, agent, performance, cache, transparency, pipeline
```

to

```python
from backend.routers import auth, tasks, pitches, agent, performance, cache, transparency, pipeline, feedback
```

and replace

```python
app.include_router(interviews.router, prefix="/api", tags=["interviews"])
app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])  # ATS Phase A board and transitions
```

with

```python
# feedback before pipeline: pipeline's POST /applications/{id}/{action} would
# otherwise swallow POST /applications/{id}/interviews.
app.include_router(feedback.router, prefix="/api", tags=["interviews"])  # ATS Phase B
app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])  # ATS Phase A board and transitions
```

Then check nothing else imported the mock:

Run: `poetry run python -c "import backend.main"` (with the two env vars from Conventions set)
Expected: no ImportError.

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_feedback.py backend/tests/test_pipeline.py backend/tests/test_auth.py -q`
Expected: all pass. The auth route walks pick up the new mutating routes automatically.

- [ ] **Step 7: Commit**

Write `$S\commit-b5.txt`:

```
feat: interview, feedback, and default-interviewer endpoints

Replaces the in-memory interviews mock with real routes: assign and
unassign on an application stage, submit feedback (assignee only, once),
list interviews (mine, pending, all), and set a stage's default
interviewers. Colleagues' feedback is redacted for an interviewer until
they submit their own. The router mounts ahead of the pipeline router so
the Phase A action route does not swallow /interviews.
```

```powershell
git add backend/models/team.py backend/models/feedback.py backend/routers/feedback.py backend/main.py backend/tests/test_feedback.py
git commit -F "$S\commit-b5.txt"
```

---

### Task 6: Interviewers see only their candidates; scores wait for feedback

**Files:**
- Modify: `backend/services/access_service.py` (the gate)
- Modify: `backend/main.py` (install it)
- Modify: `backend/routers/candidates.py` (`search_candidates`), `backend/routers/pipeline.py` (`get_job_pipeline`, `_board`), `backend/routers/enhanced_matching.py` (`match_jobs_for_candidate`)
- Test: `backend/tests/test_team_access.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_team_access.py`:

```python
"""Interviewer scoping and score hiding (ATS Phase B, spec section 8).

The route walk mirrors test_auth: instead of listing read routes by hand it
walks the application's own route table, so a read endpoint added later is
closed to interviewers the moment it exists unless someone adds it to
INTERVIEWER_PATHS on purpose.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from backend.main import app
from backend.models.models import JobApplication
from backend.services import feedback_service as fs
from backend.services import pipeline_service as ps
from backend.services.access_service import INTERVIEWER_PATHS, SCORE_HIDDEN_DETAIL
from backend.tests.test_auth import _concrete
from backend.utils.auth import READ_ONLY_POST_PATHS


@pytest.fixture(scope="module")
def assigned(db_session, scoped_application, staff_users):
    application = db_session.get(JobApplication, scoped_application["application_id"])
    interview = fs.assign(db_session, ps.current_stage(application), staff_users["interviewer"])
    db_session.commit()
    return {**scoped_application, "interview_id": interview.id}


def _reads():
    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue  # /docs and /openapi.json are not behind the app dependencies
        normalized = route.path.rstrip("/") or "/"
        if "GET" in route.methods:
            out.append(("GET", route.path))
        if "POST" in route.methods and normalized in READ_ONLY_POST_PATHS:
            out.append(("POST", route.path))
    return out


def _allowlisted(path: str) -> bool:
    concrete = _concrete(path).rstrip("/") or "/"
    return any(pattern.fullmatch(concrete) for pattern, _ in INTERVIEWER_PATHS)


CLOSED = [(method, path) for method, path in _reads() if not _allowlisted(path)]


def test_the_closed_list_covers_the_legacy_surface():
    paths = {path for _, path in CLOSED}
    assert len(CLOSED) > 20
    assert "/api/assistant/chat" in paths
    assert "/api/transparency/match-trace" in paths


@pytest.mark.parametrize(("method", "path"), CLOSED, ids=[f"{m} {p}" for m, p in CLOSED])
def test_interviewers_are_refused_everything_off_the_allowlist(interviewer_client, method, path):
    kwargs = {"json": {}} if method == "POST" else {}
    response = interviewer_client.request(method, _concrete(path), **kwargs)
    assert response.status_code == 403, f"{method} {path} answered {response.status_code}"


def test_skills_breakdown_is_closed_to_interviewers(interviewer_client):
    # Matches the candidate-id pattern, and "skills_breakdown" is nobody's id.
    assert interviewer_client.get("/api/candidates/skills_breakdown").status_code == 404


def test_candidate_list_shows_only_assigned(interviewer_client, assigned):
    body = interviewer_client.get("/api/candidates/", params={"page_size": 100}).json()
    assert [c["id"] for c in body["results"]] == [assigned["candidate_id"]]
    assert body["total"] == 1


def test_other_candidates_are_not_found(interviewer_client, assigned, seed):
    other = seed["candidate_ids"][0]
    assert interviewer_client.get(f"/api/candidates/{other}").status_code == 404
    assert interviewer_client.get(f"/api/candidates/{other}/resumes").status_code == 404
    assert interviewer_client.get(f"/api/jobs/applications/{other}").status_code == 404
    assert interviewer_client.get(f"/api/applications/{seed['application_id']}").status_code == 404
    assert interviewer_client.get(f"/api/resume/{seed['resume_id']}").status_code == 404
    assert interviewer_client.get(f"/api/candidates/{assigned['candidate_id']}").status_code == 200
    assert interviewer_client.get(f"/api/applications/{assigned['application_id']}").status_code == 200


def test_board_shows_only_assigned(interviewer_client, assigned, seed):
    def candidates_on(job_id):
        body = interviewer_client.get(f"/api/jobs/{job_id}/pipeline").json()
        return {card["candidate_id"] for col in body["columns"] for card in col["applications"]}

    assert candidates_on(seed["job_id"]) <= {assigned["candidate_id"]}
    assert candidates_on(assigned["job_id"]) == {assigned["candidate_id"]}


def test_other_roles_still_see_everyone(hiring_team_client, demo_client, seed, assigned):
    for client in (hiring_team_client, demo_client):
        body = client.get("/api/candidates/", params={"page_size": 100}).json()
        assert set(seed["candidate_ids"]) <= {c["id"] for c in body["results"]}


def test_score_is_hidden_until_feedback(interviewer_client, hiring_team_client, assigned):
    body = {"candidate_id": assigned["candidate_id"], "min_score": 0}
    before = interviewer_client.post("/api/enhanced-matching/match-jobs", json=body)
    assert before.status_code == 403
    assert before.json()["detail"] == SCORE_HIDDEN_DETAIL
    assert hiring_team_client.post("/api/enhanced-matching/match-jobs", json=body).status_code != 403

    given = interviewer_client.post(
        f"/api/interviews/{assigned['interview_id']}/feedback",
        json={"rating": 4, "recommendation": "hire", "notes": "Clear thinker."},
    )
    assert given.status_code == 200, given.text
    # Matching itself may still fail without embeddings in CI; the point is
    # that the score gate no longer refuses.
    after = interviewer_client.post("/api/enhanced-matching/match-jobs", json=body)
    assert after.status_code != 403


def test_interviewers_can_reach_their_own_screens(interviewer_client, assigned):
    for path in ("/auth/me", "/api/interviews", "/api/jobs/", "/api/transparency/policy"):
        assert interviewer_client.get(path).status_code == 200, path
```

(Settings, `/api/team/me`, arrives in Task 7, which adds its own check for interviewers.)

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_team_access.py -q`
Expected: FAIL with `ImportError: cannot import name 'INTERVIEWER_PATHS'`

- [ ] **Step 3: Add the gate**

In `backend/services/access_service.py`, extend the imports:

```python
import re

from fastapi import Depends, HTTPException, Request, status

from backend.models.models import ApplicationStage, Feedback, Interview, JobApplication, Resume, User
from backend.utils.auth import ROLE_INTERVIEWER, request_identity
from backend.utils.database import get_db
```

(replacing the earlier `from fastapi import Request` and the models import), then append:

```python
INTERVIEWER_SCOPE_DETAIL = (
    "Interviewers can open their own interviews and the candidates they interview."
)

# For the interviewer role, the only reachable paths. `kind` says what the
# `id` group names, so the gate can check it against visible_candidate_ids;
# None means the path is safe as is (or its handler filters). Matched with
# `fullmatch` after the trailing slash is stripped. Writes are still gated by
# enforce_read_only, which runs first.
INTERVIEWER_PATHS: list[tuple[re.Pattern[str], Optional[str]]] = [
    (re.compile(pattern), kind)
    for pattern, kind in [
        (r"/", None),
        (r"/health", None),
        (r"/auth/(me|login|demo)", None),
        (r"/api/team/me(/password)?", None),
        (r"/api/interviews", None),  # the handler limits interviewers to scope=mine
        (r"/api/interviews/\d+/feedback", None),  # the handler checks the assignee
        (r"/api/jobs", None),
        (r"/api/jobs/\d+", None),
        (r"/api/jobs/\d+/pipeline", None),  # the handler filters the cards
        (r"/api/candidates", None),  # the handler filters the list
        (r"/api/candidates/(?P<id>[^/]+)(/resumes)?", "candidate"),
        (r"/api/jobs/(applications|saved)/(?P<id>[^/]+)", "candidate"),
        (r"/api/applications/(?P<id>\d+)(/interviews)?", "application"),
        (r"/api/resume/(?P<id>\d+)(/preview|/view)?", "resume"),
        (r"/api/enhanced-matching/match-jobs", None),  # the handler checks can_see_score
        (r"/api/transparency/(policy|upload-policy)", None),
    ]
]


def _candidate_for(db: Session, kind: str, raw_id: str) -> Optional[str]:
    if kind == "candidate":
        return raw_id
    if not raw_id.isdigit():
        return None
    if kind == "application":
        application = db.get(JobApplication, int(raw_id))
        return application.candidate_id if application else None
    if kind == "resume":
        resume = db.get(Resume, int(raw_id))
        return resume.candidate_id if resume else None
    return None


def enforce_interviewer_scope(request: Request, db: Session = Depends(get_db)) -> None:
    """Installed app-wide after enforce_read_only. A no-op for every role but
    interviewer; for interviewers, default-deny outside INTERVIEWER_PATHS.

    A path naming someone the interviewer does not interview answers 404,
    not 403, so the response does not confirm the id exists.
    """
    role, user = request_identity(request, db)
    if role != ROLE_INTERVIEWER:
        return
    path = request.url.path.rstrip("/") or "/"
    for pattern, kind in INTERVIEWER_PATHS:
        match = pattern.fullmatch(path)
        if match is None:
            continue
        if kind is None:
            return
        candidate_id = _candidate_for(db, kind, match.group("id"))
        if candidate_id is not None and candidate_id in (visible_candidate_ids(db, user) or set()):
            return
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=INTERVIEWER_SCOPE_DETAIL)
```

- [ ] **Step 4: Install it**

In `backend/main.py`, replace

```python
from backend.utils.auth import enforce_read_only
```

with

```python
from backend.services.access_service import enforce_interviewer_scope
from backend.utils.auth import enforce_read_only
```

and

```python
app = FastAPI(dependencies=[Depends(enforce_read_only)])
```

with

```python
# Order matters: the write gate first (401/403 for writes), then the
# interviewer scope (default-deny reads for that role). Both share one
# identity lookup through request.state.
app = FastAPI(dependencies=[Depends(enforce_read_only), Depends(enforce_interviewer_scope)])
```

- [ ] **Step 5: Filter the candidate list**

In `backend/routers/candidates.py`, add `Request` to the fastapi import:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
```

add below `from ..utils.performance import async_timed`:

```python
from ..services.access_service import request_user, visible_candidate_ids
```

In `search_candidates`, add `http_request: Request,` as the **first** parameter (before `keyword`; FastAPI injects it by its annotation, and a parameter without a default must come first):

```python
def search_candidates(
    http_request: Request,
    keyword: Optional[str] = None,
```

Then directly after `query = db.query(Candidate)` add:

```python
        # ATS Phase B: an interviewer sees only the candidates they interview.
        visible = visible_candidate_ids(db, request_user(http_request))
        if visible is not None:
            query = query.filter(Candidate.id.in_(sorted(visible)))
```

`total_count = query.count()` (further down) runs after this filter, so the total is scoped too.

- [ ] **Step 6: Filter the board**

In `backend/routers/pipeline.py`, change `from fastapi import APIRouter, Depends, HTTPException` to

```python
from fastapi import APIRouter, Depends, HTTPException, Request
```

add `from ..services.access_service import request_user, visible_candidate_ids` below the `pipeline_service` import, change `_board`'s signature and its application query to

```python
def _board(db: Session, job: Job, visible: Optional[set[str]] = None) -> JobPipelineResponse:
    stages = ps.ensure_job_stages(db, job.id)
    applications = (
        db.query(JobApplication)
        .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
        .filter(JobApplication.job_id == job.id)
        .all()
    )
    if visible is not None:
        applications = [a for a in applications if a.candidate_id in visible]
```

(the rest of `_board` is unchanged), and replace `get_job_pipeline` with

```python
@router.get("/jobs/{job_id}/pipeline", response_model=JobPipelineResponse)
def get_job_pipeline(job_id: int, request: Request, db: Session = Depends(get_db)) -> JobPipelineResponse:
    """The job's stages and who is at each one (an interviewer sees only their candidates)."""
    visible = visible_candidate_ids(db, request_user(request))
    return _board(db, _job_or_404(db, job_id), visible)
```

- [ ] **Step 7: Hide the score until feedback**

In `backend/routers/enhanced_matching.py`, change the fastapi import to

```python
from fastapi import APIRouter, Depends, HTTPException, Request
```

add

```python
from backend.services.access_service import SCORE_HIDDEN_DETAIL, can_see_score, request_user
```

and change `match_jobs_for_candidate` to

```python
@router.post("/match-jobs", response_model=MatchJobsResponse)
def match_jobs_for_candidate(
    request: JobMatchRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Find jobs that match the given candidate using enhanced matching."""
    # ATS Phase B: interviewers see scores only after giving feedback.
    if not can_see_score(db, request_user(http_request), request.candidate_id):
        raise HTTPException(status_code=403, detail=SCORE_HIDDEN_DETAIL)
    try:
```

(the body from `try:` onward is unchanged).

- [ ] **Step 8: Run the tests**

Run: `poetry run pytest backend/tests/test_team_access.py backend/tests/test_auth.py backend/tests/test_pipeline.py backend/tests/test_candidate_search.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

Write `$S\commit-b6.txt`:

```
feat: interviewers see only their candidates, scores after feedback

A second app-wide gate makes the interviewer role default-deny: only an
allowlist of paths is reachable, and paths naming a candidate, resume,
or application are checked against the candidates they interview (404
otherwise, so ids are not confirmed). The candidate list and job board
filter for them, and match-jobs refuses a score until they have given
feedback. A route walk proves every other read route, the assistant
included, answers 403 for the role.
```

```powershell
git add backend/services/access_service.py backend/main.py backend/routers/candidates.py backend/routers/pipeline.py backend/routers/enhanced_matching.py backend/tests/test_team_access.py
git commit -F "$S\commit-b6.txt"
```

---

### Task 7: Team and Settings endpoints; resume save follows the matrix

**Files:**
- Modify: `backend/models/team.py` (already holds the shapes from Task 5)
- Create: `backend/routers/team.py`
- Modify: `backend/models/user.py`, `backend/routers/resume.py`, `backend/main.py`
- Test: `backend/tests/test_team.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_team.py`:

```python
"""Team management and personal settings (ATS Phase B)."""
from __future__ import annotations

import pytest

from backend.models.models import User
from backend.tests.conftest import SEED_EMAIL_DOMAIN, STAFF_PASSWORD


def _invite(client, email, role="hiring_team", name="New Person"):
    return client.post("/api/team/users", json={"email": email, "name": name, "role": role})


def test_list_excludes_the_demo_account_and_hides_emails_from_the_demo(admin_client, demo_client, staff_users):
    admin_view = admin_client.get("/api/team/users").json()["members"]
    assert all(m["role"] != "demo" for m in admin_view)
    assert all(m["email"] for m in admin_view)
    demo_view = demo_client.get("/api/team/users").json()["members"]
    assert demo_view and all(m["email"] is None for m in demo_view)


def test_a_hiring_manager_invites_and_the_temporary_password_works(hiring_manager_client, client, unique_email):
    response = _invite(hiring_manager_client, unique_email)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["member"]["role"] == "hiring_team"
    assert len(body["temporary_password"]) >= 12
    login = client.post("/auth/login", json={"email": unique_email, "password": body["temporary_password"]})
    assert login.status_code == 200
    assert login.json()["user"]["name"] == "New Person"


def test_only_an_admin_creates_an_admin(hiring_manager_client, admin_client, unique_email):
    assert _invite(hiring_manager_client, unique_email, role="admin").status_code == 403
    assert _invite(admin_client, unique_email, role="admin").status_code == 201


def test_hiring_team_cannot_invite_and_duplicates_are_409(hiring_team_client, admin_client, unique_email):
    assert _invite(hiring_team_client, unique_email).status_code == 403
    assert _invite(admin_client, unique_email).status_code == 201
    assert _invite(admin_client, unique_email.upper()).status_code == 409


def test_role_changes_are_admin_only_and_never_your_own(admin_client, hiring_manager_client, admin_user, unique_email):
    member = _invite(admin_client, unique_email).json()["member"]
    path = f"/api/team/users/{member['id']}/role"
    assert hiring_manager_client.put(path, json={"role": "interviewer"}).status_code == 403
    changed = admin_client.put(path, json={"role": "interviewer"})
    assert changed.status_code == 200 and changed.json()["role"] == "interviewer"
    assert admin_client.put(f"/api/team/users/{admin_user.id}/role", json={"role": "hiring_team"}).status_code == 409


def test_remove_refuses_people_with_feedback(admin_client, db_session, scoped_application, staff_users, unique_email):
    from backend.models.models import JobApplication
    from backend.services import feedback_service as fs
    from backend.services import pipeline_service as ps

    member = _invite(admin_client, unique_email, role="interviewer").json()["member"]
    person = db_session.get(User, member["id"])
    application = db_session.get(JobApplication, scoped_application["application_id"])
    interview = fs.assign(db_session, ps.current_stage(application), person)
    fs.submit_feedback(db_session, interview, person, 3, "hire", "")
    db_session.commit()

    refused = admin_client.delete(f"/api/team/users/{member['id']}")
    assert refused.status_code == 409
    assert "Change their role instead" in refused.json()["detail"]

    plain = _invite(admin_client, f"plain-{unique_email}").json()["member"]
    assert admin_client.delete(f"/api/team/users/{plain['id']}").status_code == 200
    assert db_session.get(User, plain["id"]) is None


def test_settings_name_timezone_and_password(staff_users, client):
    from backend.tests.conftest import _client_for

    person = staff_users["hiring_team"]
    me = _client_for(person)
    updated = me.put("/api/team/me", json={"name": "Renamed Person", "timezone": "America/Chicago"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["timezone"] == "America/Chicago"
    assert me.put("/api/team/me", json={"name": "X", "timezone": "Not a zone!"}).status_code == 422

    wrong = me.put("/api/team/me/password", json={"current_password": "nope", "new_password": "a-brand-new-password"})
    assert wrong.status_code == 400
    ok = me.put(
        "/api/team/me/password",
        json={"current_password": STAFF_PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert ok.status_code == 200
    assert client.post("/auth/login", json={"email": person.email, "password": "a-brand-new-password"}).status_code == 200
    # Put it back for the rest of the session.
    me.put("/api/team/me/password", json={"current_password": "a-brand-new-password", "new_password": STAFF_PASSWORD})
    me.put("/api/team/me", json={"name": "Test Hiring Team"})


def test_demo_cannot_change_settings(demo_client):
    assert demo_client.put("/api/team/me", json={"name": "Hacker"}).status_code == 403


def test_auth_me_returns_the_name(hiring_manager_client):
    assert hiring_manager_client.get("/auth/me").json()["name"] == "Test Hiring Manager"


def test_interviewers_reach_their_settings(interviewer_client):
    assert interviewer_client.get("/api/team/me").status_code == 200
    # ...but not the team list, which their sidebar does not offer.
    assert interviewer_client.get("/api/team/users").status_code == 403
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_team.py -q`
Expected: FAIL (every `/api/team/...` call is 404 or 403; `_client_for` exists from Task 3).

- [ ] **Step 3: Write the router**

Create `backend/routers/team.py`:

```python
"""The team, invitations, and each person's own settings (ATS Phase B).

No email is sent in Phase B: an invite creates the account with a temporary
password that is returned once and shown once, and the inviter passes it on.
Plain `def` handlers (sync ORM).
"""
from __future__ import annotations

import re
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..models.models import ApplicationStage, Feedback, Interview, User
from ..models.team import (
    InviteRequest,
    InviteResponse,
    MessageOut,
    PasswordChange,
    ProfileResponse,
    ProfileUpdate,
    RoleChangeRequest,
    TeamListResponse,
    TeamMember,
)
from ..services.feedback_service import display_name
from ..utils.auth import (
    ROLE_ADMIN,
    ROLE_DEMO,
    STAFF_ROLES,
    get_current_user,
    hash_password,
    request_identity,
    verify_password,
)
from ..utils.database import get_db
from ..utils.permissions import DELETE_RECORDS, USERS_CHANGE_ROLE, USERS_INVITE, can, require

router = APIRouter(prefix="/team")

# IANA-style names such as America/Chicago or UTC. The web offers a fixed list.
TIMEZONE_RE = re.compile(r"^[A-Za-z_]+(/[A-Za-z0-9_+\-]+)*$")


def _member(user: User, show_email: bool) -> TeamMember:
    member = TeamMember.model_validate(user)
    if not show_email:
        member.email = None
    return member


def _staff_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None or user.role == ROLE_DEMO:
        raise HTTPException(status_code=404, detail="No one on the team has that id.")
    return user


@router.get("/users", response_model=TeamListResponse)
def list_team(request: Request, db: Session = Depends(get_db)) -> TeamListResponse:
    role, _ = request_identity(request, db)
    show_email = can(role, USERS_INVITE)
    people = db.query(User).filter(User.role.in_(STAFF_ROLES)).all()
    order = {r: i for i, r in enumerate(STAFF_ROLES)}
    people.sort(key=lambda u: (order.get(u.role, 9), (u.name or u.email).lower()))
    return TeamListResponse(members=[_member(u, show_email) for u in people])


@router.post("/users", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require(USERS_INVITE)),
) -> InviteResponse:
    if payload.role == ROLE_ADMIN and actor.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Only an administrator can add another administrator.")
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="Someone with that email is already on the team.")
    temporary = secrets.token_urlsafe(12)  # 16 characters
    user = User(email=email, name=payload.name.strip(), role=payload.role, hashed_password=hash_password(temporary))
    db.add(user)
    db.commit()
    db.refresh(user)
    return InviteResponse(member=_member(user, True), temporary_password=temporary)


@router.put("/users/{user_id}/role", response_model=TeamMember)
def change_role(
    user_id: str,
    payload: RoleChangeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require(USERS_CHANGE_ROLE)),
) -> TeamMember:
    user = _staff_or_404(db, user_id)
    if user.id == actor.id:
        # Also what keeps the last administrator from demoting themselves.
        raise HTTPException(status_code=409, detail="You cannot change your own role.")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return _member(user, True)


@router.delete("/users/{user_id}", response_model=MessageOut)
def remove(
    user_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(DELETE_RECORDS)),
) -> MessageOut:
    user = _staff_or_404(db, user_id)
    if user.id == actor.id:
        raise HTTPException(status_code=409, detail="You cannot remove yourself.")
    has_feedback = (
        db.query(Feedback.id)
        .join(Interview, Feedback.interview_id == Interview.id)
        .filter(Interview.interviewer_id == user.id)
        .first()
    )
    if has_feedback is not None:
        raise HTTPException(
            status_code=409,
            detail=f"{display_name(user)} has submitted feedback, which stays on the record. Change their role instead.",
        )
    name = display_name(user)
    db.query(Interview).filter(Interview.interviewer_id == user.id).delete(synchronize_session=False)
    db.query(ApplicationStage).filter(ApplicationStage.changed_by == user.id).update(
        {ApplicationStage.changed_by: None}, synchronize_session=False
    )
    # stage_default_interviewers rows go by ON DELETE CASCADE; jobs'
    # hiring_manager_id and recruiter_id become NULL by ON DELETE SET NULL.
    db.delete(user)
    db.commit()
    return MessageOut(message=f"Removed {name} from the team.")


@router.get("/me", response_model=ProfileResponse)
def my_profile(user: User = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse.model_validate(user)


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileResponse:
    timezone: Optional[str] = (payload.timezone or "").strip() or None
    if timezone is not None and not TIMEZONE_RE.fullmatch(timezone):
        raise HTTPException(status_code=422, detail="Choose a time zone from the list.")
    user.name = payload.name.strip()
    user.timezone = timezone
    db.commit()
    db.refresh(user)
    return ProfileResponse.model_validate(user)


@router.put("/me/password", response_model=MessageOut)
def change_my_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageOut:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Your current password is not correct.")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return MessageOut(message="Password changed.")
```

Note: `update_my_profile` sets `timezone` to None when it is omitted. That matches the form, which always sends both fields.

- [ ] **Step 4: Extend the user schema and mount**

In `backend/models/user.py`, replace

```python
from typing import Literal
```

with

```python
from typing import Literal, Optional
```

replace `Role = Literal["admin", "demo"]` with

```python
Role = Literal["admin", "hiring_manager", "hiring_team", "interviewer", "demo"]
```

and add `name: Optional[str] = None` to `UserResponse` directly after `email: str`.

In `backend/main.py`, add `team` to the router import line (after `feedback`) and add, after the feedback `include_router` line:

```python
app.include_router(team.router, prefix="/api", tags=["team"])  # ATS Phase B
```

- [ ] **Step 5: Resume save follows the matrix**

In `backend/routers/resume.py`, change `from backend.utils.auth import ROLE_ADMIN, get_optional_user` to

```python
from backend.utils.auth import get_optional_user
from backend.utils.permissions import CANDIDATES_ADD, can
```

and in `require_write_access_for_save` replace

```python
    if current_user is not None and current_user.role == ROLE_ADMIN:
        return
    raise HTTPException(
        status_code=403 if current_user is not None else 401,
        detail="Saving a parsed resume requires an administrator account.",
    )
```

with

```python
    if current_user is not None and can(current_user.role, CANDIDATES_ADD):
        return
    raise HTTPException(
        status_code=403 if current_user is not None else 401,
        detail="Saving a parsed resume needs a role that can add candidates.",
    )
```

Then search for tests that pinned the old sentence:

Run: `rg -n "requires an administrator account" backend`
Expected: no matches (if any test asserts the old text, update it to the new sentence).

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_team.py backend/tests/test_team_access.py backend/tests/test_auth.py backend/tests/test_resume_save.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

Write `$S\commit-b7.txt`:

```
feat: team management and personal settings endpoints

Admins and hiring managers invite people with a temporary password shown
once (no email until Phase E); only an admin creates an admin or changes
roles, and nobody changes their own. Removing someone who has given
feedback is refused because feedback is history. Everyone can set their
name, time zone, and password. The demo can read the team list but gets
no email addresses. Saving a parsed resume now follows the matrix
(admin, hiring manager, hiring team) instead of admin only.
```

```powershell
git add backend/routers/team.py backend/models/team.py backend/models/user.py backend/routers/resume.py backend/main.py backend/tests/test_team.py
git commit -F "$S\commit-b7.txt"
```

---
### Task 8: Job links to team members; transparency says what feedback is for

**Files:**
- Modify: `backend/models/job.py`, `backend/routers/jobs.py`
- Modify: `backend/routers/transparency.py`
- Test: `backend/tests/test_team.py`, `backend/tests/test_feedback.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_team.py`:

```python
def test_jobs_link_to_team_members(admin_client, staff_users):
    payload = {
        "title": "Linked Job",
        "department": "Engineering",
        "job_overview": "Exists to test team links.",
        "required_qualifications": "Python",
        "hiring_manager_id": staff_users["hiring_manager"].id,
    }
    created = admin_client.post("/api/jobs/", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["hiring_manager_id"] == staff_users["hiring_manager"].id
    assert created.json()["recruiter_id"] is None

    ghost = "00000000-0000-4000-8000-00000000dead"
    bad = admin_client.post("/api/jobs/", json={**payload, "recruiter_id": ghost})
    assert bad.status_code == 422
    assert "someone on the team" in bad.json()["detail"]

    # An update that does not mention the links leaves them alone.
    job_id = created.json()["id"]
    without_links = {k: v for k, v in payload.items() if k != "hiring_manager_id"}
    kept = admin_client.put(f"/api/jobs/{job_id}", json={**without_links, "title": "Linked Job Renamed"})
    assert kept.status_code == 200, kept.text
    assert kept.json()["hiring_manager_id"] == staff_users["hiring_manager"].id
    admin_client.delete(f"/api/jobs/{job_id}")
```

Append to `backend/tests/test_feedback.py`:

```python
import importlib
import inspect

# Every module on the path from a candidate to a match score or a search
# ranking. If one of them ever mentions feedback, the transparency page's
# promise needs re-reading.
SCORING_MODULES = (
    "backend.services.matching_integrator",
    "backend.services.matching_enhancer",
    "backend.services.enhanced_matching_integrator",
    "backend.services.vector_search_service",
    "backend.services.search_relevance",
    "backend.services.agent_framework.agents.candidate_matching_agent",
)


@pytest.mark.parametrize("module_name", SCORING_MODULES)
def test_scoring_code_never_reads_feedback(module_name):
    source = inspect.getsource(importlib.import_module(module_name)).lower()
    assert "feedback" not in source, f"{module_name} mentions feedback"


def test_transparency_publishes_what_feedback_is_for(demo_client):
    policy = demo_client.get("/api/transparency/policy").json()["feedback_policy"]
    assert policy["used_for"] == fs.FEEDBACK_USED_FOR
    assert any("match score" in line for line in policy["never_used_for"])
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_team.py backend/tests/test_feedback.py -q -k "link or scoring_code or transparency"`
Expected: the link test fails (`KeyError: 'hiring_manager_id'`), the transparency test fails (`KeyError: 'feedback_policy'`), and the six scoring-module checks already pass (they guard the future).

- [ ] **Step 3: Accept and return the links**

In `backend/models/job.py`, add to `JobCreateUpdate` directly after `recruiter: Optional[str] = None`:

```python
    # ATS Phase B: optional links to team members (user ids).
    hiring_manager_id: Optional[str] = None
    recruiter_id: Optional[str] = None
```

and the same two lines to `JobResponse` directly after its `recruiter: Optional[str] = None`.

In `backend/routers/jobs.py`, change `from ..models.models import Job, Candidate, Resume, JobApplication, SavedJob` to

```python
from ..models.models import Job, Candidate, Resume, JobApplication, SavedJob, User
from ..utils.auth import STAFF_ROLES
```

and add after `logger = logging.getLogger("backend.routers.jobs")` (the module-level one, below `router = APIRouter(prefix="/jobs")`):

```python
def _team_link(db: Session, user_id: Optional[str], label: str) -> None:
    """ATS Phase B: a job's manager or recruiter link must name someone on the team."""
    if not user_id:
        return
    user = db.get(User, user_id)
    if user is None or user.role not in STAFF_ROLES:
        raise HTTPException(status_code=422, detail=f"The {label} must be someone on the team.")
```

In `create_job`, insert directly before the line `    try:` that opens the body (the `try` turns every exception into a 400, so the check must sit outside it):

```python
    _team_link(db, job.hiring_manager_id, "hiring manager")
    _team_link(db, job.recruiter_id, "recruiter")
```

In `update_job`, insert directly after the `if not db_job: raise HTTPException(...)` block:

```python
    _team_link(db, job_update.hiring_manager_id, "hiring manager")
    _team_link(db, job_update.recruiter_id, "recruiter")
```

`update_job` already applies `exclude_unset`, so a form that never sends the links leaves them as they were.

- [ ] **Step 4: Publish the feedback policy**

In `backend/routers/transparency.py`, add below the `vector_search_service` import block:

```python
from backend.services.feedback_service import FEEDBACK_NEVER_USED_FOR, FEEDBACK_USED_FOR
```

add above `class ScoringPolicy`:

```python
class FeedbackPolicy(BaseModel):
    used_for: List[str]
    never_used_for: List[str]
```

add the last field of `ScoringPolicy`:

```python
    feedback_policy: FeedbackPolicy
```

and in `scoring_policy()`, add as the last keyword argument:

```python
        # ATS Phase B. test_feedback pins that no scoring module mentions feedback.
        feedback_policy=FeedbackPolicy(
            used_for=list(FEEDBACK_USED_FOR),
            never_used_for=list(FEEDBACK_NEVER_USED_FOR),
        ),
```

- [ ] **Step 5: Run the tests**

Run: `poetry run pytest backend/tests/test_team.py backend/tests/test_feedback.py backend/tests/test_transparency.py backend/tests/test_jobs_admin.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

Write `$S\commit-b8.txt`:

```
feat: jobs link to team members; transparency covers feedback

Jobs accept an optional hiring manager and recruiter by user id,
validated against the team; the free-text fields stay for display. The
transparency policy gains what feedback is and is not used for, and a
test reads every scoring module's source to pin that none of them
mentions feedback.
```

```powershell
git add backend/models/job.py backend/routers/jobs.py backend/routers/transparency.py backend/tests/test_team.py backend/tests/test_feedback.py
git commit -F "$S\commit-b8.txt"
```

---

### Task 9: Assistant tool for pending feedback

**Files:**
- Modify: `backend/services/assistant_tools.py`
- Modify: `evals/assistant_golden.json`
- Test: `backend/tests/test_feedback.py`, the existing golden replay (`backend/tests/test_assistant_golden.py`)

Interviewers cannot reach the assistant at all (Task 6 route walk), so the score rule holds for it without per-tool changes.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_feedback.py`:

```python
import asyncio


def test_assistant_lists_pending_feedback(db_session, application, staff_users):
    from backend.services.assistant_tools import build_assistant_tools

    fs.assign(db_session, _row(application, "resume_submitted"), staff_users["interviewer"])
    db_session.flush()
    tools = {t.name: t for t in build_assistant_tools(db_session)}
    result = asyncio.run(tools["list_pending_feedback"].run())
    assert result["pending_count"] >= 1
    mine = [p for p in result["pending"] if p["candidate_id"] == application.candidate_id]
    assert mine and mine[0]["interviewer"] == "Test Interviewer"
    assert mine[0]["stage"] == "Resume submitted"
    assert "@" not in str(result)  # names only, never addresses
```

- [ ] **Step 2: Run it to verify it fails**

Run: `poetry run pytest backend/tests/test_feedback.py -q -k assistant`
Expected: FAIL with `KeyError: 'list_pending_feedback'`

- [ ] **Step 3: Add the tool**

In `backend/services/assistant_tools.py`, change the module docstring's tool sentence

```python
Spec §4.6: search_candidates, match_to_job, explain_match, get_market_data,
get_candidate, get_job, list_pipeline, get_candidate_resume.
```

to

```python
Spec §4.6: search_candidates, match_to_job, explain_match, get_market_data,
get_candidate, get_job, list_pipeline, get_candidate_resume. ATS Phase B adds
list_pending_feedback.
```

Insert the closure between the end of `get_candidate_resume` and the tool list, i.e. replace

```python
            "parsed_content": content,
        }

    return [
```

with

```python
            "parsed_content": content,
        }

    async def list_pending_feedback(limit: int = 10) -> dict:
        from backend.services import feedback_service

        limit = clamp_limit(limit, default=10)
        interviews = feedback_service.pending_feedback(db)
        pending = []
        for interview in interviews[:limit]:
            row = interview.application_stage
            application = row.application
            job = db.get(Job, application.job_id)
            pending.append(
                {
                    "interviewer": feedback_service.display_name(interview.interviewer),
                    "candidate_id": application.candidate_id,
                    "candidate": feedback_service.candidate_name(
                        db.get(Candidate, application.candidate_id)
                    ),
                    "job_id": application.job_id,
                    "job": job.title if job else None,
                    "stage": row.stage.name,
                    "waiting_since": row.started_at.date().isoformat() if row.started_at else None,
                }
            )
        return {"pending_count": len(interviews), "pending": pending}

    return [
```

and append a `Tool` to the list, i.e. replace

```python
            run=get_candidate_resume,
        ),
    ]
```

with

```python
            run=get_candidate_resume,
        ),
        Tool(
            name="list_pending_feedback",
            description=(
                "List interviews that have happened but have no feedback yet: who owes it, for "
                "which candidate, job, and stage, and since when. Call this for questions like "
                "'who still owes feedback' or 'what feedback is outstanding'. pending_count is the "
                "total; pending holds the oldest first."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many to list (default 10)"},
                },
            },
            run=list_pending_feedback,
        ),
    ]
```

- [ ] **Step 4: Add the golden question**

`test_golden_set_covers_every_tool` fails until the new tool has a golden question. In `evals/assistant_golden.json`, the file ends with the last case's closing brace followed by `  ]` and `}`. Insert this case as the new last element of `cases` (add a comma after the previous last case's closing `}`):

```json
    {
      "id": "pending-feedback",
      "question": "Who still owes interview feedback?",
      "expected_tools": ["list_pending_feedback"],
      "checks": {"numbers_from_results": true},
      "replay": {
        "calls": [{"tool": "list_pending_feedback", "arguments": {}}],
        "reply": "{{value:pending_count}} interviews are waiting for feedback."
      }
    }
```

- [ ] **Step 5: Run the tests**

Run: `poetry run pytest backend/tests/test_feedback.py backend/tests/test_assistant_golden.py backend/tests/test_assistant_robustness.py -q`
Expected: all pass, including `test_golden_set_covers_every_tool`, the dash checks on the new description, and the replayed `pending-feedback` case (pending_count is 0 or more on the CI seed; the reply quotes it).

- [ ] **Step 6: Commit**

Write `$S\commit-b9.txt`:

```
feat: assistant tool for outstanding interview feedback

list_pending_feedback reports who owes feedback, for whom, and since
when, with names only. Interviewers cannot reach the assistant, so the
score rule needs no per-tool change. Golden question added so the
replay covers the tool.
```

```powershell
git add backend/services/assistant_tools.py evals/assistant_golden.json backend/tests/test_feedback.py
git commit -F "$S\commit-b9.txt"
```

---

### Task 10: Generated web copy of the permission table; contract regeneration

**Files:**
- Create: `scripts/export_permissions.py`, `web/src/lib/role-permissions.json` (generated)
- Test: `backend/tests/test_permissions.py`
- Regenerate: `openapi.json`, `web/src/lib/schema.d.ts`, `backend/tests/golden/api_response_shapes.json`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_permissions.py`:

```python
def test_permissions_json_is_current():
    from scripts.export_permissions import TARGET, render

    assert TARGET.exists(), "run: poetry run python scripts/export_permissions.py"
    assert TARGET.read_text(encoding="utf-8") == render(), (
        "web/src/lib/role-permissions.json is stale; run: poetry run python scripts/export_permissions.py"
    )
```

- [ ] **Step 2: Run it to verify it fails**

Run: `poetry run pytest backend/tests/test_permissions.py -q -k json`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.export_permissions'`

- [ ] **Step 3: Write the exporter**

Create `scripts/export_permissions.py`:

```python
"""Write web/src/lib/role-permissions.json from backend/utils/permissions.py.

    poetry run python scripts/export_permissions.py          # write it
    poetry run python scripts/export_permissions.py --check  # exit 1 if stale

The backend enforces the table; the web app reads this copy to decide which
controls to draw. One source, a generated copy, and a test
(test_permissions_json_is_current) that fails when they drift, the same
pattern as openapi.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import backend.utils.win_compat  # noqa: F401  (must precede deps needing pwd)

from backend.utils.permissions import ALL_PERMISSIONS, ROLE_LABELS, ROLE_PERMISSIONS

TARGET = Path(__file__).resolve().parents[1] / "web" / "src" / "lib" / "role-permissions.json"


def render() -> str:
    data = {
        "permissions": list(ALL_PERMISSIONS),
        "roles": {role: sorted(perms) for role, perms in sorted(ROLE_PERMISSIONS.items())},
        "labels": dict(sorted(ROLE_LABELS.items())),
    }
    return json.dumps(data, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the file is stale")
    args = parser.parse_args()
    expected = render()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != expected:
            print(f"{TARGET} is stale. Run: poetry run python scripts/export_permissions.py", file=sys.stderr)
            return 1
        print(f"{TARGET.name} is up to date")
        return 0
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate and check**

```powershell
poetry run python scripts/export_permissions.py
poetry run python scripts/export_permissions.py --check
poetry run pytest backend/tests/test_permissions.py -q
```

Expected: `Wrote ...role-permissions.json`, then `role-permissions.json is up to date`, then all pass.

- [ ] **Step 5: Regenerate the contract golden, OpenAPI, and web types**

```powershell
$env:UPDATE_API_GOLDEN = "1"
poetry run pytest backend/tests/test_api_contract.py -q
Remove-Item Env:UPDATE_API_GOLDEN
git diff backend/tests/golden/api_response_shapes.json
```

Expected diff: additions only. `hiring_manager_id` and `recruiter_id` under every job shape, `name` under the auth user shapes, `feedback_policy` under the transparency policy. Any removed key is a regression: stop and fix.

```powershell
poetry run python scripts/export_openapi.py
poetry run python scripts/export_openapi.py --check
cd web; npm run types:api; cd ..
poetry run pytest backend/tests/test_api_contract.py backend/tests/test_openapi_is_current.py -q
```

Expected: `--check` passes; `web/src/lib/schema.d.ts` gains `TeamMember`, `InviteResponse`, `ProfileResponse`, `InterviewOut`, `InterviewListItem`, `StageDefaults`, `DefaultInterviewersResponse`, `FeedbackPolicy`; the old `Interview`/`InterviewCreate` mock schemas are gone; both tests pass.

- [ ] **Step 6: Commit**

Write `$S\commit-b10.txt`:

```
chore: generated permission table for the web app, contract regenerated

scripts/export_permissions.py writes role-permissions.json from the
backend table, with a --check mode and a test, so the web can hide
controls without hand-copying the matrix. Golden contract regenerated
(additions only: job links, user name, feedback policy), openapi.json and
the web types updated; the mock interview schemas are gone.
```

```powershell
git add scripts/export_permissions.py web/src/lib/role-permissions.json backend/tests/test_permissions.py backend/tests/golden/api_response_shapes.json openapi.json web/src/lib/schema.d.ts
git commit -F "$S\commit-b10.txt"
```

---

### Task 11: Seed a synthetic team and interview history; create_admin takes a role

**Files:**
- Modify: `scripts/seed_demo.py`, `scripts/create_admin.py`

- [ ] **Step 1: Let create_admin.py create any staff role**

In `scripts/create_admin.py`, update the docstring's usage block to

```python
"""Create or update a staff account (admin by default).

There is no registration endpoint by design (Phase 3 spec §2), so this is how
an admin comes into existence, locally and on the droplet. ATS Phase B: it
also sets a password for anyone else, including the synthetic team the seed
creates without passwords.

    poetry run python scripts/create_admin.py --email you@example.com
    poetry run python scripts/create_admin.py --email marcus.webb@team.recruitiq.dev --role interviewer

The password is read from the ADMIN_PASSWORD environment variable, or prompted
for without echo. Passing it on the command line is not supported: it would land
in shell history and in the process list.
"""
```

change `from backend.utils.auth import ROLE_ADMIN, hash_password` to

```python
from backend.utils.auth import ROLE_ADMIN, STAFF_ROLES, hash_password
```

add after `parser.add_argument("--email", required=True)`:

```python
    parser.add_argument("--role", default=ROLE_ADMIN, choices=STAFF_ROLES)
    parser.add_argument("--name", default=None, help="display name (optional)")
```

and replace the update/create block

```python
        if user:
            user.hashed_password = hash_password(password)
            user.role = ROLE_ADMIN
            action = "Updated"
        else:
            user = User(
                email=args.email, hashed_password=hash_password(password), role=ROLE_ADMIN
            )
            db.add(user)
            action = "Created"
        db.commit()
        print(f"{action} admin {args.email}")
```

with

```python
        if user:
            user.hashed_password = hash_password(password)
            user.role = args.role
            action = "Updated"
        else:
            user = User(email=args.email, hashed_password=hash_password(password), role=args.role)
            db.add(user)
            action = "Created"
        if args.name:
            user.name = args.name
        db.commit()
        print(f"{action} {args.role} {args.email}")
```

- [ ] **Step 2: Add the team and interview seed**

In `scripts/seed_demo.py`, add `from datetime import datetime` below `import zlib`, and replace the models import with

```python
from backend.models.models import (
    ApplicationStage,
    Candidate,
    CandidateSkill,
    Feedback,
    Interview,
    Job,
    JobApplication,
    PipelineStage,
    SavedJob,
    StageDefaultInterviewer,
    User,
)
```

Add after `STATUS_TO_STAGE_INDEX = {...}`:

```python
# ATS Phase B. Synthetic people, no passwords: nobody can sign in as them until
# someone runs scripts/create_admin.py --email ... --role ... with a password
# from the environment.
TEAM = [
    ("Priya Raman", "priya.raman@team.recruitiq.dev", "hiring_manager"),
    ("Daniel Okafor", "daniel.okafor@team.recruitiq.dev", "hiring_manager"),
    ("Lena Fischer", "lena.fischer@team.recruitiq.dev", "hiring_team"),
    ("Marcus Webb", "marcus.webb@team.recruitiq.dev", "interviewer"),
    ("Sofia Alvarez", "sofia.alvarez@team.recruitiq.dev", "interviewer"),
    ("Kenji Watanabe", "kenji.watanabe@team.recruitiq.dev", "interviewer"),
]

# Rounds the seed staffs: the job's hiring manager runs the review, the
# interviewers run the conversations.
INTERVIEW_ROUNDS = ("hm_review", "technical_interview", "problem_solving", "case_study")

FEEDBACK_NOTES = {
    "passed": [
        "Strong fundamentals and clear communication.",
        "Worked through the problem methodically and asked good questions.",
        "Good depth in their primary area. Would be glad to work with them.",
    ],
    "failed": [
        "Struggled to explain the reasoning behind past design decisions.",
        "Not enough depth in the core skills for this level.",
    ],
}
```

Add these functions directly above `def embed(`:

```python
def seed_team(db) -> dict[str, list[User]]:
    """The synthetic team, keyed by role. Additive: an existing person keeps
    whatever role someone gave them on the Team page."""
    by_role: dict[str, list[User]] = {}
    for name, email, role in TEAM:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, name=name, role=role, hashed_password=None)
            db.add(user)
        elif not user.name:
            user.name = name
        by_role.setdefault(user.role, []).append(user)
    db.commit()
    return by_role


def _pick(people: list[User], key: str) -> User:
    return people[stable_index(key, len(people))]


def seed_interviews(db, team: dict[str, list[User]], jobs: list[Job]) -> None:
    """Hiring managers on jobs, a default interviewer per job, and interview
    history matching each application's stage rows.

    Deterministic and additive: a stage row that already has an interview is
    left alone, so a re-run never duplicates or rewrites anyone's feedback.
    Rounds that are done get feedback; the round in progress is left waiting,
    so the Interviews page has something outstanding to show.
    """
    from backend.services import pipeline_service as ps

    managers = team.get("hiring_manager", [])
    interviewers = team.get("interviewer", [])
    if not managers or not interviewers:
        return

    for job in jobs:
        if job.hiring_manager_id is None:
            job.hiring_manager_id = _pick(managers, f"manager-{job.title}").id
        stages = {s.key: s for s in ps.ensure_job_stages(db, job.id)}
        technical = stages.get("technical_interview")
        if technical is not None and not technical.default_interviewers:
            technical.default_interviewers.append(
                StageDefaultInterviewer(user_id=_pick(interviewers, f"default-{job.title}").id)
            )
    db.flush()

    rows = (
        db.query(ApplicationStage)
        .join(PipelineStage, ApplicationStage.stage_id == PipelineStage.id)
        .filter(
            PipelineStage.key.in_(INTERVIEW_ROUNDS),
            ApplicationStage.status.in_(("in_progress", "passed", "failed")),
        )
        .order_by(ApplicationStage.id)
        .all()
    )
    for row in rows:
        if row.interviews:
            continue
        job = row.application.job
        if row.stage.key == "hm_review" and job.hiring_manager_id:
            person = db.get(User, job.hiring_manager_id)
        else:
            person = _pick(interviewers, f"{row.application_id}-{row.stage.key}")
        interview = Interview(
            interviewer_id=person.id,
            assignment_source="manual",
            created_at=row.started_at or datetime.utcnow(),
        )
        row.interviews.append(interview)
        if row.status in ("passed", "failed"):
            passed = row.status == "passed"
            notes = FEEDBACK_NOTES[row.status]
            interview.feedback = Feedback(
                rating=(4 + stable_index(f"rating-{row.id}", 2)) if passed else 2,
                recommendation=(
                    ("strong_hire" if stable_index(f"rec-{row.id}", 3) == 0 else "hire")
                    if passed
                    else "no_hire"
                ),
                notes=notes[stable_index(f"note-{row.id}", len(notes))],
                submitted_at=row.completed_at or row.started_at or datetime.utcnow(),
            )
    db.commit()
```

In `main()`, add after the `--re-embed` argument:

```python
    parser.add_argument(
        "--team-only",
        action="store_true",
        help=(
            "only add the synthetic team and interview history (ATS Phase B). Never "
            "changes a candidate, a candidate's status, or an application"
        ),
    )
```

replace

```python
        jobs = seed_jobs(db)
        candidates = seed_candidates(db, random.Random(SEED_FIELDS))
        seed_pipeline(db, candidates, jobs)
```

with

```python
        if args.team_only:
            jobs = db.query(Job).order_by(Job.id).all()
            seed_interviews(db, seed_team(db), jobs)
            print(f"  team: {db.query(User).filter(User.role != 'demo').count()}  "
                  f"interviews: {db.query(Interview).count()}  feedback: {db.query(Feedback).count()}")
            return 0

        jobs = seed_jobs(db)
        candidates = seed_candidates(db, random.Random(SEED_FIELDS))
        seed_pipeline(db, candidates, jobs)
        seed_interviews(db, seed_team(db), jobs)
```

and add to the summary prints at the end of `main()`, after the `applications:` line:

```python
        print(f"  team: {db.query(User).filter(User.role != 'demo').count()}  "
              f"interviews: {db.query(Interview).count()}  feedback: {db.query(Feedback).count()}")
```

- [ ] **Step 3: Verify on a fresh database**

```powershell
$dev = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $dev -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
poetry run python scripts/seed_demo.py --no-embeddings
docker exec recruitiq-db psql -U admin -d st_scratch -t -c "SELECT md5(string_agg(i.application_stage_id||':'||i.interviewer_id||':'||coalesce(f.rating::text,'-'), ',' ORDER BY i.id)) FROM interviews i LEFT JOIN feedback f ON f.interview_id = i.id"
poetry run python scripts/seed_demo.py --no-embeddings
poetry run python scripts/seed_demo.py --team-only
docker exec recruitiq-db psql -U admin -d st_scratch -t -c "SELECT md5(string_agg(i.application_stage_id||':'||i.interviewer_id||':'||coalesce(f.rating::text,'-'), ',' ORDER BY i.id)) FROM interviews i LEFT JOIN feedback f ON f.interview_id = i.id"
docker exec recruitiq-db psql -U admin -d st_scratch -c "SELECT u.role, COUNT(*) FROM users u GROUP BY 1" -c "SELECT COUNT(*) FILTER (WHERE f.id IS NULL) AS waiting, COUNT(f.id) AS submitted FROM interviews i LEFT JOIN feedback f ON f.interview_id = i.id"
```

Expected: the two md5 hashes are identical (re-runs and `--team-only` add nothing); users are 2 hiring_manager, 1 hiring_team, 3 interviewer, 1 demo; interviews show both waiting (the interviewing candidates' technical interviews) and submitted rows.

Then run the full suite against this scratch database (it now carries a migration and seed data built from nothing):

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:1"
poetry run pytest -q
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
$env:POSTGRES_CONN = $dev
poetry run python scripts/seed_demo.py --team-only
```

Expected: green except the two known embedding tests under the unreachable-Ollama env. The last command adds the team to the dev database for the live checks in Task 17.

- [ ] **Step 4: Commit**

Write `$S\commit-b11.txt`:

```
feat: seed a synthetic team and interview history

Six invented people across the three non-admin roles, no passwords
(create_admin.py now takes --role to give one a password from the
environment). Each job gets a hiring manager and a default technical
interviewer; finished rounds carry feedback and the round in progress is
left waiting. --team-only adds just this and never touches candidates or
applications, so it is safe on prod. Verified on a fresh database: two
full runs and a --team-only run give byte-identical interview history.
```

```powershell
git add scripts/seed_demo.py scripts/create_admin.py
git commit -F "$S\commit-b11.txt"
```

---
### Task 12: Web permission helpers and session roles

**Files:**
- Create: `web/src/lib/permissions.ts`, `web/src/lib/permissions.test.ts`, `web/src/lib/guards.ts`
- Modify: `web/src/lib/session.ts`, `web/src/lib/session.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/permissions.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import table from "./role-permissions.json";
import {
  CANDIDATES_ADD,
  DELETE_RECORDS,
  FEEDBACK_SUBMIT,
  JOBS_WRITE,
  PIPELINE_MOVE,
  PROFILE_EDIT,
  REPORTS_VIEW,
  SCORE_BEFORE_FEEDBACK,
  TEMPLATES_MANAGE,
  USERS_CHANGE_ROLE,
  USERS_INVITE,
  can,
  roleLabel,
} from "./permissions";

describe("can", () => {
  it("matches the spec matrix for the rows the screens depend on", () => {
    expect(can("hiring_manager", JOBS_WRITE)).toBe(true);
    expect(can("hiring_team", JOBS_WRITE)).toBe(false);
    expect(can("hiring_team", PIPELINE_MOVE)).toBe(true);
    expect(can("interviewer", PIPELINE_MOVE)).toBe(false);
    expect(can("interviewer", FEEDBACK_SUBMIT)).toBe(true);
    expect(can("interviewer", SCORE_BEFORE_FEEDBACK)).toBe(false);
    expect(can("hiring_manager", USERS_INVITE)).toBe(true);
    expect(can("hiring_manager", USERS_CHANGE_ROLE)).toBe(false);
    expect(can("admin", DELETE_RECORDS)).toBe(true);
    expect(can("demo", CANDIDATES_ADD)).toBe(false);
    expect(can("demo", SCORE_BEFORE_FEEDBACK)).toBe(true);
  });

  it("grants nothing to a missing or unknown role", () => {
    expect(can(null, PROFILE_EDIT)).toBe(false);
    expect(can(undefined, PROFILE_EDIT)).toBe(false);
    expect(can("superuser", PROFILE_EDIT)).toBe(false);
  });

  it("declares every permission the backend exports", () => {
    const declared = [
      JOBS_WRITE,
      CANDIDATES_ADD,
      PIPELINE_MOVE,
      FEEDBACK_SUBMIT,
      USERS_INVITE,
      USERS_CHANGE_ROLE,
      DELETE_RECORDS,
      SCORE_BEFORE_FEEDBACK,
      REPORTS_VIEW,
      TEMPLATES_MANAGE,
      PROFILE_EDIT,
    ];
    expect([...declared].sort()).toEqual([...table.permissions].sort());
  });
});

describe("roleLabel", () => {
  it("uses the spec's terms", () => {
    expect(roleLabel("hiring_manager")).toBe("Hiring manager");
    expect(roleLabel("hiring_team")).toBe("Hiring team");
    expect(roleLabel("demo")).toBe("Read-only demo");
    expect(roleLabel(null)).toBe("Signed out");
  });
});
```

In `web/src/lib/session.test.ts`, change the import line to

```ts
const { canWrite, getToken, getUser, hasPermission } = await import("./session");
```

and append:

```ts
describe("canWrite (ATS Phase B: may move the pipeline)", () => {
  for (const [role, expected] of [
    ["admin", true],
    ["hiring_manager", true],
    ["hiring_team", true],
    ["interviewer", false],
    ["demo", false],
  ] as const) {
    it(`is ${expected} for ${role}`, async () => {
      setCookie("jwt-abc");
      vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ ...DEMO_USER, role })));
      await expect(canWrite()).resolves.toBe(expected);
    });
  }
});

describe("hasPermission", () => {
  it("reads the generated table", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ...DEMO_USER, role: "hiring_team" })),
    );
    await expect(hasPermission("jobs.write")).resolves.toBe(false);
    await expect(hasPermission("candidates.add")).resolves.toBe(true);
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd web; npx vitest run src/lib/permissions.test.ts src/lib/session.test.ts`
Expected: FAIL, cannot resolve `./permissions`

- [ ] **Step 3: Write the helpers**

Create `web/src/lib/permissions.ts`:

```ts
/**
 * Who may do what, for drawing controls (ATS Phase B).
 *
 * `role-permissions.json` is generated from backend/utils/permissions.py by
 * scripts/export_permissions.py, and a backend test fails if it drifts. The
 * backend enforces the table; this only decides which buttons to show, since
 * a hidden button is not an access control.
 *
 * No `server-only` import: client components need `can` too.
 */
import table from "./role-permissions.json";

export const JOBS_WRITE = "jobs.write";
export const CANDIDATES_ADD = "candidates.add";
export const PIPELINE_MOVE = "pipeline.move";
export const FEEDBACK_SUBMIT = "feedback.submit";
export const USERS_INVITE = "users.invite";
export const USERS_CHANGE_ROLE = "users.change_role";
export const DELETE_RECORDS = "records.delete";
export const SCORE_BEFORE_FEEDBACK = "score.before_feedback";
export const REPORTS_VIEW = "reports.view";
export const TEMPLATES_MANAGE = "templates.manage";
export const PROFILE_EDIT = "profile.edit";

export type Permission =
  | typeof JOBS_WRITE
  | typeof CANDIDATES_ADD
  | typeof PIPELINE_MOVE
  | typeof FEEDBACK_SUBMIT
  | typeof USERS_INVITE
  | typeof USERS_CHANGE_ROLE
  | typeof DELETE_RECORDS
  | typeof SCORE_BEFORE_FEEDBACK
  | typeof REPORTS_VIEW
  | typeof TEMPLATES_MANAGE
  | typeof PROFILE_EDIT;

export type Role = "admin" | "hiring_manager" | "hiring_team" | "interviewer" | "demo";

/** The four roles a person on the team can hold, in the order screens list them. */
export const STAFF_ROLES: Role[] = ["admin", "hiring_manager", "hiring_team", "interviewer"];

const GRANTS = table.roles as Record<string, string[]>;
const LABELS = table.labels as Record<string, string>;

export function can(role: string | null | undefined, permission: Permission): boolean {
  if (!role) return false;
  return (GRANTS[role] ?? []).includes(permission);
}

export function roleLabel(role: string | null | undefined): string {
  if (!role) return "Signed out";
  return LABELS[role] ?? role;
}
```

In `web/src/lib/session.ts`, replace

```ts
export type Role = "admin" | "demo";

export interface SessionUser {
  id: string;
  email: string;
  role: Role;
  created_at: string;
}
```

with

```ts
import { can, PIPELINE_MOVE, type Permission, type Role } from "./permissions";

export type { Role } from "./permissions";

export interface SessionUser {
  id: string;
  email: string;
  name: string | null;
  role: Role;
  created_at: string;
}
```

(move the new `import` line up next to the other imports), and replace the whole `canWrite` function with:

```ts
/**
 * Whether the current session may move candidates through the pipeline
 * (admin, hiring manager, hiring team). Kept under its Phase A name because
 * the candidate page's stage actions are what it gates.
 *
 * Used only to hide controls. The real gate is `enforce_read_only` in the
 * backend: a hidden button is not an access control (spec section 2).
 */
export async function canWrite(): Promise<boolean> {
  return hasPermission(PIPELINE_MOVE);
}

/** Whether the current session holds one permission from the generated table. */
export async function hasPermission(permission: Permission): Promise<boolean> {
  const user = await getUser();
  return can(user?.role, permission);
}
```

Create `web/src/lib/guards.ts`:

```ts
import "server-only";

import { redirect } from "next/navigation";

import { getUser } from "./session";

/**
 * Send an interviewer to their own home (ATS Phase B).
 *
 * The API already refuses interviewers on Matching, Upload, the assistant,
 * and the team list; this is the courtesy that keeps them from landing on a
 * page that can only show an error.
 */
export async function redirectInterviewer(to: string = "/interviews"): Promise<void> {
  const user = await getUser();
  if (user?.role === "interviewer") redirect(to);
}
```

- [ ] **Step 4: Run the tests and the type check**

Run: `cd web; npx vitest run src/lib/permissions.test.ts src/lib/session.test.ts; npm run typecheck`
Expected: all pass; typecheck clean (the existing `canWrite` callers keep compiling; Task 17 moves the job pages onto `hasPermission`).

- [ ] **Step 5: Commit**

Write `$S\commit-b12.txt`:

```
feat(web): permission helpers read the generated table

can() and roleLabel() read role-permissions.json, so the screens draw
controls from the same matrix the API enforces. canWrite now means "may
move the pipeline" (admin, hiring manager, hiring team), and
hasPermission covers everything else. A guard sends interviewers to
their own page instead of a screen that can only show a 403.
```

```powershell
git add web/src/lib/permissions.ts web/src/lib/permissions.test.ts web/src/lib/guards.ts web/src/lib/session.ts web/src/lib/session.test.ts
git commit -F "$S\commit-b12.txt"
```

---

### Task 13: Grouped sidebar navigation

**Files:**
- Create: `web/src/lib/nav.ts`, `web/src/lib/nav.test.ts`, `web/src/components/sidebar.tsx`, `web/src/components/session-sidebar.tsx`
- Delete: `web/src/components/nav.tsx`
- Modify: `web/src/app/layout.tsx`, `web/src/components/session-badge.tsx`, `web/e2e/header-layout.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/nav.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { NAV_GROUPS, isActive, visibleGroups } from "./nav";
import type { Role } from "./permissions";

const labels = (role: Role | null) => visibleGroups(role).flatMap((g) => g.items.map((i) => i.label));
const all = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.label));

describe("visibleGroups", () => {
  it("shows the demo every screen", () => {
    expect(labels("demo")).toEqual(all);
    expect(all).toHaveLength(10);
  });

  it("gives interviewers only what they can use", () => {
    expect(labels("interviewer")).toEqual(["Jobs", "Candidates", "Interviews", "Transparency", "Settings"]);
  });

  it("shows everything while the session is still resolving", () => {
    expect(labels(null)).toEqual(all);
  });

  it("groups in the spec's order", () => {
    expect(NAV_GROUPS.map((g) => g.label)).toEqual(["Hiring", "Intelligence", "Admin"]);
  });
});

describe("isActive", () => {
  it("does not light Dashboard on every page", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/", "/jobs")).toBe(false);
  });

  it("covers a section's detail pages and nothing that merely shares a prefix", () => {
    expect(isActive("/jobs", "/jobs/12")).toBe(true);
    expect(isActive("/jobs", "/jobsboard")).toBe(false);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd web; npx vitest run src/lib/nav.test.ts`
Expected: FAIL, cannot resolve `./nav`

- [ ] **Step 3: Write the navigation table and the sidebar**

Create `web/src/lib/nav.ts`:

```ts
/**
 * The app's navigation, grouped as spec section 6 lays it out.
 *
 * Later phases add screens by appending to a group here (Phase D puts
 * Reports at the top of Admin). `hiddenFor` hides an item from roles that
 * cannot use it; the API refuses them anyway, so this is courtesy.
 */
import {
  Bot,
  Briefcase,
  CalendarCheck,
  LayoutDashboard,
  Scale,
  Settings,
  Sparkles,
  Upload,
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "./permissions";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  hiddenFor?: Role[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Hiring",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard, hiddenFor: ["interviewer"] },
      { href: "/jobs", label: "Jobs", icon: Briefcase },
      { href: "/candidates", label: "Candidates", icon: Users },
      { href: "/interviews", label: "Interviews", icon: CalendarCheck },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/matching", label: "Matching", icon: Sparkles, hiddenFor: ["interviewer"] },
      { href: "/upload", label: "Upload", icon: Upload, hiddenFor: ["interviewer"] },
      { href: "/assistant", label: "Assistant", icon: Bot, hiddenFor: ["interviewer"] },
      { href: "/transparency", label: "Transparency", icon: Scale },
    ],
  },
  {
    label: "Admin",
    items: [
      { href: "/team", label: "Team", icon: UserCog, hiddenFor: ["interviewer"] },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

/** The groups a role sees. Null while the session resolves: everything. */
export function visibleGroups(role: Role | null | undefined): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !role || !item.hiddenFor?.includes(role)),
  })).filter((group) => group.items.length > 0);
}

export function isActive(href: string, pathname: string): boolean {
  // "/" would otherwise prefix-match every route and light up permanently.
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
```

Create `web/src/components/sidebar.tsx`:

```tsx
"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";

import { isActive, visibleGroups } from "@/lib/nav";
import type { Role } from "@/lib/permissions";
import { cn } from "@/lib/utils";

/** A dot that appears only if a click did not resolve straight away (see globals.css). */
function PendingDot() {
  const { pending } = useLinkStatus();
  return <span aria-hidden className={cn("nav-hint", pending && "is-pending")} />;
}

/**
 * Grouped navigation (spec section 6): labelled groups from lg up, an
 * icon-only rail below. Every link carries aria-label and title because the
 * label text is display:none on the rail.
 *
 * `role` hides what a role cannot use. The layout renders this with
 * `role={null}` (everything) as the Suspense fallback and swaps in the
 * filtered list once the session resolves, so the shell never waits on
 * /auth/me.
 */
export function Sidebar({ role }: { role: Role | null }) {
  const pathname = usePathname();

  return (
    <aside className="sticky top-14 h-[calc(100vh-3.5rem)] w-14 shrink-0 overflow-y-auto border-r border-slate-200 bg-white lg:w-56">
      <nav aria-label="Main" className="flex flex-col gap-4 px-2 py-4 lg:px-3">
        {visibleGroups(role).map((group) => (
          <div key={group.label}>
            <p className="mb-1 hidden px-2 text-xs font-medium tracking-wide text-slate-400 uppercase lg:block">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(href, pathname);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-label={label}
                      title={label}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center justify-center gap-2 rounded-md px-2 py-2 text-sm font-medium transition-colors lg:justify-start",
                        active
                          ? "bg-indigo-600 text-white"
                          : "text-slate-600 hover:bg-indigo-50 hover:text-indigo-700",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden />
                      <span className="hidden lg:inline">{label}</span>
                      <PendingDot />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
```

Create `web/src/components/session-sidebar.tsx`:

```tsx
import { Sidebar } from "@/components/sidebar";
import { getUser } from "@/lib/session";

/** The sidebar for the signed-in role. Rendered inside Suspense by the layout. */
export async function SessionSidebar() {
  const user = await getUser();
  return <Sidebar role={user?.role ?? null} />;
}
```

- [ ] **Step 4: Put the sidebar in the layout**

```powershell
git rm web/src/components/nav.tsx
```

In `web/src/app/layout.tsx`, replace `import { Nav } from "@/components/nav";` with

```tsx
import { SessionSidebar } from "@/components/session-sidebar";
import { Sidebar } from "@/components/sidebar";
```

and replace everything inside `<body ...>` (the `<header>`, `<main>`, and `<footer>`) with:

```tsx
        <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
          <div className="flex h-14 items-center gap-4 px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
                R
              </span>
              <span>RecruitIQ</span>
            </Link>
            {/* Suspended on purpose, and load-bearing for every `loading.tsx`:
                SessionBadge reads cookies() and calls /auth/me, and runtime
                data read directly in a layout blocks navigation with no
                fallback. Behind a boundary the shell paints immediately. */}
            <div className="ml-auto shrink-0">
              <Suspense fallback={<SessionBadgeFallback />}>
                <SessionBadge />
              </Suspense>
            </div>
          </div>
        </header>

        <div className="flex flex-1">
          {/* Same reason as the badge: the role-filtered sidebar waits on
              /auth/me, so the unfiltered one stands in until it resolves. */}
          <Suspense fallback={<Sidebar role={null} />}>
            <SessionSidebar />
          </Suspense>

          <div className="flex min-w-0 flex-1 flex-col">
            <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">{children}</main>

            <footer className="border-t border-slate-200 bg-white">
              <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-slate-500 sm:px-6">
                <span>RecruitIQ is a portfolio demo. Data is seeded and read-only.</span>
                <a href="/docs" className="font-medium text-slate-700 hover:underline">
                  API docs
                </a>
              </div>
            </footer>
          </div>
        </div>
```

- [ ] **Step 5: Show the role, and the name, on the badge**

In `web/src/components/session-badge.tsx`, add `import { roleLabel } from "@/lib/permissions";` and replace the signed-in branch (the final `return (...)`) with:

```tsx
  return (
    <span className="flex items-center gap-3 whitespace-nowrap">
      <Link
        href="/settings"
        className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 hover:border-emerald-300"
        title={`Signed in as ${user.email}`}
      >
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
        {user.name ? <span className="hidden max-w-40 truncate sm:inline">{user.name} ·</span> : null}
        {roleLabel(user.role)}
      </Link>
      <form action="/api/auth/logout" method="post">
        <button
          type="submit"
          className="text-xs font-medium text-slate-500 hover:text-indigo-700"
        >
          Sign out
        </button>
      </form>
    </span>
  );
```

- [ ] **Step 6: Update the header layout check**

In `web/e2e/header-layout.spec.ts`, replace the final loop

```ts
    // Below lg the nav is icon-only, so each link needs its own accessible
    // name; getByRole would not find it otherwise.
    for (const name of ["Dashboard", "Candidates", "Matching", "Assistant", "Transparency"]) {
      await expect(page.getByRole("navigation").getByRole("link", { name })).toBeVisible();
    }
```

with

```ts
    // Below lg the sidebar is an icon rail, so each link needs its own
    // accessible name; getByRole would not find it otherwise.
    const nav = page.getByRole("navigation", { name: "Main" });
    for (const name of ["Dashboard", "Candidates", "Interviews", "Matching", "Assistant", "Transparency", "Settings"]) {
      await expect(nav.getByRole("link", { name })).toBeVisible();
    }
```

and update the file comment's second paragraph to: "Since ATS Phase B the navigation is a sidebar (an icon rail below lg), so the header holds only the logo and the account badge; the check still guards against sideways scroll at every width."

- [ ] **Step 7: Run the checks**

Run: `cd web; npx vitest run src/lib/nav.test.ts; npm run typecheck; npm run lint`
Expected: 6 nav tests pass; typecheck and lint clean.

- [ ] **Step 8: Commit**

Write `$S\commit-b13.txt`:

```
feat(web): grouped sidebar replaces the top navigation

Hiring, Intelligence, and Admin groups from lg up, an icon rail below,
per spec section 6; the header keeps the logo and an account badge that
now names the role (and the person). Interviewers do not see Dashboard,
Matching, Upload, Assistant, or Team. The unfiltered sidebar stands in
while the session resolves so no navigation waits on /auth/me.
```

```powershell
git add web/src/lib/nav.ts web/src/lib/nav.test.ts web/src/components/sidebar.tsx web/src/components/session-sidebar.tsx web/src/app/layout.tsx web/src/components/session-badge.tsx web/e2e/header-layout.spec.ts
git commit -F "$S\commit-b13.txt"
```

---

### Task 14: One forwarder for the new proxy routes; types and fetchers

**Files:**
- Create: `web/src/lib/forward.ts`, `web/src/lib/forward.test.ts`
- Create: `web/src/app/api/team/users/route.ts`, `web/src/app/api/team/users/[id]/route.ts`, `web/src/app/api/team/users/[id]/role/route.ts`, `web/src/app/api/team/me/route.ts`, `web/src/app/api/team/me/password/route.ts`, `web/src/app/api/applications/[id]/interviews/route.ts`, `web/src/app/api/interviews/[id]/route.ts`, `web/src/app/api/interviews/[id]/feedback/route.ts`, `web/src/app/api/jobs/[id]/stages/[stage]/default-interviewers/route.ts`
- Modify: `web/src/lib/domain.ts`, `web/src/lib/data.ts`, and the four existing proxy routes' sign-in messages

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/forward.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE } from "./config";

const cookieStore = { get: vi.fn() };
vi.mock("next/headers", () => ({ cookies: async () => cookieStore }));

const { forwardWrite } = await import("./forward");

function setCookie(value: string | undefined) {
  cookieStore.get.mockImplementation((name: string) =>
    name === SESSION_COOKIE && value !== undefined ? { name, value } : undefined,
  );
}

function request(body?: unknown): NextRequest {
  return new Request("http://localhost/api/x", {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  }) as unknown as NextRequest;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  cookieStore.get.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("forwardWrite", () => {
  it("refuses without a session and never calls the API", async () => {
    setCookie(undefined);
    const response = await forwardWrite(request({}), "/api/team/users", "POST");
    expect(response.status).toBe(401);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("attaches the bearer token and passes the API's status and body through", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(new Response('{"detail":"Your role cannot do this."}', { status: 403 }));
    const response = await forwardWrite(request({ role: "admin" }), "/api/team/users", "POST");
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ detail: "Your role cannot do this." });
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toMatch(/\/api\/team\/users$/);
    expect(new Headers((init as RequestInit).headers).get("authorization")).toBe("Bearer jwt-abc");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ role: "admin" });
  });

  it("sends no body on DELETE", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockResolvedValue(new Response('{"message":"ok"}', { status: 200 }));
    await forwardWrite(request(), "/api/interviews/3", "DELETE");
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init as RequestInit).body).toBeUndefined();
  });

  it("reports an unreachable API as 503", async () => {
    setCookie("jwt-abc");
    vi.mocked(fetch).mockRejectedValue(new TypeError("fetch failed"));
    const response = await forwardWrite(request({}), "/api/team/me", "PUT");
    expect(response.status).toBe(503);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd web; npx vitest run src/lib/forward.test.ts`
Expected: FAIL, cannot resolve `./forward`

- [ ] **Step 3: Write the forwarder and the routes**

Create `web/src/lib/forward.ts`:

```ts
import "server-only";

import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "./config";
import { getToken } from "./session";

/**
 * Forward one write to the API with the httpOnly session token (ATS Phase B).
 *
 * The jobs and pipeline handlers each carry their own copy of this; the
 * Phase B routes share this one. The backend's gate is the authority: this
 * passes its status and body through untouched and only refuses a request
 * that has no session at all.
 */
export async function forwardWrite(
  request: NextRequest,
  upstreamPath: string,
  method: "POST" | "PUT" | "DELETE",
): Promise<NextResponse> {
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ detail: "Sign in to make changes." }, { status: 401 });
  }

  const init: RequestInit = {
    method,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  };
  if (method !== "DELETE") {
    let body: unknown = {};
    try {
      body = await request.json();
    } catch {
      // An empty body is allowed; the API validates what it needs.
    }
    init.headers = { ...init.headers, "Content-Type": "application/json" };
    init.body = JSON.stringify(body ?? {});
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}${upstreamPath}`, init);
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  const text = await upstream.text();
  return new NextResponse(text || "{}", {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Path segments the routes accept, checked before anything reaches the API. */
export const NUMERIC_ID = /^\d+$/;
export const USER_ID = /^[0-9a-f-]{36}$/i;
export const STAGE_KEY = /^[a-z0-9_]+$/;

export function badRequest(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 400 });
}
```

Create each route file below. Every file starts with the same three lines:

```ts
import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, NUMERIC_ID, STAGE_KEY, USER_ID } from "@/lib/forward";
```

(import only the names the file uses, or lint fails on unused imports), followed by:

```ts
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
```

`web/src/app/api/team/users/route.ts`:

```ts
/** Invite someone to the team. */
export async function POST(request: NextRequest) {
  return forwardWrite(request, "/api/team/users", "POST");
}
```

`web/src/app/api/team/users/[id]/route.ts`:

```ts
/** Remove someone from the team. */
export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!USER_ID.test(id)) return badRequest("That is not a valid user id.");
  return forwardWrite(request, `/api/team/users/${id}`, "DELETE");
}
```

`web/src/app/api/team/users/[id]/role/route.ts`:

```ts
/** Change someone's role. */
export async function PUT(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!USER_ID.test(id)) return badRequest("That is not a valid user id.");
  return forwardWrite(request, `/api/team/users/${id}/role`, "PUT");
}
```

`web/src/app/api/team/me/route.ts`:

```ts
/** Update your own name and time zone. */
export async function PUT(request: NextRequest) {
  return forwardWrite(request, "/api/team/me", "PUT");
}
```

`web/src/app/api/team/me/password/route.ts`:

```ts
/** Change your own password. */
export async function PUT(request: NextRequest) {
  return forwardWrite(request, "/api/team/me/password", "PUT");
}
```

`web/src/app/api/applications/[id]/interviews/route.ts` (a static segment, so Next routes `/interviews` here rather than to the `[action]` handler):

```ts
/** Assign an interviewer to a stage of this application. */
export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid application id.");
  return forwardWrite(request, `/api/applications/${id}/interviews`, "POST");
}
```

`web/src/app/api/interviews/[id]/route.ts`:

```ts
/** Unassign an interviewer. */
export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid interview id.");
  return forwardWrite(request, `/api/interviews/${id}`, "DELETE");
}
```

`web/src/app/api/interviews/[id]/feedback/route.ts`:

```ts
/** Submit feedback for an interview. */
export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid interview id.");
  return forwardWrite(request, `/api/interviews/${id}/feedback`, "POST");
}
```

`web/src/app/api/jobs/[id]/stages/[stage]/default-interviewers/route.ts`:

```ts
/** Replace a stage's default interviewers. */
export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ id: string; stage: string }> },
) {
  const { id, stage } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid job id.");
  if (!STAGE_KEY.test(stage)) return badRequest("That is not a valid stage.");
  return forwardWrite(request, `/api/jobs/${id}/stages/${stage}/default-interviewers`, "PUT");
}
```

- [ ] **Step 4: Stop the old routes saying "administrator"**

Four strings, one per file, now that other roles can write:

- `web/src/app/api/applications/[id]/[action]/route.ts`: `"Sign in as an administrator to move candidates."` becomes `"Sign in to move candidates."`
- `web/src/app/api/jobs/route.ts`: `"Sign in as an administrator to create jobs."` becomes `"Sign in to create jobs."`
- `web/src/app/api/jobs/[id]/route.ts`: `` `Sign in as an administrator to ${action} jobs.` `` becomes `` `Sign in to ${action} jobs.` ``
- `web/src/app/api/resume/save/route.ts`: `"Sign in as an administrator to save candidates."` becomes `"Sign in to save candidates."`

Run: `rg -n "as an administrator" web/src`
Expected: no matches.

- [ ] **Step 5: Add the types and fetchers**

In `web/src/lib/domain.ts`, after the ATS Phase A aliases, add:

```ts
/** ATS Phase B: the team, interviews, and feedback. */
export type TeamMember = Schemas["TeamMember"];
export type Profile = Schemas["ProfileResponse"];
export type InterviewEntry = Schemas["InterviewOut"];
export type InterviewListItem = Schemas["InterviewListItem"];
export type StageDefaults = Schemas["StageDefaults"];
export type InterviewScope = "mine" | "pending" | "all";
```

In `web/src/lib/data.ts`, add `InterviewEntry`, `InterviewListItem`, `InterviewScope`, `Profile`, `StageDefaults`, and `TeamMember` to the type import from `./domain`, then append:

```ts
// --- ATS Phase B: team, interviews, feedback --------------------------------

/** Everyone on the team. Emails are null for roles that cannot invite. */
export async function listTeam(): Promise<TeamMember[]> {
  const result = await apiFetch<{ members: TeamMember[] }>("/api/team/users", {
    token: await getToken(),
  });
  return result.members;
}

export async function getMyProfile(): Promise<Profile | null> {
  return apiFetchOptional<Profile>("/api/team/me", { token: await getToken() });
}

export async function listInterviews(scope: InterviewScope): Promise<InterviewListItem[]> {
  const result = await apiFetch<{ items: InterviewListItem[] }>("/api/interviews", {
    token: await getToken(),
    query: { scope },
  });
  return result.items;
}

export async function getApplicationInterviews(applicationId: number): Promise<InterviewEntry[]> {
  return (
    (await apiFetchOptional<InterviewEntry[]>(`/api/applications/${applicationId}/interviews`, {
      token: await getToken(),
    })) ?? []
  );
}

export async function getDefaultInterviewers(jobId: number): Promise<StageDefaults[] | null> {
  const result = await apiFetchOptional<{ stages: StageDefaults[] }>(
    `/api/jobs/${jobId}/default-interviewers`,
    { token: await getToken() },
  );
  return result?.stages ?? null;
}
```

- [ ] **Step 6: Run the checks**

Run: `cd web; npx vitest run src/lib/forward.test.ts; npm run typecheck; npm run lint`
Expected: 4 forward tests pass; typecheck and lint clean.

- [ ] **Step 7: Commit**

Write `$S\commit-b14.txt`:

```
feat(web): proxy routes for team, interviews, and feedback

One tested forwarder attaches the session token and passes the API's
status through; nine small routes validate their path segments and use
it. The older routes stop saying "administrator" now that other roles
can write. Types and fetchers for the new screens.
```

```powershell
git add web/src/lib/forward.ts web/src/lib/forward.test.ts web/src/app/api web/src/lib/domain.ts web/src/lib/data.ts
git commit -F "$S\commit-b14.txt"
```

---
### Task 15: Team and Settings pages

**Files:**
- Create: `web/src/lib/interviews.ts`, `web/src/lib/interviews.test.ts` (shared labels; used here for `memberName`)
- Create: `web/src/components/team-invite-form.tsx`, `web/src/components/team-member-actions.tsx`, `web/src/components/settings-form.tsx`, `web/src/components/password-form.tsx`
- Create: `web/src/app/team/page.tsx`, `web/src/app/team/loading.tsx`, `web/src/app/settings/page.tsx`, `web/src/app/settings/loading.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/interviews.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { INTERVIEW_STATE_LABELS, RECOMMENDATIONS, RECOMMENDATION_LABELS, memberName } from "./interviews";

describe("interview vocabulary", () => {
  it("has plain English for every recommendation and state", () => {
    for (const key of RECOMMENDATIONS) expect(RECOMMENDATION_LABELS[key]).toBeTruthy();
    expect(RECOMMENDATION_LABELS.strong_no_hire).toBe("Strong no hire");
    for (const state of ["upcoming", "waiting", "submitted", "skipped"]) {
      expect(INTERVIEW_STATE_LABELS[state]).toBeTruthy();
    }
  });

  it("names a person without ever showing an email", () => {
    expect(memberName({ name: "Priya Raman", role: "hiring_manager" })).toBe("Priya Raman");
    expect(memberName({ name: null, role: "admin" })).toBe("Admin");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd web; npx vitest run src/lib/interviews.test.ts`
Expected: FAIL, cannot resolve `./interviews`

- [ ] **Step 3: Write the shared vocabulary**

Create `web/src/lib/interviews.ts`:

```ts
/**
 * Interview and feedback vocabulary (ATS Phase B). Mirrors
 * feedback_service.py; the API validates, this only labels.
 */
import { roleLabel } from "./permissions";

export const RECOMMENDATIONS = ["strong_hire", "hire", "no_hire", "strong_no_hire"] as const;

export const RECOMMENDATION_LABELS: Record<string, string> = {
  strong_hire: "Strong hire",
  hire: "Hire",
  no_hire: "No hire",
  strong_no_hire: "Strong no hire",
};

export const INTERVIEW_STATE_LABELS: Record<string, string> = {
  upcoming: "Upcoming",
  waiting: "Waiting for feedback",
  submitted: "Feedback submitted",
  skipped: "Stage skipped",
};

/** Same rule as the backend's display_name: a name, else the role. Never an email. */
export function memberName(member: { name?: string | null; role: string }): string {
  return member.name || roleLabel(member.role);
}
```

- [ ] **Step 4: Write the Team components**

Create `web/src/components/team-invite-form.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Loader2, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { STAFF_ROLES, roleLabel } from "@/lib/permissions";

/**
 * Add someone to the team. No email is sent (spec: email arrives in Phase E):
 * the API returns a temporary password once, this shows it once, and the
 * inviter passes it on.
 */
export function TeamInviteForm({ canInviteAdmin }: { canInviteAdmin: boolean }) {
  const router = useRouter();
  const roles = STAFF_ROLES.filter((role) => canInviteAdmin || role !== "admin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("interviewer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ name: string; email: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const response = await fetch("/api/team/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, role }),
      });
      const payload = (await response.json().catch(() => null)) as {
        detail?: string;
        temporary_password?: string;
      } | null;
      if (!response.ok || !payload?.temporary_password) {
        throw new Error(payload?.detail || `Could not add them (${response.status})`);
      }
      setCreated({ name, email, password: payload.temporary_password });
      setName("");
      setEmail("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function copy(password: string) {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add someone</CardTitle>
        <p className="text-xs text-slate-500">
          They sign in with a temporary password you pass on, then change it in Settings.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Name</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Email</span>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm"
            >
              {roles.map((r) => (
                <option key={r} value={r}>
                  {roleLabel(r)}
                </option>
              ))}
            </select>
          </label>
          {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <UserPlus className="mr-2 h-4 w-4" aria-hidden />
            )}
            Add to team
          </Button>
        </form>

        {created ? (
          <div role="status" className="space-y-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm">
            <p className="font-medium text-emerald-900">
              {created.name} can now sign in as {created.email}.
            </p>
            <p className="text-emerald-800">Temporary password, shown only this once:</p>
            <div className="flex flex-wrap items-center gap-2">
              <code className="rounded bg-white px-2 py-1 font-mono text-sm text-slate-900">
                {created.password}
              </code>
              <Button type="button" variant="outline" size="sm" onClick={() => copy(created.password)}>
                <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
```

Create `web/src/components/team-member-actions.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { STAFF_ROLES, roleLabel } from "@/lib/permissions";

/** Role picker and Remove for one row of the Team page. Admin only (the API checks). */
export function TeamMemberActions({
  member,
  isSelf,
  canChangeRole,
  canRemove,
}: {
  member: { id: string; name: string; role: string };
  isSelf: boolean;
  canChangeRole: boolean;
  canRemove: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(url: string, method: "PUT" | "DELETE", body?: unknown) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(url, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Request failed (${response.status})`);
      setConfirming(false);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex flex-wrap items-center justify-end gap-2">
        {canChangeRole && !isSelf ? (
          <select
            aria-label={`Role for ${member.name}`}
            value={member.role}
            disabled={busy}
            onChange={(e) => {
              void send(`/api/team/users/${member.id}/role`, "PUT", { role: e.target.value });
            }}
            className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs"
          >
            {STAFF_ROLES.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r)}
              </option>
            ))}
          </select>
        ) : (
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">
            {roleLabel(member.role)}
            {isSelf ? " (you)" : ""}
          </span>
        )}
        {canRemove && !isSelf ? (
          confirming ? (
            <>
              <Button
                type="button"
                size="sm"
                disabled={busy}
                onClick={() => send(`/api/team/users/${member.id}`, "DELETE")}
                className="bg-rose-600 text-white hover:bg-rose-700"
              >
                {busy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
                Remove {member.name}
              </Button>
              <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => setConfirming(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Button type="button" size="sm" variant="outline" onClick={() => setConfirming(true)}>
              Remove
            </Button>
          )
        ) : null}
      </div>
      {error ? <p className="max-w-xs text-right text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 5: Write the Team page**

Create `web/src/app/team/page.tsx`:

```tsx
import { ErrorState, PageHeader } from "@/components/page-header";
import { TeamInviteForm } from "@/components/team-invite-form";
import { TeamMemberActions } from "@/components/team-member-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { listTeam } from "@/lib/data";
import { formatDate } from "@/lib/format";
import { redirectInterviewer } from "@/lib/guards";
import { memberName } from "@/lib/interviews";
import { DELETE_RECORDS, USERS_CHANGE_ROLE, USERS_INVITE, can, roleLabel } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export const metadata = { title: "Team · RecruitIQ" };

const ROLE_GUIDE = [
  ["admin", "Everything, including roles and removing people."],
  ["hiring_manager", "Jobs, candidates, moving candidates, and adding people."],
  ["hiring_team", "Candidates, and moving them through the pipeline."],
  ["interviewer", "Their own interviews and feedback. Match scores appear after they submit feedback."],
] as const;

export default async function TeamPage() {
  await redirectInterviewer();
  const user = await getUser();

  let members;
  try {
    members = await listTeam();
  } catch (error) {
    return (
      <>
        <PageHeader title="Team" />
        <ErrorState
          title="Could not load the team"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  const role = user?.role;
  const canInvite = can(role, USERS_INVITE);
  const canChangeRole = can(role, USERS_CHANGE_ROLE);
  const canRemove = can(role, DELETE_RECORDS);

  return (
    <>
      <PageHeader
        title="Team"
        description="Who can sign in, and what each role can do."
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">
              {members.length} {members.length === 1 ? "person" : "people"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {members.length === 0 ? (
              <p className="text-sm text-slate-500">Nobody yet besides the demo account.</p>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm">
                {members.map((member) => (
                  <li
                    key={member.id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-slate-900">
                        {memberName(member)}
                      </span>
                      <span className="block truncate text-xs text-slate-500">
                        {member.email ? `${member.email} · ` : ""}joined {formatDate(member.created_at)}
                      </span>
                    </span>
                    {canChangeRole || canRemove ? (
                      <TeamMemberActions
                        member={{ id: member.id, name: memberName(member), role: member.role }}
                        isSelf={member.id === user?.id}
                        canChangeRole={canChangeRole}
                        canRemove={canRemove}
                      />
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">
                        {roleLabel(member.role)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          {canInvite ? (
            <TeamInviteForm canInviteAdmin={role === "admin"} />
          ) : (
            <Card>
              <CardContent className="p-6 text-sm text-slate-500">
                Hiring managers and administrators can add people to the team.
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">What each role can do</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3 text-sm">
                {ROLE_GUIDE.map(([key, text]) => (
                  <div key={key}>
                    <dt className="font-medium text-slate-800">{roleLabel(key)}</dt>
                    <dd className="text-slate-500">{text}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
```

Create `web/src/app/team/loading.tsx`:

```tsx
import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";

export default function Loading() {
  return (
    <>
      <HeaderSkeleton />
      <div className="grid gap-6 lg:grid-cols-3">
        <CardSkeleton className="h-96 lg:col-span-2" />
        <CardSkeleton className="h-96" />
      </div>
    </>
  );
}
```

- [ ] **Step 6: Write the Settings components and page**

Create `web/src/components/settings-form.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Phoenix",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Australia/Sydney",
  "UTC",
];

export function SettingsForm({
  name: initialName,
  timezone: initialTimezone,
  email,
  roleText,
}: {
  name: string;
  timezone: string;
  email: string;
  roleText: string;
}) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [timezone, setTimezone] = useState(initialTimezone);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch("/api/team/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, timezone: timezone || null }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not save (${response.status})`);
      setMessage({ ok: true, text: "Saved." });
      router.refresh();
    } catch (err) {
      setMessage({ ok: false, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Profile</CardTitle>
        <p className="text-xs text-slate-500">
          {email} · {roleText}
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Name</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Time zone</span>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm"
            >
              <option value="">Not set</option>
              {TIMEZONES.map((zone) => (
                <option key={zone} value={zone}>
                  {zone.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          {message ? (
            <p className={message.ok ? "text-sm text-emerald-700" : "text-sm font-medium text-rose-700"}>
              {message.text}
            </p>
          ) : null}
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Save className="mr-2 h-4 w-4" aria-hidden />
            )}
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

Create `web/src/components/password-form.tsx`:

```tsx
"use client";

import { useState } from "react";
import { KeyRound, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (next !== confirm) {
      setMessage({ ok: false, text: "The new passwords do not match." });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch("/api/team/me/password", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not change it (${response.status})`);
      setCurrent("");
      setNext("");
      setConfirm("");
      setMessage({ ok: true, text: "Password changed." });
    } catch (err) {
      setMessage({ ok: false, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Password</CardTitle>
        <p className="text-xs text-slate-500">At least 12 characters.</p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Current password</span>
            <Input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" required />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">New password</span>
            <Input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" minLength={12} required />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">New password again</span>
            <Input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" minLength={12} required />
          </label>
          {message ? (
            <p className={message.ok ? "text-sm text-emerald-700" : "text-sm font-medium text-rose-700"}>
              {message.text}
            </p>
          ) : null}
          <Button type="submit" variant="outline" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <KeyRound className="mr-2 h-4 w-4" aria-hidden />
            )}
            Change password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

Create `web/src/app/settings/page.tsx`:

```tsx
import Link from "next/link";

import { ErrorState, PageHeader } from "@/components/page-header";
import { PasswordForm } from "@/components/password-form";
import { SettingsForm } from "@/components/settings-form";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getMyProfile } from "@/lib/data";
import { roleLabel } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export const metadata = { title: "Settings · RecruitIQ" };

export default async function SettingsPage() {
  const user = await getUser();

  if (!user || user.role === "demo") {
    return (
      <>
        <PageHeader title="Settings" description="Your name, time zone, and password." />
        <Card>
          <CardContent className="p-6 text-sm text-slate-600">
            The read-only demo account has no settings to change.{" "}
            <Link href="/login" className="font-medium text-indigo-700 hover:underline">
              Sign in
            </Link>{" "}
            to set your name, time zone, and password.
          </CardContent>
        </Card>
      </>
    );
  }

  let profile;
  try {
    profile = await getMyProfile();
  } catch (error) {
    return (
      <>
        <PageHeader title="Settings" />
        <ErrorState
          title="Could not load your settings"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }
  if (!profile) {
    return (
      <>
        <PageHeader title="Settings" />
        <ErrorState title="Could not load your settings" detail="Your account was not found. Sign in again." />
      </>
    );
  }

  return (
    <>
      <PageHeader title="Settings" description="Your name, time zone, and password." />
      <div className="grid gap-6 lg:grid-cols-2">
        <SettingsForm
          name={profile.name ?? ""}
          timezone={profile.timezone ?? ""}
          email={profile.email ?? user.email}
          roleText={roleLabel(profile.role)}
        />
        <PasswordForm />
      </div>
    </>
  );
}
```

Create `web/src/app/settings/loading.tsx`:

```tsx
import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";

export default function Loading() {
  return (
    <>
      <HeaderSkeleton />
      <div className="grid gap-6 lg:grid-cols-2">
        <CardSkeleton className="h-72" />
        <CardSkeleton className="h-72" />
      </div>
    </>
  );
}
```

- [ ] **Step 7: Run the checks**

Run: `cd web; npx vitest run src/lib/interviews.test.ts; npm run typecheck; npm run lint`
Expected: 2 tests pass; typecheck and lint clean.

- [ ] **Step 8: Commit**

Write `$S\commit-b15.txt`:

```
feat(web): Team and Settings pages

Team lists everyone with their role; hiring managers and admins can add
people and see the temporary password once, and admins can change roles
or remove people. The demo sees names and roles but no email addresses.
Settings sets your name, time zone, and password; the demo gets a
sentence pointing to Sign in.
```

```powershell
git add web/src/lib/interviews.ts web/src/lib/interviews.test.ts web/src/components/team-invite-form.tsx web/src/components/team-member-actions.tsx web/src/components/settings-form.tsx web/src/components/password-form.tsx web/src/app/team web/src/app/settings
git commit -F "$S\commit-b15.txt"
```

---

### Task 16: Interviews page, feedback form, and the candidate page panel

**Files:**
- Create: `web/src/components/feedback-form.tsx`, `web/src/components/assign-interviewer.tsx`, `web/src/components/interview-panel.tsx`
- Create: `web/src/app/interviews/page.tsx`, `web/src/app/interviews/loading.tsx`
- Modify: `web/src/components/application-timeline.tsx`, `web/src/app/candidates/[id]/page.tsx`

- [ ] **Step 1: Write the feedback and assignment components**

Create `web/src/components/feedback-form.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RECOMMENDATIONS, RECOMMENDATION_LABELS } from "@/lib/interviews";
import { cn } from "@/lib/utils";

const CHOICE = "cursor-pointer rounded-md border px-2.5 py-1 text-sm";
const ON = "border-indigo-600 bg-indigo-600 text-white";
const OFF = "border-slate-200 bg-white text-slate-700 hover:border-indigo-300";

/** One interviewer's feedback on one stage. Final once submitted. */
export function FeedbackForm({ interviewId, stageName }: { interviewId: number; stageName: string }) {
  const router = useRouter();
  const [rating, setRating] = useState<number | null>(null);
  const [recommendation, setRecommendation] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (rating === null || recommendation === null) {
      setError("Choose a rating and a recommendation.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/interviews/${interviewId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, recommendation, notes }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not submit (${response.status})`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-md bg-slate-50 p-3">
      <p className="text-xs text-slate-600">
        Your feedback for {stageName}. It is final once submitted, and other interviewers see it
        only after giving their own.
      </p>
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-slate-700">Rating</legend>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <label key={n} className={cn(CHOICE, "grid w-9 place-items-center", rating === n ? ON : OFF)}>
              <input
                type="radio"
                name={`rating-${interviewId}`}
                value={n}
                checked={rating === n}
                onChange={() => setRating(n)}
                className="sr-only"
              />
              {n}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-slate-700">Recommendation</legend>
        <div className="flex flex-wrap gap-1">
          {RECOMMENDATIONS.map((key) => (
            <label key={key} className={cn(CHOICE, recommendation === key ? ON : OFF)}>
              <input
                type="radio"
                name={`recommendation-${interviewId}`}
                value={key}
                checked={recommendation === key}
                onChange={() => setRecommendation(key)}
                className="sr-only"
              />
              {RECOMMENDATION_LABELS[key]}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="block">
        <span className="text-xs font-medium text-slate-700">Notes (optional)</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          maxLength={5000}
          className="mt-1 w-full rounded-md border border-slate-200 bg-white p-2 text-sm text-slate-800"
        />
      </label>
      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
      <Button type="submit" size="sm" disabled={busy}>
        {busy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
        Submit feedback
      </Button>
    </form>
  );
}
```

Create `web/src/components/assign-interviewer.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Put someone on a stage of this application. Writers only (the API checks). */
export function AssignInterviewer({
  applicationId,
  stages,
  team,
  defaultStage,
}: {
  applicationId: number;
  stages: { key: string; name: string }[];
  team: { id: string; name: string }[];
  defaultStage?: string;
}) {
  const router = useRouter();
  const initialStage =
    defaultStage && stages.some((s) => s.key === defaultStage) ? defaultStage : (stages[0]?.key ?? "");
  const [stageKey, setStageKey] = useState(initialStage);
  const [personId, setPersonId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function assign() {
    if (busy) return;
    if (!stageKey || !personId) {
      setError("Choose a stage and a person.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${applicationId}/interviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage_key: stageKey, interviewer_id: personId }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not assign (${response.status})`);
      setPersonId("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (stages.length === 0 || team.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <select
        aria-label="Stage"
        value={stageKey}
        onChange={(e) => setStageKey(e.target.value)}
        className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm"
      >
        {stages.map((s) => (
          <option key={s.key} value={s.key}>
            {s.name}
          </option>
        ))}
      </select>
      <select
        aria-label="Interviewer"
        value={personId}
        onChange={(e) => setPersonId(e.target.value)}
        className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm"
      >
        <option value="">Choose someone</option>
        {team.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name}
          </option>
        ))}
      </select>
      <Button type="button" size="sm" variant="outline" onClick={assign} disabled={busy}>
        {busy ? (
          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <UserPlus className="mr-1.5 h-3.5 w-3.5" aria-hidden />
        )}
        Assign
      </Button>
      {error ? <p className="w-full text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
```

Create `web/src/components/interview-panel.tsx`:

```tsx
import { AssignInterviewer } from "@/components/assign-interviewer";
import { FeedbackForm } from "@/components/feedback-form";
import type { ApplicationDetail, InterviewEntry, TeamMember } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { INTERVIEW_STATE_LABELS, RECOMMENDATION_LABELS, memberName } from "@/lib/interviews";

/**
 * Who interviews this candidate for this job, and what they thought
 * (ATS Phase B). Rendered inside the application's timeline card.
 *
 * The API decides what each viewer may read: a colleague's feedback arrives
 * as `feedback_hidden` until the viewer has submitted their own.
 */
export function InterviewPanel({
  application,
  interviews,
  team,
  viewerId,
  canAssign,
}: {
  application: ApplicationDetail;
  interviews: InterviewEntry[];
  team: TeamMember[];
  viewerId: string | null;
  canAssign: boolean;
}) {
  const rounds = application.stages
    .filter((s) => s.kind === "round" && s.enabled && s.status !== "skipped")
    .map((s) => ({ key: s.key, name: s.name }));

  return (
    <section id={`interviews-${application.id}`} className="space-y-3 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-medium text-slate-800">Interviews and feedback</h3>
      {interviews.length === 0 ? (
        <p className="text-sm text-slate-500">No interviewers assigned yet.</p>
      ) : (
        <ul className="space-y-3">
          {interviews.map((interview) => (
            <li key={interview.id} className="rounded-md border border-slate-200 p-3 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium text-slate-800">
                  {interview.interviewer_name}{" "}
                  <span className="text-xs font-normal text-slate-500">{interview.stage_name}</span>
                </span>
                <span className="text-xs text-slate-500">{INTERVIEW_STATE_LABELS[interview.state]}</span>
              </div>
              {interview.feedback ? (
                <div className="mt-2 space-y-1">
                  <p className="text-slate-700">
                    {interview.feedback.rating} of 5 ·{" "}
                    {RECOMMENDATION_LABELS[interview.feedback.recommendation] ?? interview.feedback.recommendation}
                  </p>
                  {interview.feedback.notes ? (
                    <p className="whitespace-pre-line text-slate-600">{interview.feedback.notes}</p>
                  ) : null}
                  <p className="text-xs text-slate-400">Submitted {formatDate(interview.feedback.submitted_at)}</p>
                </div>
              ) : interview.feedback_hidden ? (
                <p className="mt-2 text-xs text-slate-500">
                  Feedback submitted. You will see it after you submit your own.
                </p>
              ) : interview.interviewer_id === viewerId && interview.state === "waiting" ? (
                <FeedbackForm interviewId={interview.id} stageName={interview.stage_name} />
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {canAssign && application.status === "active" ? (
        <AssignInterviewer
          applicationId={application.id}
          stages={rounds}
          team={team.map((m) => ({ id: m.id, name: memberName(m) }))}
          defaultStage={application.current_stage_key ?? undefined}
        />
      ) : null}
    </section>
  );
}
```

- [ ] **Step 2: Let the timeline card hold the panel**

In `web/src/components/application-timeline.tsx`, add `import type { ReactNode } from "react";` at the top, change the props to

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

and replace

```tsx
        {actions.length > 0 && current ? (
          <StageActions applicationId={application.id} actions={actions} stageName={current.name} />
        ) : null}
      </CardContent>
```

with

```tsx
        {actions.length > 0 && current ? (
          <StageActions applicationId={application.id} actions={actions} stageName={current.name} />
        ) : null}
        {children}
      </CardContent>
```

- [ ] **Step 3: Wire the candidate page**

In `web/src/app/candidates/[id]/page.tsx`:

Add imports (merge into the existing `@/lib/data` and `@/lib/session` imports):

```tsx
import { InterviewPanel } from "@/components/interview-panel";
import { ApiError } from "@/lib/api";
import { getApplicationInterviews, listTeam } from "@/lib/data";
import { getUser } from "@/lib/session";
```

Replace

```tsx
  const [applications, savedJobs, resumes, writable] = await Promise.all([
    getCandidateApplications(id),
    getCandidateSavedJobs(id),
    getCandidateResumes(id),
    canWrite(),
  ]);
  const details = (
    await Promise.all(applications.map((application) => getApplication(application.id)))
  ).filter((detail): detail is NonNullable<typeof detail> => detail !== null);
```

with

```tsx
  const [applications, savedJobs, resumes, writable, user] = await Promise.all([
    getCandidateApplications(id),
    getCandidateSavedJobs(id),
    getCandidateResumes(id),
    canWrite(),
    getUser(),
  ]);
  const [details, team] = await Promise.all([
    Promise.all(applications.map((application) => getApplication(application.id))).then((all) =>
      all.filter((detail): detail is NonNullable<typeof detail> => detail !== null),
    ),
    // Only writers assign interviewers; nobody else needs the team list.
    writable ? listTeam().catch(() => []) : Promise.resolve([]),
  ]);
  const interviews = new Map(
    await Promise.all(
      details.map(async (detail) => [detail.id, await getApplicationInterviews(detail.id)] as const),
    ),
  );
```

Replace

```tsx
            details.map((detail) => (
              <ApplicationTimeline key={detail.id} application={detail} writable={writable} />
            ))
```

with

```tsx
            details.map((detail) => (
              <ApplicationTimeline key={detail.id} application={detail} writable={writable}>
                <InterviewPanel
                  application={detail}
                  interviews={interviews.get(detail.id) ?? []}
                  team={team}
                  viewerId={user?.id ?? null}
                  canAssign={writable}
                />
              </ApplicationTimeline>
            ))
```

Replace the start of `RecommendedRoles`

```tsx
async function RecommendedRoles({ candidateId }: { candidateId: string }) {
  // If matching fails, the profile still renders; an empty panel beats a 500 on
  // the whole route.
  const matches = await matchJobsForCandidate(candidateId).catch(
    () => [] as Awaited<ReturnType<typeof matchJobsForCandidate>>,
  );
```

with

```tsx
async function RecommendedRoles({ candidateId }: { candidateId: string }) {
  // If matching fails, the profile still renders; an empty panel beats a 500 on
  // the whole route. A 403 is the score rule (ATS Phase B): an interviewer
  // sees match scores only after giving feedback, and the API says so.
  let matches: Awaited<ReturnType<typeof matchJobsForCandidate>> = [];
  try {
    matches = await matchJobsForCandidate(candidateId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return <p className="text-sm text-slate-500">{error.detail}</p>;
    }
  }
```

- [ ] **Step 4: Write the Interviews page**

Create `web/src/app/interviews/page.tsx`:

```tsx
import Link from "next/link";

import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { listInterviews } from "@/lib/data";
import type { InterviewScope } from "@/lib/domain";
import { INTERVIEW_STATE_LABELS } from "@/lib/interviews";
import { getUser } from "@/lib/session";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata = { title: "Interviews · RecruitIQ" };

const SCOPES: { key: InterviewScope; label: string }[] = [
  { key: "mine", label: "My interviews" },
  { key: "pending", label: "Waiting for feedback" },
  { key: "all", label: "All" },
];

const EMPTY: Record<InterviewScope, string> = {
  mine: "Nobody has assigned you an interview yet.",
  pending: "No feedback is outstanding.",
  all: "No interviews have been assigned yet.",
};

const STATE_CLASSES: Record<string, string> = {
  waiting: "border-amber-200 bg-amber-50 text-amber-700",
  upcoming: "border-slate-200 bg-slate-50 text-slate-600",
  submitted: "border-emerald-200 bg-emerald-50 text-emerald-700",
  skipped: "border-neutral-200 bg-neutral-100 text-neutral-500",
};

export default async function InterviewsPage({ searchParams }: PageProps<"/interviews">) {
  const params = await searchParams;
  const user = await getUser();
  const interviewer = user?.role === "interviewer";
  const requested = Array.isArray(params.scope) ? params.scope[0] : params.scope;
  // Signed-in staff start on their own list; the demo starts on everything.
  const fallback: InterviewScope = user && user.role !== "demo" ? "mine" : "all";
  const scope: InterviewScope = interviewer
    ? "mine"
    : SCOPES.some((s) => s.key === requested)
      ? (requested as InterviewScope)
      : fallback;

  let items;
  try {
    items = await listInterviews(scope);
  } catch (error) {
    return (
      <>
        <PageHeader title="Interviews" />
        <ErrorState
          title="Could not load interviews"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Interviews"
        description={
          interviewer
            ? "The candidates you are interviewing. Their match scores appear once you submit your feedback."
            : "Who is interviewing whom, and whose feedback is still outstanding."
        }
      />
      {!interviewer ? (
        <nav aria-label="Interview views" className="mb-4 flex flex-wrap gap-2">
          {SCOPES.map((s) => (
            <Link
              key={s.key}
              href={`/interviews?scope=${s.key}`}
              aria-current={s.key === scope ? "page" : undefined}
              className={cn(
                "rounded-full border px-3 py-1 text-sm",
                s.key === scope
                  ? "border-indigo-600 bg-indigo-600 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-indigo-300",
              )}
            >
              {s.label}
            </Link>
          ))}
        </nav>
      ) : null}

      {items.length === 0 ? (
        <EmptyState title={EMPTY[scope]} />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-slate-100">
              {items.map((item) => {
                const href = `/candidates/${item.candidate_id}#interviews-${item.application_id}`;
                const yours = item.interviewer_id === user?.id;
                return (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm sm:px-6"
                  >
                    <span className="min-w-0">
                      <Link href={href} className="block truncate font-medium text-slate-900 hover:underline">
                        {item.candidate_name}
                      </Link>
                      <span className="block truncate text-xs text-slate-500">
                        {item.job_title} · {item.stage_name}
                        {scope !== "mine" ? ` · ${item.interviewer_name}` : ""}
                      </span>
                    </span>
                    <span className="flex items-center gap-3">
                      <span className={cn("rounded-full border px-2.5 py-0.5 text-xs", STATE_CLASSES[item.state])}>
                        {INTERVIEW_STATE_LABELS[item.state]}
                      </span>
                      {yours && item.state === "waiting" ? (
                        <Link href={href} className="text-xs font-medium text-indigo-700 hover:underline">
                          Give feedback
                        </Link>
                      ) : null}
                    </span>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  );
}
```

Create `web/src/app/interviews/loading.tsx`:

```tsx
import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";

export default function Loading() {
  return (
    <>
      <HeaderSkeleton />
      <CardSkeleton className="h-96" />
    </>
  );
}
```

- [ ] **Step 5: Run the checks**

Run: `cd web; npm run typecheck; npm run lint; npm test`
Expected: clean; all unit tests pass.

- [ ] **Step 6: Commit**

Write `$S\commit-b16.txt`:

```
feat(web): Interviews page and feedback on the candidate page

Each application's card gains an Interviews and feedback section: who is
assigned to which stage, feedback where the viewer may read it, an
Assign control for writers, and the feedback form for the assigned
interviewer once their stage has started. Recommended roles explain the
score rule to an interviewer instead of rendering an empty panel. The
Interviews page lists my interviews, outstanding feedback, or all.
```

```powershell
git add web/src/components/feedback-form.tsx web/src/components/assign-interviewer.tsx web/src/components/interview-panel.tsx web/src/components/application-timeline.tsx "web/src/app/candidates/[id]/page.tsx" web/src/app/interviews
git commit -F "$S\commit-b16.txt"
```

---

### Task 17: Job pages, guards, and the transparency card

**Files:**
- Create: `web/src/components/default-interviewers-editor.tsx`
- Modify: `web/src/app/jobs/[id]/page.tsx`, `web/src/app/jobs/page.tsx`, `web/src/app/jobs/new/page.tsx`, `web/src/app/jobs/[id]/edit/page.tsx`
- Modify: `web/src/app/page.tsx`, `web/src/app/matching/page.tsx`, `web/src/app/upload/page.tsx`, `web/src/app/assistant/page.tsx`, `web/src/app/transparency/page.tsx`
- Create: `web/e2e/team-screens.spec.ts`

- [ ] **Step 1: Write the default-interviewers editor**

Create `web/src/components/default-interviewers-editor.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, X } from "lucide-react";

import type { StageDefaults } from "@/lib/domain";

/**
 * Who is assigned automatically when a candidate reaches each round of this
 * job. Read-only unless `editable` (jobs.write); the API checks either way.
 */
export function DefaultInterviewersEditor({
  jobId,
  stages,
  team,
  editable,
}: {
  jobId: number;
  stages: StageDefaults[];
  team: { id: string; name: string }[];
  editable: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(stageKey: string, userIds: string[]) {
    setBusy(stageKey);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${jobId}/stages/${stageKey}/default-interviewers`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_ids: userIds }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not save (${response.status})`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-2">
      <ul className="divide-y divide-slate-100 text-sm">
        {stages.map((stage) => {
          const ids = stage.users.map((u) => u.id);
          const available = team.filter((m) => !ids.includes(m.id));
          return (
            <li key={stage.stage_key} className="flex flex-wrap items-center gap-2 py-2 first:pt-0 last:pb-0">
              <span className="w-44 shrink-0 text-slate-700">{stage.stage_name}</span>
              {stage.users.length === 0 && !editable ? (
                <span className="text-xs text-slate-400">Nobody</span>
              ) : null}
              {stage.users.map((u) => (
                <span
                  key={u.id}
                  className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700"
                >
                  {u.name}
                  {editable ? (
                    <button
                      type="button"
                      aria-label={`Remove ${u.name} from ${stage.stage_name}`}
                      disabled={busy !== null}
                      onClick={() => save(stage.stage_key, ids.filter((id) => id !== u.id))}
                      className="text-slate-400 hover:text-rose-600"
                    >
                      <X className="h-3 w-3" aria-hidden />
                    </button>
                  ) : null}
                </span>
              ))}
              {editable && available.length > 0 ? (
                <select
                  aria-label={`Add a default interviewer for ${stage.stage_name}`}
                  value=""
                  disabled={busy !== null}
                  onChange={(e) => {
                    if (e.target.value) void save(stage.stage_key, [...ids, e.target.value]);
                  }}
                  className="h-7 rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-600"
                >
                  <option value="">Add someone</option>
                  {available.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              ) : null}
              {busy === stage.stage_key ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" aria-hidden />
              ) : null}
            </li>
          );
        })}
      </ul>
      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 2: Job detail page**

In `web/src/app/jobs/[id]/page.tsx`:

Replace `import { canWrite } from "@/lib/session";` with

```tsx
import { DefaultInterviewersEditor } from "@/components/default-interviewers-editor";
import { memberName } from "@/lib/interviews";
import { DELETE_RECORDS, JOBS_WRITE, SCORE_BEFORE_FEEDBACK, can } from "@/lib/permissions";
import { getUser } from "@/lib/session";
```

and add `getDefaultInterviewers` and `listTeam` to the `@/lib/data` import.

Replace

```tsx
  const [job, writable] = await Promise.all([getJob(id), canWrite()]);
  if (!job) notFound();
```

with

```tsx
  const [job, user] = await Promise.all([getJob(id), getUser()]);
  if (!job) notFound();
  const role = user?.role;
  const writable = can(role, JOBS_WRITE);
  const deletable = can(role, DELETE_RECORDS);
  // Interviewers see match scores only per candidate, after their feedback.
  const seesScores = can(role, SCORE_BEFORE_FEEDBACK);
```

Replace `{writable ? <DeleteJobButton jobId={job.id} title={job.title} variant="full" /> : null}` with

```tsx
          {deletable ? <DeleteJobButton jobId={job.id} title={job.title} variant="full" /> : null}
```

Wrap the Matching card and add the default-interviewers card: replace

```tsx
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Matching candidates</CardTitle>
            </CardHeader>
```

with

```tsx
          {seesScores ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Matching candidates</CardTitle>
            </CardHeader>
```

and replace the end of that card plus the column boundary

```tsx
          </Card>
        </div>

        <div className="space-y-6">
```

with

```tsx
          </Card>
          ) : null}

          {role !== "interviewer" ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Default interviewers</CardTitle>
                <p className="text-xs text-slate-500">
                  Assigned automatically when a candidate reaches the stage.
                </p>
              </CardHeader>
              <CardContent>
                <Suspense fallback={<Skeleton className="h-24 w-full rounded-lg" />}>
                  <DefaultInterviewers jobId={job.id} editable={writable} />
                </Suspense>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div className="space-y-6">
```

Add next to `Board`:

```tsx
async function DefaultInterviewers({ jobId, editable }: { jobId: number; editable: boolean }) {
  const [stages, team] = await Promise.all([
    getDefaultInterviewers(jobId).catch(() => null),
    editable ? listTeam().catch(() => []) : Promise.resolve([]),
  ]);
  if (!stages) {
    return <p className="text-sm text-slate-500">Default interviewers could not be loaded.</p>;
  }
  return (
    <DefaultInterviewersEditor
      jobId={jobId}
      stages={stages}
      team={team.map((m) => ({ id: m.id, name: memberName(m) }))}
      editable={editable}
    />
  );
}
```

- [ ] **Step 3: Jobs list, new, and edit**

In `web/src/app/jobs/page.tsx`, replace `import { canWrite } from "@/lib/session";` with

```tsx
import { DELETE_RECORDS, JOBS_WRITE, can } from "@/lib/permissions";
import { getUser } from "@/lib/session";
```

replace `  const writable = await canWrite();` with

```tsx
  const user = await getUser();
  const writable = can(user?.role, JOBS_WRITE);
  const deletable = can(user?.role, DELETE_RECORDS);
```

and replace the card footer

```tsx
                {writable ? (
                  <div className="flex items-center gap-2 border-t border-slate-100 pt-3">
                    <Link
                      href={`/jobs/${job.id}/edit`}
                      className={buttonVariants({ variant: "outline", size: "sm" })}
                    >
                      <Pencil className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                      Edit
                    </Link>
                    <DeleteJobButton jobId={job.id} title={job.title} />
                  </div>
                ) : null}
```

with

```tsx
                {writable || deletable ? (
                  <div className="flex items-center gap-2 border-t border-slate-100 pt-3">
                    {writable ? (
                      <Link
                        href={`/jobs/${job.id}/edit`}
                        className={buttonVariants({ variant: "outline", size: "sm" })}
                      >
                        <Pencil className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                        Edit
                      </Link>
                    ) : null}
                    {deletable ? <DeleteJobButton jobId={job.id} title={job.title} /> : null}
                  </div>
                ) : null}
```

In `web/src/app/jobs/new/page.tsx`, replace `import { canWrite } from "@/lib/session";` with

```tsx
import { JOBS_WRITE } from "@/lib/permissions";
import { hasPermission } from "@/lib/session";
```

and `if (!(await canWrite())) redirect("/jobs");` with `if (!(await hasPermission(JOBS_WRITE))) redirect("/jobs");`.

In `web/src/app/jobs/[id]/edit/page.tsx`, make the same import change and replace ``if (!(await canWrite())) redirect(`/jobs/${id}`);`` with ``if (!(await hasPermission(JOBS_WRITE))) redirect(`/jobs/${id}`);``.

- [ ] **Step 4: Guards for screens interviewers cannot use**

- `web/src/app/page.tsx`: add `import { redirectInterviewer } from "@/lib/guards";` and make `await redirectInterviewer();` the first line of `DashboardPage`.
- `web/src/app/matching/page.tsx`: same import; `await redirectInterviewer();` as the first line of `MatchingPage`.
- `web/src/app/assistant/page.tsx`: same import; change `export default function AssistantPage()` to `export default async function AssistantPage()` and make `await redirectInterviewer();` its first line.
- `web/src/app/upload/page.tsx`: replace `import { canWrite } from "@/lib/session";` with

  ```tsx
  import { redirectInterviewer } from "@/lib/guards";
  import { CANDIDATES_ADD } from "@/lib/permissions";
  import { hasPermission } from "@/lib/session";
  ```

  and `  const writable = await canWrite();` with

  ```tsx
    await redirectInterviewer();
    const writable = await hasPermission(CANDIDATES_ADD);
  ```

- [ ] **Step 5: Transparency: traces for score readers, a feedback card for everyone**

In `web/src/app/transparency/page.tsx`, add

```tsx
import { SCORE_BEFORE_FEEDBACK } from "@/lib/permissions";
import { hasPermission } from "@/lib/session";
```

add after `const selected = ...`:

```tsx
  // Interviewers may not see scores before their own feedback, so the trace
  // tools (which are all scores) are not drawn for them; the API refuses
  // them too.
  const showTraces = await hasPermission(SCORE_BEFORE_FEEDBACK);
```

replace `        <HowAScoreIsBuilt policy={policy} />` with

```tsx
        <HowAScoreIsBuilt policy={policy} />
        <FeedbackUse policy={policy} />

        {showTraces ? (
        <>
```

and replace

```tsx
        </Card>

        <UploadPrivacy policy={uploadPolicy} />
```

with

```tsx
        </Card>
        </>
        ) : null}

        <UploadPrivacy policy={uploadPolicy} />
```

(the first `</Card>` followed by a blank line and `<UploadPrivacy` is the end of the "Trace a search" card, so the two trace cards are now inside the fragment). Add the component next to `Inputs`:

```tsx
// --- what interview feedback is for -----------------------------------------

function FeedbackUse({ policy }: { policy: ScoringPolicy }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>What interview feedback is and is not used for</CardTitle>
        <p className="text-xs text-slate-500">
          A test reads every scoring module and fails if one of them mentions feedback.
        </p>
      </CardHeader>
      <CardContent className="grid gap-6 text-sm lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">Used for</h3>
          <ul className="space-y-1.5 text-slate-700">
            {policy.feedback_policy.used_for.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">Never used for</h3>
          <ul className="space-y-1.5 text-slate-700">
            {policy.feedback_policy.never_used_for.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: E2E for the new screens**

Create `web/e2e/team-screens.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

/**
 * The three ATS Phase B screens render for the auto-signed-in demo user
 * (spec section 10: the demo must keep working on every screen).
 */
for (const [path, heading] of [
  ["/interviews", "Interviews"],
  ["/team", "Team"],
  ["/settings", "Settings"],
] as const) {
  test(`${path} renders for the demo account`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await expect(page.getByText(/^Could not load/)).toHaveCount(0);
  });
}

test("the demo never sees a team member's email", async ({ page }) => {
  await page.goto("/team");
  await expect(page.getByRole("heading", { name: "Team", level: 1 })).toBeVisible();
  await expect(page.locator("main")).not.toContainText("@");
});
```

- [ ] **Step 7: Run the checks**

Run: `cd web; npm run typecheck; npm run lint; npm test; npm run build`
Expected: clean.

- [ ] **Step 8: Commit**

Write `$S\commit-b17.txt`:

```
feat(web): role-aware job pages, guards, and the feedback card

Job pages draw Edit for jobs.write and Delete for records.delete instead
of one admin flag, add a Default interviewers card (editable by those
who can edit the job), and leave out Matching for interviewers. Dashboard,
Matching, Upload, Assistant, and Team send interviewers to Interviews.
Transparency gains a card on what feedback is and is not used for, and
draws the trace tools only for roles that may see scores.
```

```powershell
git add web/src/components/default-interviewers-editor.tsx web/src/app/jobs "web/src/app/jobs/[id]/page.tsx" web/src/app/page.tsx web/src/app/matching/page.tsx web/src/app/upload/page.tsx web/src/app/assistant/page.tsx web/src/app/transparency/page.tsx web/e2e/team-screens.spec.ts
git commit -F "$S\commit-b17.txt"
```

---

### Task 18: Full verification, live checks, PR, deploy

**Files:** `CLAUDE.md` (one line), nothing else new.

- [ ] **Step 1: Backend, the way CI does it**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
$env:OLLAMA_BASE_URL = "http://localhost:1"
poetry run ruff check backend --select E9,F63,F7,F82 --exclude backend/tests
poetry run python scripts/export_openapi.py --check
poetry run python scripts/export_permissions.py --check
poetry run pytest -q
```

Run the suite in the background (about 11 minutes on dev) and continue with Step 2. Expected: ruff clean, both `--check`s pass, suite green except the two known embedding tests under the unreachable-Ollama env.

- [ ] **Step 2: Scratch-database pass (schema changed)**

```powershell
$dev = $env:POSTGRES_CONN
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $dev -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
poetry run pytest -q
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
$env:POSTGRES_CONN = $dev
```

Expected: same result as Step 1 on a database built from migrations alone (no seed, like CI).

- [ ] **Step 3: Web**

```powershell
cd web; npm run typecheck; npm run lint; npm test; npm run build; cd ..
```

- [ ] **Step 4: Live checks as three roles**

Start the servers (`cd backend; poetry run python -m uvicorn main:app --port 8010` and `cd web; npm run dev`). Give two seeded people a local password (dev database only; the password comes from the environment, never the command line):

```powershell
$env:ADMIN_PASSWORD = "<a local password of 12+ characters>"
poetry run python scripts/create_admin.py --email marcus.webb@team.recruitiq.dev --role interviewer
poetry run python scripts/create_admin.py --email priya.raman@team.recruitiq.dev --role hiring_manager
Remove-Item Env:ADMIN_PASSWORD
```

Then, in the browser:

1. **Demo** (a fresh private window): the sidebar shows ten items; `/interviews` shows "All" with seeded rows; `/team` shows six people with roles and no email addresses; `/settings` shows the demo sentence; a candidate page shows interviews and feedback; Transparency shows the new feedback card and both trace tools.
2. **Interviewer** (`/login` as Marcus Webb): lands on `/interviews`; the sidebar shows Jobs, Candidates, Interviews, Transparency, Settings; Candidates lists only his candidates; opening `/candidates/<another id>` shows the not-found page; on one of his candidates with "Waiting for feedback", Recommended roles shows "Submit your feedback on this candidate to see their match scores."; submit feedback; the panel shows it and Recommended roles fills in on refresh; `/matching` redirects to `/interviews`.
3. **Hiring manager** (`/login` as Priya Raman): the job page shows Edit but not Delete, and the Default interviewers card is editable; add someone on the Team page and see the temporary password once; Settings saves a time zone; on a candidate page, Assign puts an interviewer on the current stage.

If anything on a page renders an error state, check the uvicorn log first, then fix and repeat.

Then run e2e against the dev servers:

```powershell
cd web; $env:E2E_BASE_URL = "http://localhost:3000"; npx playwright test; cd ..
```

Expected: pass. If it fails, re-run against `https://recruitiq.io` (pre-deploy: only the old specs apply) and restart `next dev` before blaming the change (a rotted `next dev` fakes failures).

Finally, take the local passwords back off the seeded people so the dev database matches prod's "no seeded logins" state:

```powershell
docker exec recruitiq-db psql -U admin -d ats_db -c "UPDATE users SET hashed_password = NULL WHERE email LIKE '%@team.recruitiq.dev'"
```

- [ ] **Step 5: Document the new create_admin flag**

In `CLAUDE.md`, replace

```
- One-off admin: `scripts/create_admin.py` (reads `ADMIN_PASSWORD` env);
```

with

```
- One-off admin: `scripts/create_admin.py` (reads `ADMIN_PASSWORD` env;
  `--role` sets up any staff role, e.g. a seeded interviewer);
```

Write `$S\commit-b18.txt`:

```
docs: create_admin.py takes a role

One line in CLAUDE.md so the next session knows a seeded team member
gets a password the same way an admin does.
```

```powershell
git add CLAUDE.md
git commit -F "$S\commit-b18.txt"
```

- [ ] **Step 6: Push and open the PR**

Write `$S\pr-b.md`:

```
## What

ATS Phase B: four staff roles (Admin, Hiring manager, Hiring team, Interviewer) with the spec's permission matrix, interviewers assigned per stage by hand or by default, a feedback form (1 to 5, recommendation, notes), interviewers confined to the candidates they interview and kept from the AI score until they give feedback, Team / Settings / Interviews pages, and a grouped sidebar. Spec: docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md section 8 Phase B; plan: docs/superpowers/plans/2026-10-03-ats-phase-b-team-feedback.md.

## Decisions worth a look

- Roles are read from the database on every request, so a demotion or removal takes effect immediately.
- Interviewers are default-deny for reads as well as writes (allowlist plus a route walk), rather than per-route patches across the legacy API. They do not get the assistant, Matching, Upload, or the trace tools in this phase.
- Colleagues' feedback follows the score rule: hidden from an interviewer until they submit their own.
- Feedback is final once submitted; removing a person who has given feedback is refused.
- The demo sees the team's names and roles but never an email address.
- Anonymous and demo reads are unchanged. Closing anonymous reads for a private deployment is a separate setting, not in this PR.

## Verified

- backend: test_permissions (matrix cell by cell), test_feedback, test_team, test_team_access (interviewer route walk over every read route), the extended test_auth staff walk, the golden contract (additions only), and the full suite on the dev database and on a scratch database built from migrations alone
- migration: upgrade, downgrade, upgrade on a scratch database
- seed: two full runs and a --team-only run give byte-identical interview history
- web: typecheck, lint, vitest, build, Playwright (header layout at seven widths, demo journey, the three new screens)
- live: demo, interviewer, and hiring manager walked through on the dev servers

## Prod follow-up

`scripts/seed_demo.py --team-only` adds the synthetic team and interview history so the demo's Interviews and Team pages are not empty. It is additive and never touches candidates or applications. Seeded people have no passwords on prod.
```

```powershell
git push -u origin ats-team-feedback
gh pr create --base main --title "feat: team roles, interviews, and feedback (ATS Phase B)" --body-file "$S\pr-b.md"
gh pr checks --watch
```

- [ ] **Step 7: Merge and deploy**

```powershell
gh pr merge --merge --delete-branch
git fetch origin
```

Deploy with the Bash tool:

```bash
ssh root@157.245.233.229 "free -h"
ssh root@157.245.233.229 "pgrep -fa '[d]eploy.sh' || echo none"
ssh root@157.245.233.229 "/opt/recruitiq/app/scripts/deploy.sh"
```

Expected: at least 500M available; no deploy running; `==> deployed <sha>` matching `git rev-parse --short origin/main`. The deploy runs `alembic upgrade head` (d5f9b2c3e4a5).

Then the non-destructive prod follow-up:

```bash
ssh root@157.245.233.229 "sudo -u recruitiq bash -c 'set -a; . /etc/recruitiq/env; set +a; cd /opt/recruitiq/app && .venv/bin/python scripts/seed_demo.py --team-only'"
```

Expected: a `team: 6  interviews: N  feedback: M` line with N and M above zero.

- [ ] **Step 8: Smoke test prod**

```bash
curl -sS -o /dev/null -w "home %{http_code}\n" https://recruitiq.io/
ssh root@157.245.233.229 'curl -sS http://127.0.0.1:8020/health; echo
TOKEN=$(curl -s -X POST http://127.0.0.1:8020/auth/demo | grep -o "\"access_token\":\"[^\"]*\"" | cut -d\" -f4)
echo "team (expect no @):"; curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8020/api/team/users | grep -c "@" || true
echo "interviews:"; curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8020/api/interviews?scope=pending" | head -c 300; echo
echo "policy:"; curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8020/api/transparency/policy | grep -o "\"feedback_policy\"" ; echo
J=$(curl -s "http://127.0.0.1:8020/api/jobs/?page_size=1" | grep -o "\"id\":[0-9]*" | head -1 | cut -d: -f2); echo "job=$J"
curl -s -o /dev/null -w "advance as demo: %{http_code}\n" -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{}" http://127.0.0.1:8020/api/applications/1/advance'
for p in /interviews /team /settings; do curl -sS -o /dev/null -w "$p %{http_code}\n" "https://recruitiq.io$p"; done
```

Expected: home 200; health ok; the team body contains `0` occurrences of `@`; a pending-interviews JSON body starting with `{"items":[`; `"feedback_policy"` printed; a real job id printed; the demo advance is 403; `/interviews`, `/team`, `/settings` are 200.

---

## Self-review

**Spec coverage (section 8, Phase B scope):**
- Four roles and `name` on users: Task 1 (column), Task 2 (constants and matrix), Task 7 (`UserResponse.name`, Role literal). Covered.
- Invite flow with a temporary password, no email: Task 7 backend, Task 15 UI. Covered.
- Permission matrix in `enforce_read_only` and per-route checks: Tasks 2 and 3 (`ROUTE_PERMISSIONS`, default deny, `require`), every new route uses `require`. Covered, cell by cell in `test_permissions.py`.
- `interviews` and `feedback` tables, stage default interviewers: Task 1 (schema), Task 4 (service, hook), Task 5 (routes). Covered.
- Assign on the candidate page, Interviews page, feedback form: Task 16. Covered.
- Score hiding for interviewers: Task 4 (`can_see_score`), Task 6 (match-jobs 403, assistant and traces closed to the role), Task 16 (message instead of an empty panel), Task 17 (no Matching card, no trace tools). Covered.
- Team and Settings pages: Task 15. Covered.
- Sidebar navigation: Task 13. Covered.
- Assistant tool for pending feedback: Task 9. Covered.
- Transparency "what feedback is and is not used for": Task 8 (policy plus source test), Task 17 (card). Covered.
- `jobs.hiring_manager_id` / `recruiter_id` (spec 3.2): Task 1 and Task 8; the job form picker is deferred to Phase E's job-form work (decision 12).

**Acceptance:**
- "An interviewer account can see only the candidates they are assigned to": the default-deny gate, the list and board filters, the id checks, and the route walk in Task 6.
- "Cannot see a score until their feedback exists": `test_score_is_hidden_until_feedback` (Task 6) and the live check in Task 18.
- "The transparency page states that feedback never reaches the scorer": Task 8 policy, Task 17 card, and `test_scoring_code_never_reads_feedback`.
- Demo keeps every screen: `ROLE_DEMO` read permissions (decision 6), demo assertions in `test_interview_lists`, `test_list_excludes_the_demo_account...`, and `e2e/team-screens.spec.ts`.

**Placeholder scan:** no "TBD", "TODO", "similar to Task N", or "add validation" steps. Every code step shows the code. The one manual edit without a full code block (Task 14 Step 4, four sign-in strings) names each exact old and new string.

**Type and name consistency:** `ROUTE_PERMISSIONS` rows (Task 2) match the routes defined in Tasks 5 and 7 (`/api/applications/{id}/interviews`, `/api/interviews/{id}`, `/api/interviews/{id}/feedback`, `/api/jobs/{id}/stages/{key}/default-interviewers`, `/api/team/users`, `/api/team/users/{id}/role`, `/api/team/users/{id}`, `/api/team/me`, `/api/team/me/password`). `INTERVIEWER_PATHS` (Task 6) covers every path the interviewer's screens fetch in Tasks 15 to 17 (`/auth/me`, `/api/team/me`, `/api/interviews`, `/api/jobs`, `/api/jobs/{id}`, `/api/jobs/{id}/pipeline`, `/api/candidates`, `/api/candidates/{id}`, `/api/candidates/{id}/resumes`, `/api/jobs/applications/{id}`, `/api/jobs/saved/{id}`, `/api/applications/{id}`, `/api/applications/{id}/interviews`, `/api/resume/{id}`, `/api/enhanced-matching/match-jobs`, `/api/transparency/policy` and `/upload-policy`); the job page does not call `/api/jobs/{id}/default-interviewers` for interviewers. `InterviewOut` fields used in `interview-panel.tsx` (`state`, `stage_name`, `interviewer_name`, `feedback`, `feedback_hidden`, `interviewer_id`) match `backend/models/feedback.py`. `TeamMember.email` is optional on both sides. The permission strings in `web/src/lib/permissions.ts` are pinned against the generated JSON by `permissions.test.ts`, and the JSON against the backend by `test_permissions_json_is_current`.

**Contract notes for Phases C to E (beyond ats-contract.md):**
- One extra permission exists: `profile.edit` (all four staff roles). The demo holds `score.before_feedback` and `reports.view` so read-only screens work for it; Phase D can gate Reports on `reports.view` and the demo will still see it.
- `NavItem.hiddenFor?: Role[]` exists; Phase D's Reports item should set `hiddenFor: ["interviewer"]`.
- An interviewer can reach only `INTERVIEWER_PATHS`. A later phase that wants interviewers on a new read route must add it there (with a `kind` if it names a candidate, application, or resume) and extend `test_team_access.py`; otherwise the route walk keeps it closed.
- `request_user(request)` (access_service) is how a handler gets the acting staff user without another lookup; it is None for anonymous and demo callers.
- `feedback_service.display_name` never falls back to an email; any screen the demo can see should use it (or `memberName` on the web) for people.
- The feedback router is mounted before the pipeline router; any new `/applications/{id}/<word>` route must also be mounted before `pipeline.router`, or the `{action}` route swallows it.
