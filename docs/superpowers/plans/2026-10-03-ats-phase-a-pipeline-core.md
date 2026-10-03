# ATS Phase A: Pipeline Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every job an 11-stage pipeline and every application a stage history, with Advance, Skip, Reject, and Decline actions on the candidate page and a board on the job page.

**Architecture:** Two new tables (`pipeline_stages` per job, `application_stages` per application) and one service module (`backend/services/pipeline_service.py`) that owns every transition and keeps `candidates.status` in sync. A new FastAPI router exposes the board and the four actions. The Next.js job and candidate pages render Server Components fed by `lib/data.ts`; a small client component posts actions through a Next route handler and refreshes.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic (backend), Next.js 16 App Router + Tailwind + Vitest (web), pytest with the existing transactional fixtures in `backend/tests/conftest.py`.

**Spec:** `docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md` (sections 3, 4, and 8 Phase A).

---

## Conventions for every task

- Work on branch `ats-pipeline-core`, created from `origin/main`.
- Backend tests run from the repo root with the dev database:
  ```powershell
  $env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
  $env:OLLAMA_BASE_URL = "http://localhost:1"
  poetry run pytest backend/tests/test_pipeline.py -q
  ```
- Web tests run from `web/`: `npm test`, `npm run typecheck`, `npm run lint`.
- Commit with `git commit -F <file>` (never `-m` with a here-string). No attribution trailers.
- No em dashes in any string a user can read.
- New endpoints are plain `def`, not `async def`.

## File structure

| File | Responsibility |
|---|---|
| `backend/alembic/versions/c4e8a1b2d3f4_pipeline_stages.py` | Create: both tables, status vocabulary migration, backfill for existing jobs and applications |
| `backend/models/models.py` | Modify: add `PipelineStage`, `ApplicationStage`, relationships on `Job` and `JobApplication` |
| `backend/services/pipeline_service.py` | Create: `DEFAULT_STAGES`, ensure functions, the four transitions, candidate status sync |
| `backend/models/pipeline.py` | Create: Pydantic response and request models |
| `backend/routers/pipeline.py` | Create: `GET/PUT /api/jobs/{id}/pipeline`, `GET /api/applications/{id}`, `POST /api/applications/{id}/{action}` |
| `backend/main.py` | Modify: mount the router |
| `backend/routers/jobs.py` | Modify: `create_job` seeds stages, `apply_to_job` starts the application, `CandidateApplicationSummary` gains stage fields |
| `backend/tests/test_pipeline.py` | Create: service and route tests |
| `backend/tests/conftest.py` | Modify: seeded application status `reviewing` becomes `active` |
| `scripts/seed_demo.py` | Modify: `seed_pipeline` builds stage history from each candidate's status |
| `openapi.json`, `web/src/lib/schema.d.ts` | Regenerated |
| `web/src/lib/domain.ts` | Modify: type aliases for the new schemas |
| `web/src/lib/data.ts` | Modify: `getJobPipeline`, `getApplication` |
| `web/src/lib/pipeline.ts` + `pipeline.test.ts` | Create: pure helpers (labels, which actions apply) |
| `web/src/app/api/applications/[id]/[action]/route.ts` | Create: proxy for the four actions |
| `web/src/components/pipeline-board.tsx` | Create: columns on the job page |
| `web/src/components/application-timeline.tsx` | Create: stage list on the candidate page |
| `web/src/components/stage-actions.tsx` | Create: client buttons |
| `web/src/app/jobs/[id]/page.tsx` | Modify: add the board |
| `web/src/app/candidates/[id]/page.tsx` | Modify: replace Applications card |

---

### Task 1: Branch and ORM models

**Files:**
- Modify: `backend/models/models.py` (after the `JobApplication` class, and relationships on `Job` and `JobApplication`)
- Test: `backend/tests/test_pipeline.py` (new)

- [ ] **Step 1: Create the branch**

```powershell
git fetch origin
git switch -c ats-pipeline-core origin/main
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_pipeline.py`:

```python
"""Pipeline stages and application stage history (ATS Phase A).

Runs against the real schema inside the session-wide rolled-back transaction
from conftest. The seeded application (candidate 0 on job 0) has no stage rows
until something asks for them, which is exactly the state existing production
rows are in, so these tests also cover the lazy-repair path.
"""
from __future__ import annotations

import pytest

from backend.models.models import ApplicationStage, JobApplication, PipelineStage


def test_models_import_and_map():
    assert PipelineStage.__tablename__ == "pipeline_stages"
    assert ApplicationStage.__tablename__ == "application_stages"
    assert "stages" in JobApplication.__mapper__.relationships
```

- [ ] **Step 3: Run it to verify it fails**

Run: `poetry run pytest backend/tests/test_pipeline.py::test_models_import_and_map -q`
Expected: FAIL with `ImportError: cannot import name 'ApplicationStage'`

- [ ] **Step 4: Add the models**

In `backend/models/models.py`, add `Boolean` to the sqlalchemy import line:

```python
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Table, UniqueConstraint, event, Float, Index, Boolean
```

Add to the `Job` class relationships block (after `pitches = ...`):

```python
    pipeline_stages = relationship(
        "PipelineStage",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="PipelineStage.position",
    )
```

Add to the `JobApplication` class relationships block (after `candidate = ...`):

```python
    stages = relationship(
        "ApplicationStage",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationStage.id",
    )
```

Append after the `SavedJob` class:

```python
# ====================================================================
# Pipeline (ATS Phase A, spec 2026-10-03 section 3)
# ====================================================================


class PipelineStage(Base):
    """One stage of one job's pipeline.

    Copied from `pipeline_service.DEFAULT_STAGES` when a job is created or the
    first time its pipeline is read. `kind` is `round` (something the candidate
    goes through) or `outcome` (where they end up). Disabled rounds are skipped
    by every transition.
    """
    __tablename__ = "pipeline_stages"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    kind = Column(String(20), nullable=False, default="round")
    position = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("job_id", "key", name="uq_pipeline_stage_job_key"),)

    job = relationship("Job", back_populates="pipeline_stages")

    def __repr__(self):
        return f"<PipelineStage(job_id={self.job_id}, key='{self.key}', enabled={self.enabled})>"


class ApplicationStage(Base):
    """Where one application stands at one stage. Together these rows are the history."""
    __tablename__ = "application_stages"

    id = Column(Integer, primary_key=True)
    application_id = Column(
        Integer, ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id = Column(
        Integer, ForeignKey("pipeline_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    changed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("application_id", "stage_id", name="uq_application_stage"),
    )

    application = relationship("JobApplication", back_populates="stages")
    stage = relationship("PipelineStage")

    def __repr__(self):
        return f"<ApplicationStage(application_id={self.application_id}, stage_id={self.stage_id}, status='{self.status}')>"
```

- [ ] **Step 5: Run the test**

Run: `poetry run pytest backend/tests/test_pipeline.py::test_models_import_and_map -q`
Expected: PASS

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a1.txt`:

```
feat: add pipeline stage and application stage models

Phase A of the ATS workflow blueprint. The tables do not exist yet (next
commit adds the migration); this only registers the ORM classes and the
relationships so the service can be written against them.
```

```powershell
git add backend/models/models.py backend/tests/test_pipeline.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a1.txt
```

---

### Task 2: Migration with backfill

**Files:**
- Create: `backend/alembic/versions/c4e8a1b2d3f4_pipeline_stages.py`

- [ ] **Step 1: Write the migration**

```python
"""pipeline_stages and application_stages, with backfill

ATS Phase A (spec 2026-10-03 section 3). Creates the two tables, moves
job_applications.status to the new vocabulary (active, hired, rejected,
declined, withdrawn), then backfills: every existing job gets the 11 default
stages, and every existing application gets one row per stage positioned
from the candidate's current status, so the board is populated the moment
the code deploys and no reseed is needed on the droplet.

The stage list is duplicated here on purpose rather than imported from
pipeline_service: a migration must describe the schema as of its own
revision, not as of whatever the code says later.

Revision ID: c4e8a1b2d3f4
Revises: b7d2e9a41c53
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a1b2d3f4"
down_revision: Union[str, None] = "b7d2e9a41c53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (key, name, kind, description)
DEFAULT_STAGES = [
    ("resume_submitted", "Resume submitted", "round", "We have your resume and are reviewing it."),
    ("hm_review", "Hiring manager review", "round", "The hiring manager reviews your background against the role."),
    ("technical_written", "Technical assessment", "round", "A take-home or written exercise on the fundamentals of the role."),
    ("technical_interview", "Technical interview", "round", "A live conversation going deep on your primary area."),
    ("problem_solving", "Problem solving", "round", "An open-ended reasoning session with the team."),
    ("case_study", "Case study", "round", "A scenario-based discussion with a small panel."),
    ("hr_screen", "HR screen", "round", "A final conversation about logistics, timing, and references."),
    ("offer", "Offer", "round", "An offer has been extended."),
    ("offer_accepted", "Offer accepted", "round", "You have accepted. We are completing paperwork and a start date."),
    ("offer_declined", "Offer declined", "outcome", "You declined the offer."),
    ("hired", "Hired", "outcome", "Welcome aboard."),
]

# candidate.status -> (index of the in-progress round, application status)
# Indexes are 0-based into DEFAULT_STAGES. None means no round is in progress
# because the application is terminal.
STATUS_SNAPSHOT = {
    "active": (0, "active"),
    "screening": (1, "active"),
    "interviewing": (3, "active"),
    "offered": (7, "active"),
    "on_hold": (1, "active"),
    "hired": (None, "hired"),
    "rejected": (None, "rejected"),
    "withdrawn": (None, "withdrawn"),
}


def upgrade() -> None:
    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="round"),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("job_id", "key", name="uq_pipeline_stage_job_key"),
    )
    op.create_index("ix_pipeline_stages_job_id", "pipeline_stages", ["job_id"])

    op.create_table(
        "application_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("job_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_stages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("changed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("application_id", "stage_id", name="uq_application_stage"),
    )
    op.create_index("ix_application_stages_application_id", "application_stages", ["application_id"])
    op.create_index("ix_application_stages_stage_id", "application_stages", ["stage_id"])

    # Old vocabulary: submitted, reviewing, interviewing, accepted, rejected.
    op.execute("UPDATE job_applications SET status = 'hired' WHERE status = 'accepted'")
    op.execute(
        "UPDATE job_applications SET status = 'active' "
        "WHERE status NOT IN ('hired', 'rejected', 'declined', 'withdrawn')"
    )

    bind = op.get_bind()

    # Every existing job gets the default stages.
    for job_id, in bind.execute(sa.text("SELECT id FROM jobs")).fetchall():
        for position, (key, name, kind, description) in enumerate(DEFAULT_STAGES, start=1):
            bind.execute(
                sa.text(
                    "INSERT INTO pipeline_stages (job_id, key, name, description, kind, position, enabled) "
                    "VALUES (:job_id, :key, :name, :description, :kind, :position, true)"
                ),
                {
                    "job_id": job_id,
                    "key": key,
                    "name": name,
                    "description": description,
                    "kind": kind,
                    "position": position,
                },
            )

    # Every existing application gets a row per stage, positioned from the
    # candidate's status (the only funnel signal the old schema had).
    rows = bind.execute(
        sa.text(
            "SELECT a.id, a.job_id, a.status, a.applied_at, c.status AS candidate_status "
            "FROM job_applications a JOIN candidates c ON c.id = a.candidate_id"
        )
    ).fetchall()
    for app_id, job_id, app_status, applied_at, candidate_status in rows:
        stage_ids = bind.execute(
            sa.text(
                "SELECT id, key FROM pipeline_stages WHERE job_id = :job_id ORDER BY position"
            ),
            {"job_id": job_id},
        ).fetchall()
        current_index, derived_status = STATUS_SNAPSHOT.get(candidate_status or "active", (0, "active"))
        if app_status in ("hired", "rejected", "declined", "withdrawn"):
            derived_status = app_status
            current_index = None
        for index, (stage_id, key) in enumerate(stage_ids):
            if derived_status == "hired":
                status = "passed" if key != "offer_declined" else "skipped"
            elif derived_status in ("rejected", "withdrawn", "declined"):
                if index == 0:
                    status = "passed"
                elif index == 1:
                    status = "failed" if derived_status == "rejected" else "skipped"
                else:
                    status = "skipped"
            elif current_index is None or index < current_index:
                status = "passed"
            elif index == current_index:
                status = "in_progress"
            else:
                status = "pending"
            bind.execute(
                sa.text(
                    "INSERT INTO application_stages (application_id, stage_id, status, started_at, completed_at) "
                    "VALUES (:application_id, :stage_id, :status, :started_at, :completed_at)"
                ),
                {
                    "application_id": app_id,
                    "stage_id": stage_id,
                    "status": status,
                    "started_at": applied_at if status != "pending" else None,
                    "completed_at": applied_at if status in ("passed", "failed", "skipped") else None,
                },
            )
        bind.execute(
            sa.text("UPDATE job_applications SET status = :status WHERE id = :id"),
            {"status": derived_status, "id": app_id},
        )


def downgrade() -> None:
    op.drop_index("ix_application_stages_stage_id", table_name="application_stages")
    op.drop_index("ix_application_stages_application_id", table_name="application_stages")
    op.drop_table("application_stages")
    op.drop_index("ix_pipeline_stages_job_id", table_name="pipeline_stages")
    op.drop_table("pipeline_stages")
    op.execute("UPDATE job_applications SET status = 'accepted' WHERE status = 'hired'")
    op.execute(
        "UPDATE job_applications SET status = 'submitted' "
        "WHERE status IN ('active', 'declined', 'withdrawn')"
    )
```

- [ ] **Step 2: Verify on a scratch database**

```powershell
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
docker exec recruitiq-db psql -U admin -d st_scratch -c "\d pipeline_stages" -c "\d application_stages"
cd backend; poetry run alembic downgrade -1; poetry run alembic upgrade head; cd ..
```

Expected: both tables listed with the columns above; downgrade and re-upgrade both succeed.

- [ ] **Step 3: Verify the backfill on the dev database**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
cd backend; poetry run alembic upgrade head; cd ..
docker exec recruitiq-db psql -U admin -d ats_db -c "SELECT COUNT(*) FROM pipeline_stages" -c "SELECT status, COUNT(*) FROM application_stages GROUP BY status" -c "SELECT status, COUNT(*) FROM job_applications GROUP BY status"
```

Expected: `pipeline_stages` count is 11 times the job count; `application_stages` has rows in `passed`, `in_progress`, `pending`, `skipped`; `job_applications.status` contains only `active`, `hired`, `rejected`, `withdrawn`.

- [ ] **Step 4: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a2.txt`:

```
feat: migration for pipeline stages with backfill of existing rows

Creates pipeline_stages and application_stages, moves application status to
the active/hired/rejected/declined/withdrawn vocabulary, and positions every
existing application from its candidate's status. Verified: upgrade,
downgrade, and upgrade again on a scratch database; backfill counts checked
on the dev database.
```

```powershell
git add backend/alembic/versions/c4e8a1b2d3f4_pipeline_stages.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a2.txt
```

---

### Task 3: Pipeline service, ensure functions

**Files:**
- Create: `backend/services/pipeline_service.py`
- Modify: `backend/tests/conftest.py:181` (`status="reviewing"` becomes `status="active"`)
- Test: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Update the conftest seed**

In `backend/tests/conftest.py`, in the `JobApplication(...)` inside `seed`, change `status="reviewing",` to `status="active",`.

- [ ] **Step 2: Write the failing tests**

Append to `backend/tests/test_pipeline.py`:

```python
from backend.services import pipeline_service as ps


@pytest.fixture
def application(db_session, seed) -> JobApplication:
    return db_session.get(JobApplication, seed["application_id"])


def test_ensure_job_stages_creates_the_eleven_defaults(db_session, seed):
    stages = ps.ensure_job_stages(db_session, seed["job_ids"][1])
    assert [s.key for s in stages] == [key for key, *_ in ps.DEFAULT_STAGES]
    assert [s.kind for s in stages][-2:] == ["outcome", "outcome"]
    # Idempotent: a second call returns the same rows, not duplicates.
    again = ps.ensure_job_stages(db_session, seed["job_ids"][1])
    assert [s.id for s in again] == [s.id for s in stages]


def test_ensure_application_stages_starts_at_resume_submitted(db_session, application):
    rows = ps.ensure_application_stages(db_session, application)
    assert len(rows) == 11
    assert rows[0].stage.key == "resume_submitted"
    assert rows[0].status == "in_progress"
    assert rows[0].started_at is not None
    assert all(r.status == "pending" for r in rows[1:])
    assert ps.current_stage(application).stage.key == "resume_submitted"
```

- [ ] **Step 3: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_pipeline.py -q`
Expected: FAIL with `ImportError: cannot import name 'pipeline_service'`

- [ ] **Step 4: Write the service**

Create `backend/services/pipeline_service.py`:

```python
"""Every pipeline transition lives here (ATS Phase A, spec 2026-10-03 section 4).

Routers call these and nothing else touches `application_stages` or
`candidates.status`. The functions mutate the session but do not commit, so a
router can compose several and commit once; the tests run inside the
rolled-back fixture transaction the same way.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.models import ApplicationStage, Candidate, JobApplication, PipelineStage

# (key, name, kind, description). Canonical names from the spec, section 4.
DEFAULT_STAGES: list[tuple[str, str, str, str]] = [
    ("resume_submitted", "Resume submitted", "round", "We have your resume and are reviewing it."),
    ("hm_review", "Hiring manager review", "round", "The hiring manager reviews your background against the role."),
    ("technical_written", "Technical assessment", "round", "A take-home or written exercise on the fundamentals of the role."),
    ("technical_interview", "Technical interview", "round", "A live conversation going deep on your primary area."),
    ("problem_solving", "Problem solving", "round", "An open-ended reasoning session with the team."),
    ("case_study", "Case study", "round", "A scenario-based discussion with a small panel."),
    ("hr_screen", "HR screen", "round", "A final conversation about logistics, timing, and references."),
    ("offer", "Offer", "round", "An offer has been extended."),
    ("offer_accepted", "Offer accepted", "round", "You have accepted. We are completing paperwork and a start date."),
    ("offer_declined", "Offer declined", "outcome", "You declined the offer."),
    ("hired", "Hired", "outcome", "Welcome aboard."),
]

ROUND = "round"
OUTCOME = "outcome"

PENDING = "pending"
IN_PROGRESS = "in_progress"
PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"

APP_ACTIVE = "active"
APP_HIRED = "hired"
APP_REJECTED = "rejected"
APP_DECLINED = "declined"
APP_WITHDRAWN = "withdrawn"
TERMINAL = frozenset({APP_HIRED, APP_REJECTED, APP_DECLINED, APP_WITHDRAWN})

DECLINABLE_KEYS = frozenset({"offer", "offer_accepted"})

# Stage key -> candidates.status (spec section 3.3).
_STAGE_TO_CANDIDATE_STATUS = {
    "resume_submitted": "active",
    "hm_review": "screening",
    "technical_written": "interviewing",
    "technical_interview": "interviewing",
    "problem_solving": "interviewing",
    "case_study": "interviewing",
    "hr_screen": "interviewing",
    "offer": "offered",
    "offer_accepted": "offered",
}
_APP_TO_CANDIDATE_STATUS = {
    APP_HIRED: "hired",
    APP_REJECTED: "rejected",
    APP_DECLINED: "withdrawn",
    APP_WITHDRAWN: "withdrawn",
}


class PipelineError(Exception):
    """A transition that is not allowed from the application's current state."""


def ensure_job_stages(db: Session, job_id: int) -> list[PipelineStage]:
    """The job's stages in order, creating the defaults the first time."""
    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.job_id == job_id)
        .order_by(PipelineStage.position)
        .all()
    )
    if stages:
        return stages
    for position, (key, name, kind, description) in enumerate(DEFAULT_STAGES, start=1):
        db.add(
            PipelineStage(
                job_id=job_id,
                key=key,
                name=name,
                kind=kind,
                description=description,
                position=position,
                enabled=True,
            )
        )
    db.flush()
    return (
        db.query(PipelineStage)
        .filter(PipelineStage.job_id == job_id)
        .order_by(PipelineStage.position)
        .all()
    )


def ensure_application_stages(db: Session, application: JobApplication) -> list[ApplicationStage]:
    """The application's stage rows in pipeline order, creating them if absent.

    Absent rows mean an application that predates Phase A and was not reached
    by the migration (a fresh row inserted by old code, or a test fixture). It
    starts at the first enabled round, like a new application would.
    """
    stages = ensure_job_stages(db, application.job_id)
    existing = {row.stage_id: row for row in application.stages}
    if len(existing) == len(stages):
        return sorted(application.stages, key=lambda r: r.stage.position)

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
    if application.status not in TERMINAL:
        application.status = APP_ACTIVE
    sync_candidate_status(db, application)
    return sorted(application.stages, key=lambda r: r.stage.position)


def start_application(db: Session, application: JobApplication) -> list[ApplicationStage]:
    """A brand-new application: stage 1 in progress, candidate status synced."""
    application.status = APP_ACTIVE
    db.flush()
    return ensure_application_stages(db, application)


def current_stage(application: JobApplication) -> Optional[ApplicationStage]:
    for row in application.stages:
        if row.status == IN_PROGRESS:
            return row
    return None


def sync_candidate_status(db: Session, application: JobApplication) -> None:
    """Recompute candidates.status from this application (spec 3.3)."""
    candidate = db.get(Candidate, application.candidate_id)
    if candidate is None:
        return
    if application.status in _APP_TO_CANDIDATE_STATUS:
        candidate.status = _APP_TO_CANDIDATE_STATUS[application.status]
        return
    current = current_stage(application)
    if current is not None:
        candidate.status = _STAGE_TO_CANDIDATE_STATUS.get(current.stage.key, "active")
```

- [ ] **Step 5: Run the tests**

Run: `poetry run pytest backend/tests/test_pipeline.py -q`
Expected: 3 passed

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a3.txt`:

```
feat: pipeline service creates default stages and starts applications

Lazy creation covers jobs and applications that predate the migration or
come from the test fixtures, so nothing has to be reseeded for the board to
work. Candidate status is derived from the application from here on.
```

```powershell
git add backend/services/pipeline_service.py backend/tests/conftest.py backend/tests/test_pipeline.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a3.txt
```

---

### Task 4: The four transitions

**Files:**
- Modify: `backend/services/pipeline_service.py`
- Test: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_pipeline.py`:

```python
def _keys_by_status(application, status):
    return [r.stage.key for r in sorted(application.stages, key=lambda r: r.stage.position) if r.status == status]


def test_advance_moves_to_the_next_enabled_round(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.advance(db_session, application)
    assert _keys_by_status(application, "passed") == ["resume_submitted"]
    assert ps.current_stage(application).stage.key == "hm_review"
    assert db_session.get(Candidate, application.candidate_id).status == "screening"


def test_advance_skips_disabled_rounds(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.advance(db_session, application)  # now at hm_review
    stages = {s.key: s for s in ps.ensure_job_stages(db_session, application.job_id)}
    stages["technical_written"].enabled = False
    db_session.flush()
    ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "technical_interview"
    assert _keys_by_status(application, "skipped") == ["technical_written"]
    stages["technical_written"].enabled = True


def test_advance_from_the_last_round_hires(db_session, application):
    ps.ensure_application_stages(db_session, application)
    for _ in range(9):
        ps.advance(db_session, application)
    assert application.status == "hired"
    assert ps.current_stage(application) is None
    assert "hired" in _keys_by_status(application, "passed")
    assert _keys_by_status(application, "skipped") == ["offer_declined"]
    assert db_session.get(Candidate, application.candidate_id).status == "hired"
    with pytest.raises(ps.PipelineError):
        ps.advance(db_session, application)


def test_reject_fails_current_and_skips_the_rest(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.advance(db_session, application)
    ps.reject(db_session, application, note="Not enough SQL depth.")
    assert application.status == "rejected"
    assert _keys_by_status(application, "failed") == ["hm_review"]
    assert len(_keys_by_status(application, "skipped")) == 9
    failed = next(r for r in application.stages if r.status == "failed")
    assert failed.note == "Not enough SQL depth."
    assert db_session.get(Candidate, application.candidate_id).status == "rejected"


def test_skip_passes_over_the_current_round(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.skip(db_session, application)
    assert _keys_by_status(application, "skipped") == ["resume_submitted"]
    assert ps.current_stage(application).stage.key == "hm_review"


def test_skip_refused_on_the_last_round(db_session, application):
    ps.ensure_application_stages(db_session, application)
    for _ in range(8):
        ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "offer_accepted"
    with pytest.raises(ps.PipelineError):
        ps.skip(db_session, application)


def test_decline_only_at_offer(db_session, application):
    ps.ensure_application_stages(db_session, application)
    with pytest.raises(ps.PipelineError):
        ps.decline(db_session, application)
    for _ in range(7):
        ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "offer"
    ps.decline(db_session, application)
    assert application.status == "declined"
    assert "offer_declined" in _keys_by_status(application, "passed")
    assert "hired" in _keys_by_status(application, "skipped")
    assert db_session.get(Candidate, application.candidate_id).status == "withdrawn"


def test_terminal_application_refuses_everything(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.reject(db_session, application)
    for action in (ps.advance, ps.skip, ps.reject, ps.decline):
        with pytest.raises(ps.PipelineError):
            action(db_session, application)
```

Add `Candidate` to the models import at the top of the test file:

```python
from backend.models.models import ApplicationStage, Candidate, JobApplication, PipelineStage
```

Each test starts from the same seeded application, so they must not leak state into each other. Add this fixture right after the `application` fixture:

```python
@pytest.fixture(autouse=True)
def _reset_application(db_session, seed):
    """Every test starts from a fresh, unstarted application."""
    yield
    app = db_session.get(JobApplication, seed["application_id"])
    for row in list(app.stages):
        db_session.delete(row)
    app.status = "active"
    db_session.get(Candidate, app.candidate_id).status = "active"
    db_session.flush()
    db_session.expire(app)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_pipeline.py -q`
Expected: 8 failed with `AttributeError: module ... has no attribute 'advance'`

- [ ] **Step 3: Implement the transitions**

Append to `backend/services/pipeline_service.py`:

```python
def _ordered(application: JobApplication) -> list[ApplicationStage]:
    return sorted(application.stages, key=lambda r: r.stage.position)


def _require_active(application: JobApplication) -> ApplicationStage:
    if application.status in TERMINAL:
        raise PipelineError(f"This application is already {application.status}.")
    current = current_stage(application)
    if current is None:
        raise PipelineError("This application has no stage in progress.")
    return current


def _next_enabled_round(rows: list[ApplicationStage], after: ApplicationStage) -> Optional[ApplicationStage]:
    for row in rows:
        if row.stage.position <= after.stage.position:
            continue
        if row.stage.kind != ROUND:
            continue
        if row.stage.enabled:
            return row
        if row.status == PENDING:
            row.status = SKIPPED
            row.completed_at = datetime.utcnow()
    return None


def _skip_pending(rows: list[ApplicationStage], now: datetime) -> None:
    for row in rows:
        if row.status == PENDING:
            row.status = SKIPPED
            row.completed_at = now


def _set_outcome(db: Session, application: JobApplication, outcome_key: str, status: str, now: datetime) -> None:
    rows = _ordered(application)
    for row in rows:
        if row.stage.key == outcome_key:
            row.status = PASSED
            row.started_at = now
            row.completed_at = now
    _skip_pending(rows, now)
    application.status = status
    sync_candidate_status(db, application)


def advance(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """Current round passed; next enabled round in progress; last round hires."""
    current = _require_active(application)
    now = datetime.utcnow()
    current.status = PASSED
    current.completed_at = now
    current.changed_by = actor_id
    current.note = note
    nxt = _next_enabled_round(_ordered(application), current)
    if nxt is None:
        _set_outcome(db, application, "hired", APP_HIRED, now)
        return
    nxt.status = IN_PROGRESS
    nxt.started_at = now
    sync_candidate_status(db, application)


def skip(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """Current round skipped; next enabled round in progress. Refused on the last round."""
    current = _require_active(application)
    rows = _ordered(application)
    nxt = _next_enabled_round(rows, current)
    if nxt is None:
        raise PipelineError("There is no later stage to skip to. Use Advance to mark the candidate hired.")
    now = datetime.utcnow()
    current.status = SKIPPED
    current.completed_at = now
    current.changed_by = actor_id
    current.note = note
    nxt.status = IN_PROGRESS
    nxt.started_at = now
    sync_candidate_status(db, application)


def reject(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """Current round failed; everything later skipped; application rejected."""
    current = _require_active(application)
    now = datetime.utcnow()
    current.status = FAILED
    current.completed_at = now
    current.changed_by = actor_id
    current.note = note
    _skip_pending(_ordered(application), now)
    application.status = APP_REJECTED
    sync_candidate_status(db, application)


def decline(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """Candidate declined an offer. Only valid at Offer or Offer accepted."""
    current = _require_active(application)
    if current.stage.key not in DECLINABLE_KEYS:
        raise PipelineError("A candidate can only decline once an offer has been made.")
    now = datetime.utcnow()
    current.status = PASSED
    current.completed_at = now
    current.changed_by = actor_id
    current.note = note
    _set_outcome(db, application, "offer_declined", APP_DECLINED, now)


ACTIONS = {"advance": advance, "skip": skip, "reject": reject, "decline": decline}
```

- [ ] **Step 4: Run the tests**

Run: `poetry run pytest backend/tests/test_pipeline.py -q`
Expected: 11 passed

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a4.txt`:

```
feat: advance, skip, reject, and decline transitions

Rounds and outcomes are different kinds of stage, so advancing past Offer
accepted lands on Hired rather than walking into Offer declined the way the
reference tracker does. Each transition recomputes candidates.status so the
dashboard and candidate list keep working without changes.
```

```powershell
git add backend/services/pipeline_service.py backend/tests/test_pipeline.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a4.txt
```

---

### Task 5: Pydantic models and the router

**Files:**
- Create: `backend/models/pipeline.py`
- Create: `backend/routers/pipeline.py`
- Modify: `backend/main.py:99` (mount after the interviews router)
- Test: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing route tests**

Append to `backend/tests/test_pipeline.py`:

```python
def test_get_job_pipeline_has_a_column_per_enabled_stage(client, seed):
    response = client.get(f"/api/jobs/{seed['job_id']}/pipeline")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == seed["job_id"]
    assert [s["key"] for s in body["stages"]][:2] == ["resume_submitted", "hm_review"]
    assert len(body["columns"]) == 9  # rounds only; outcomes are counts
    first = body["columns"][0]
    assert first["stage_key"] == "resume_submitted"
    assert any(a["application_id"] == seed["application_id"] for a in first["applications"])
    assert body["outcomes"] == {"hired": 0, "rejected": 0, "declined": 0}


def test_get_application_returns_the_timeline(client, seed):
    response = client.get(f"/api/applications/{seed['application_id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "active"
    assert body["current_stage_key"] == "resume_submitted"
    assert len(body["stages"]) == 11
    assert body["stages"][0]["status"] == "in_progress"
    assert body["candidate_name"] == "Ada Lovelace"


def test_actions_require_admin(demo_client, seed):
    response = demo_client.post(f"/api/applications/{seed['application_id']}/advance", json={})
    assert response.status_code == 403


def test_advance_route_moves_the_application(admin_client, seed):
    response = admin_client.post(f"/api/applications/{seed['application_id']}/advance", json={})
    assert response.status_code == 200, response.text
    assert response.json()["current_stage_key"] == "hm_review"


def test_unknown_action_is_404(admin_client, seed):
    response = admin_client.post(f"/api/applications/{seed['application_id']}/promote", json={})
    assert response.status_code == 404


def test_illegal_transition_is_409(admin_client, seed):
    response = admin_client.post(f"/api/applications/{seed['application_id']}/decline", json={})
    assert response.status_code == 409
    assert "offer" in response.json()["detail"].lower()


def test_put_pipeline_disables_a_stage(admin_client, seed):
    response = admin_client.put(
        f"/api/jobs/{seed['job_id']}/pipeline",
        json={"stages": [{"key": "case_study", "enabled": False, "name": "Case study"}]},
    )
    assert response.status_code == 200, response.text
    case_study = next(s for s in response.json()["stages"] if s["key"] == "case_study")
    assert case_study["enabled"] is False
    # Restore so later tests see the default.
    admin_client.put(
        f"/api/jobs/{seed['job_id']}/pipeline",
        json={"stages": [{"key": "case_study", "enabled": True, "name": "Case study"}]},
    )


def test_put_pipeline_never_disables_the_first_round_or_an_outcome(admin_client, seed):
    for key, name in (("resume_submitted", "Resume submitted"), ("hired", "Hired")):
        response = admin_client.put(
            f"/api/jobs/{seed['job_id']}/pipeline",
            json={"stages": [{"key": key, "enabled": False, "name": name}]},
        )
        assert response.status_code == 409, key
        assert "cannot be turned off" in response.json()["detail"]


def test_put_pipeline_refuses_to_disable_a_stage_in_use(admin_client, seed):
    # Move the seeded application to Hiring manager review, then try to turn
    # that stage off underneath it.
    moved = admin_client.post(f"/api/applications/{seed['application_id']}/advance", json={})
    assert moved.json()["current_stage_key"] == "hm_review"
    response = admin_client.put(
        f"/api/jobs/{seed['job_id']}/pipeline",
        json={"stages": [{"key": "hm_review", "enabled": False, "name": "Hiring manager review"}]},
    )
    assert response.status_code == 409
    assert "Move them first" in response.json()["detail"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_pipeline.py -q`
Expected: the new tests fail with 404 (no route yet)

- [ ] **Step 3: Write the Pydantic models**

Create `backend/models/pipeline.py`:

```python
"""Request and response shapes for the pipeline router (ATS Phase A)."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class StageOut(BaseModel):
    id: int
    key: str
    name: str
    kind: str
    description: Optional[str] = None
    position: int
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class ApplicationCard(BaseModel):
    """One candidate chip on the board."""
    application_id: int
    candidate_id: str
    candidate_name: str
    current_position: Optional[str] = None
    entered_at: Optional[datetime] = None


class BoardColumn(BaseModel):
    stage_key: str
    stage_name: str
    applications: List[ApplicationCard]


class JobPipelineResponse(BaseModel):
    job_id: int
    stages: List[StageOut]
    columns: List[BoardColumn]
    outcomes: Dict[str, int]


class StageUpdate(BaseModel):
    key: str
    enabled: bool
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None


class PipelineUpdateRequest(BaseModel):
    stages: List[StageUpdate]


class ApplicationStageOut(BaseModel):
    key: str
    name: str
    kind: str
    description: Optional[str] = None
    enabled: bool
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    note: Optional[str] = None


class ApplicationDetail(BaseModel):
    id: int
    job_id: int
    job_title: str
    candidate_id: str
    candidate_name: str
    status: str
    current_stage_key: Optional[str] = None
    current_stage_name: Optional[str] = None
    applied_at: Optional[datetime] = None
    stages: List[ApplicationStageOut]


class TransitionRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)
```

- [ ] **Step 4: Write the router**

Create `backend/routers/pipeline.py`:

```python
"""Pipeline board and transitions (ATS Phase A, spec 2026-10-03 section 4).

Plain `def` handlers: they do sync ORM work and must not run on the event loop
(CLAUDE.md sharp edge). Writes are admin-only through the app-wide
`enforce_read_only` gate; nothing here needs to re-check that.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..models.models import ApplicationStage, Candidate, Job, JobApplication, PipelineStage
from ..models.pipeline import (
    ApplicationCard,
    ApplicationDetail,
    ApplicationStageOut,
    BoardColumn,
    JobPipelineResponse,
    PipelineUpdateRequest,
    StageOut,
    TransitionRequest,
)
from ..services import pipeline_service as ps
from ..utils.database import get_db

router = APIRouter(tags=["pipeline"])


def _name(candidate: Candidate) -> str:
    return " ".join(part for part in (candidate.first_name, candidate.last_name) if part) or "Unnamed candidate"


def _job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _application_or_404(db: Session, application_id: int) -> JobApplication:
    application = (
        db.query(JobApplication)
        .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
        .filter(JobApplication.id == application_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _detail(db: Session, application: JobApplication) -> ApplicationDetail:
    rows = ps.ensure_application_stages(db, application)
    candidate = db.get(Candidate, application.candidate_id)
    job = db.get(Job, application.job_id)
    current = ps.current_stage(application)
    return ApplicationDetail(
        id=application.id,
        job_id=application.job_id,
        job_title=job.title if job else "",
        candidate_id=application.candidate_id,
        candidate_name=_name(candidate) if candidate else "Unnamed candidate",
        status=application.status,
        current_stage_key=current.stage.key if current else None,
        current_stage_name=current.stage.name if current else None,
        applied_at=application.applied_at,
        stages=[
            ApplicationStageOut(
                key=row.stage.key,
                name=row.stage.name,
                kind=row.stage.kind,
                description=row.stage.description,
                enabled=row.stage.enabled,
                status=row.status,
                started_at=row.started_at,
                completed_at=row.completed_at,
                note=row.note,
            )
            for row in rows
        ],
    )


def _board(db: Session, job: Job) -> JobPipelineResponse:
    stages = ps.ensure_job_stages(db, job.id)
    applications = (
        db.query(JobApplication)
        .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
        .filter(JobApplication.job_id == job.id)
        .all()
    )
    for application in applications:
        ps.ensure_application_stages(db, application)
    db.commit()

    candidates = {
        c.id: c
        for c in db.query(Candidate).filter(Candidate.id.in_([a.candidate_id for a in applications])).all()
    } if applications else {}

    columns = []
    for stage in stages:
        if stage.kind != ps.ROUND or not stage.enabled:
            continue
        cards = []
        for application in applications:
            if application.status != ps.APP_ACTIVE:
                continue
            current = ps.current_stage(application)
            if current is None or current.stage_id != stage.id:
                continue
            candidate = candidates.get(application.candidate_id)
            cards.append(
                ApplicationCard(
                    application_id=application.id,
                    candidate_id=application.candidate_id,
                    candidate_name=_name(candidate) if candidate else "Unnamed candidate",
                    current_position=candidate.current_position if candidate else None,
                    entered_at=current.started_at,
                )
            )
        cards.sort(key=lambda c: (c.entered_at or datetime.min, c.candidate_name))
        columns.append(BoardColumn(stage_key=stage.key, stage_name=stage.name, applications=cards))

    outcomes = {"hired": 0, "rejected": 0, "declined": 0}
    for application in applications:
        if application.status in outcomes:
            outcomes[application.status] += 1

    return JobPipelineResponse(
        job_id=job.id,
        stages=[StageOut.model_validate(s) for s in stages],
        columns=columns,
        outcomes=outcomes,
    )


@router.get("/jobs/{job_id}/pipeline", response_model=JobPipelineResponse)
def get_job_pipeline(job_id: int, db: Session = Depends(get_db)) -> JobPipelineResponse:
    """The job's stages and who is at each one."""
    return _board(db, _job_or_404(db, job_id))


@router.put("/jobs/{job_id}/pipeline", response_model=JobPipelineResponse)
def update_job_pipeline(
    job_id: int, payload: PipelineUpdateRequest, db: Session = Depends(get_db)
) -> JobPipelineResponse:
    """Enable, disable, or rename stages. Outcomes and the first round stay enabled."""
    job = _job_or_404(db, job_id)
    stages = {s.key: s for s in ps.ensure_job_stages(db, job.id)}
    for update in payload.stages:
        stage = stages.get(update.key)
        if stage is None:
            raise HTTPException(status_code=404, detail=f"No stage named '{update.key}' on this job.")
        if not update.enabled and (stage.kind == ps.OUTCOME or stage.position == 1):
            raise HTTPException(status_code=409, detail=f"'{stage.name}' cannot be turned off.")
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
                raise HTTPException(
                    status_code=409,
                    detail=f"{in_use} candidate(s) are at '{stage.name}' right now. Move them first.",
                )
        stage.enabled = update.enabled
        stage.name = update.name.strip()
        if update.description is not None:
            stage.description = update.description.strip() or None
    db.commit()
    return _board(db, job)


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, db: Session = Depends(get_db)) -> ApplicationDetail:
    """One application with its full stage timeline."""
    application = _application_or_404(db, application_id)
    detail = _detail(db, application)
    db.commit()
    return detail


@router.post("/applications/{application_id}/{action}", response_model=ApplicationDetail)
def transition_application(
    application_id: int,
    action: str,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
) -> ApplicationDetail:
    """Advance, skip, reject, or decline. One transaction; 409 when not allowed."""
    fn = ps.ACTIONS.get(action)
    if fn is None:
        raise HTTPException(status_code=404, detail=f"Unknown action '{action}'.")
    application = _application_or_404(db, application_id)
    ps.ensure_application_stages(db, application)
    try:
        fn(db, application, note=payload.note)
    except ps.PipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(application)
    return _detail(db, application)
```

- [ ] **Step 5: Mount the router**

In `backend/main.py`, add `pipeline` to the routers import (find the line that imports `interviews` and add `pipeline` alongside it), then after line 99 (`app.include_router(interviews.router, ...)`) add:

```python
app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])  # ATS Phase A board and transitions
```

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_pipeline.py -q`
Expected: 20 passed

Run: `poetry run pytest backend/tests/test_auth.py -q`
Expected: all pass. The route-walking test now covers the three new mutating routes automatically.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a5.txt`:

```
feat: pipeline router with board, timeline, and transition endpoints

GET and PUT /api/jobs/{id}/pipeline, GET /api/applications/{id}, and
POST /api/applications/{id}/{action}. Disabling a stage that has candidates
in it is refused rather than silently moving them. Verified with 19 service
and route tests plus the existing read-only gate walk.
```

```powershell
git add backend/models/pipeline.py backend/routers/pipeline.py backend/main.py backend/tests/test_pipeline.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a5.txt
```

---

### Task 6: Hook job creation, apply, and the applications list

**Files:**
- Modify: `backend/routers/jobs.py:80-88` (`CandidateApplicationSummary`), `:141-150` (`create_job`), `:526-553` (`apply_to_job`), `:616-640` (`get_candidate_applications`)
- Test: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_pipeline.py`:

```python
def test_creating_a_job_seeds_its_stages(admin_client, db_session):
    response = admin_client.post(
        "/api/jobs/",
        json={
            "title": "Pipeline Test Engineer",
            "department": "Engineering",
            "job_overview": "Exists to test stage seeding.",
            "required_qualifications": "Python",
            "skills": ["Python"],
        },
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    assert db_session.query(PipelineStage).filter(PipelineStage.job_id == job_id).count() == 11


def test_apply_starts_the_pipeline(admin_client, seed):
    response = admin_client.post(
        f"/api/jobs/{seed['job_ids'][1]}/apply",
        json={"candidate_id": seed["candidate_ids"][1], "source": "referral"},
    )
    assert response.status_code == 200, response.text
    application_id = response.json()["id"]
    detail = admin_client.get(f"/api/applications/{application_id}").json()
    assert detail["current_stage_key"] == "resume_submitted"
    assert detail["status"] == "active"


def test_candidate_applications_carry_the_current_stage(client, seed):
    response = client.get(f"/api/jobs/applications/{seed['candidate_id']}")
    assert response.status_code == 200, response.text
    row = next(a for a in response.json() if a["id"] == seed["application_id"])
    assert row["current_stage_key"] == "resume_submitted"
    assert row["current_stage"] == "Resume submitted"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_pipeline.py -q -k "creating_a_job or apply_starts or carry_the_current"`
Expected: 3 failed (count is 0, `KeyError: 'current_stage_key'`)

- [ ] **Step 3: Extend the summary model**

In `backend/routers/jobs.py`, replace the `CandidateApplicationSummary` class with:

```python
class CandidateApplicationSummary(BaseModel):
    """One of a candidate's applications, with the job denormalised in."""
    id: int
    job_id: int
    job_title: Optional[str] = None
    job_department: Optional[str] = None
    status: str
    applied_at: str
    source: Optional[str] = None
    # ATS Phase A: where this application stands. Null once it is terminal.
    current_stage_key: Optional[str] = None
    current_stage: Optional[str] = None
```

- [ ] **Step 4: Seed stages on job creation**

In `create_job`, directly after `db.refresh(db_job)`, add:

```python
        # ATS Phase A: every job carries its own copy of the default stages.
        from ..services import pipeline_service as ps
        ps.ensure_job_stages(db, db_job.id)
        db.commit()
```

- [ ] **Step 5: Start the pipeline on apply**

In `apply_to_job`, replace the block from `db.add(db_application)` through `db.refresh(db_application)` with:

```python
    db.add(db_application)

    # Update job applications count
    if job.applications is None:
        job.applications = 0
    job.applications += 1

    db.flush()
    # ATS Phase A: the application starts at the first enabled round.
    from ..services import pipeline_service as ps
    ps.start_application(db, db_application)
    db.commit()
    db.refresh(db_application)
```

- [ ] **Step 6: Return the current stage on the applications list**

Replace the body of `get_candidate_applications` with:

```python
    """Get all applications for a candidate, with the stage each one is at."""
    from ..services import pipeline_service as ps

    applications = db.query(JobApplication).filter(
        JobApplication.candidate_id == candidate_id
    ).join(Job).all()

    out = []
    for app in applications:
        ps.ensure_application_stages(db, app)
        current = ps.current_stage(app)
        out.append(
            {
                "id": app.id,
                "job_id": app.job_id,
                "job_title": app.job.title,
                "job_department": app.job.department,
                "status": app.status,
                "applied_at": app.applied_at.isoformat(),
                "source": app.source,
                "current_stage_key": current.stage.key if current else None,
                "current_stage": current.stage.name if current else None,
            }
        )
    db.commit()
    return out
```

Note: this handler is `async def` today. Change it to plain `def` while you are in it (it does sync ORM work).

- [ ] **Step 7: Run the tests**

Run: `poetry run pytest backend/tests/test_pipeline.py -q`
Expected: 23 passed

- [ ] **Step 8: Regenerate the contract golden and the OpenAPI file**

```powershell
$env:UPDATE_API_GOLDEN = "1"
poetry run pytest backend/tests/test_api_contract.py -q
Remove-Item Env:UPDATE_API_GOLDEN
git diff backend/tests/golden/api_response_shapes.json
```

Expected diff: only additions of `current_stage` and `current_stage_key` under the candidate applications route. Any removed key is a regression; stop and fix.

```powershell
poetry run python scripts/export_openapi.py
poetry run python scripts/export_openapi.py --check
cd web; npm run types:api; cd ..
```

Expected: `--check` passes; `web/src/lib/schema.d.ts` gains `JobPipelineResponse`, `ApplicationDetail`, `ApplicationStageOut`, `BoardColumn`, `ApplicationCard`, `StageOut`, `PipelineUpdateRequest`, `TransitionRequest`.

- [ ] **Step 9: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a6.txt`:

```
feat: jobs seed their stages, applying starts the pipeline

The candidate applications list now reports the current stage so the
candidate page can link straight into the timeline. Golden contract
regenerated (two added keys, nothing removed) and openapi.json plus the
generated web types updated.
```

```powershell
git add backend/routers/jobs.py backend/tests/test_pipeline.py backend/tests/golden/api_response_shapes.json openapi.json web/src/lib/schema.d.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a6.txt
```

---

### Task 7: Seed data builds a believable board

**Files:**
- Modify: `scripts/seed_demo.py:86-94` (`STATUS_TO_APPLICATION`), `:510-564` (`seed_pipeline`)

- [ ] **Step 1: Replace the status map**

Replace `STATUS_TO_APPLICATION` with the vocabulary the migration introduced:

```python
STATUS_TO_APPLICATION = {
    "active": "active",
    "screening": "active",
    "interviewing": "active",
    "offered": "active",
    "hired": "hired",
    "rejected": "rejected",
    "on_hold": "active",
    "withdrawn": "withdrawn",
}

# How far along the pipeline a seeded application is, by candidate status.
# Index into pipeline_service.DEFAULT_STAGES of the round in progress; None
# for terminal applications.
STATUS_TO_STAGE_INDEX = {
    "active": 0,
    "screening": 1,
    "interviewing": 3,
    "offered": 7,
    "on_hold": 1,
    "hired": None,
    "rejected": None,
    "withdrawn": None,
}
```

- [ ] **Step 2: Add the stage history builder**

Add this function above `seed_pipeline`:

```python
def _seed_stage_history(db, application: JobApplication, candidate_status: str) -> None:
    """Position one application on its job's pipeline from the candidate's status.

    Deterministic: the same status always yields the same rows, and an
    application that already has rows is left alone so a re-run never
    rewinds a board someone has been clicking on.
    """
    from backend.services import pipeline_service as ps

    if application.stages:
        return
    stages = ps.ensure_job_stages(db, application.job_id)
    target = STATUS_TO_STAGE_INDEX.get(candidate_status, 0)
    final = STATUS_TO_APPLICATION.get(candidate_status, "active")
    when = application.applied_at

    for index, stage in enumerate(stages):
        row = ApplicationStage(application_id=application.id, stage_id=stage.id, status="pending")
        if final == "hired":
            row.status = "skipped" if stage.key == "offer_declined" else "passed"
        elif final in ("rejected", "withdrawn"):
            if index == 0:
                row.status = "passed"
            elif index == 1:
                row.status = "failed" if final == "rejected" else "skipped"
            else:
                row.status = "skipped"
        elif target is not None and index < target:
            row.status = "passed"
        elif index == target:
            row.status = "in_progress"
        if row.status != "pending":
            row.started_at = when
        if row.status in ("passed", "failed", "skipped"):
            row.completed_at = when
        db.add(row)
    application.status = final
```

Add `ApplicationStage` to the models import at the top of the script:

```python
from backend.models.models import (
    ApplicationStage,
    Candidate,
    CandidateSkill,
    Job,
    JobApplication,
    SavedJob,
)
```

- [ ] **Step 3: Call it from `seed_pipeline`**

In `seed_pipeline`, replace the three lines

```python
        application.status = app_status
        application.source = candidate.source or "direct"
        application.notes = f"Seeded demo application ({app_status})."
```

with

```python
        application.source = candidate.source or "direct"
        application.notes = f"Seeded demo application ({app_status})."
        db.flush()
        _seed_stage_history(db, application, candidate.status or "active")
```

- [ ] **Step 4: Verify against a fresh database**

```powershell
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
poetry run python scripts/seed_demo.py --no-embeddings
poetry run python scripts/seed_demo.py --no-embeddings
docker exec recruitiq-db psql -U admin -d st_scratch -c "SELECT s.key, COUNT(*) FROM application_stages a JOIN pipeline_stages s ON s.id = a.stage_id WHERE a.status = 'in_progress' GROUP BY s.key ORDER BY MIN(s.position)"
```

Expected: the second run changes nothing (idempotent); the in-progress counts spread across `resume_submitted`, `hm_review`, `technical_interview`, and `offer`.

Then run the suite against the scratch database:

```powershell
poetry run pytest -q
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
```

Expected: everything green except the two known embedding tests under the unreachable-Ollama env.

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a7.txt`:

```
feat: seed data positions every application on its pipeline

A fresh database plus seed_demo.py now yields a populated board on every
job. Re-running is a no-op for applications that already have history, so
clicking around the dev board survives a reseed. Verified on a scratch
database built from migrations alone.
```

```powershell
git add scripts/seed_demo.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a7.txt
```

---

### Task 8: Web types, data helpers, and pure pipeline helpers

**Files:**
- Modify: `web/src/lib/domain.ts`
- Modify: `web/src/lib/data.ts`
- Create: `web/src/lib/pipeline.ts`
- Test: `web/src/lib/pipeline.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/pipeline.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { availableActions, STAGE_STATUS_LABELS } from "./pipeline";
import type { ApplicationDetail } from "./domain";

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

describe("availableActions", () => {
  it("offers advance, skip, and reject mid-pipeline", () => {
    expect(availableActions(detail({}))).toEqual(["advance", "skip", "reject"]);
  });

  it("adds decline once an offer is out", () => {
    expect(availableActions(detail({ current_stage_key: "offer" }))).toEqual([
      "advance",
      "skip",
      "reject",
      "decline",
    ]);
    expect(availableActions(detail({ current_stage_key: "offer_accepted" }))).toEqual([
      "advance",
      "reject",
      "decline",
    ]);
  });

  it("offers nothing on a terminal application", () => {
    expect(availableActions(detail({ status: "hired", current_stage_key: null }))).toEqual([]);
    expect(availableActions(detail({ status: "rejected", current_stage_key: null }))).toEqual([]);
  });
});

describe("STAGE_STATUS_LABELS", () => {
  it("has plain English for every status", () => {
    expect(STAGE_STATUS_LABELS.in_progress).toBe("In progress");
    expect(STAGE_STATUS_LABELS.failed).toBe("Rejected here");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd web; npx vitest run src/lib/pipeline.test.ts`
Expected: FAIL, cannot resolve `./pipeline`

- [ ] **Step 3: Add the type aliases**

In `web/src/lib/domain.ts`, after `export type ResumeSummary = ...`, add:

```ts
/** ATS Phase A: the board on a job page and the timeline on a candidate page. */
export type JobPipeline = Schemas["JobPipelineResponse"];
export type BoardColumn = Schemas["BoardColumn"];
export type ApplicationCard = Schemas["ApplicationCard"];
export type ApplicationDetail = Schemas["ApplicationDetail"];
export type ApplicationStage = Schemas["ApplicationStageOut"];
```

- [ ] **Step 4: Add the data helpers**

In `web/src/lib/data.ts`, add `ApplicationDetail` and `JobPipeline` to the type import from `./domain`, then append:

```ts
/** The stages of one job and who is at each (ATS Phase A). */
export async function getJobPipeline(jobId: number | string): Promise<JobPipeline | null> {
  return apiFetchOptional<JobPipeline>(`/api/jobs/${jobId}/pipeline`, {
    token: await getToken(),
  });
}

/** One application with its full stage timeline. */
export async function getApplication(id: number | string): Promise<ApplicationDetail | null> {
  return apiFetchOptional<ApplicationDetail>(`/api/applications/${id}`, {
    token: await getToken(),
  });
}
```

- [ ] **Step 5: Write the pure helpers**

Create `web/src/lib/pipeline.ts`:

```ts
/**
 * Pipeline vocabulary and the rules for which actions a writer may take.
 *
 * Mirrors `pipeline_service.py`: the server is the authority and answers 409
 * for anything illegal; this only decides which buttons to draw.
 */
import type { ApplicationDetail } from "./domain";

export type StageAction = "advance" | "skip" | "reject" | "decline";

export const ACTION_LABELS: Record<StageAction, string> = {
  advance: "Advance",
  skip: "Skip stage",
  reject: "Reject",
  decline: "Candidate declined",
};

export const STAGE_STATUS_LABELS: Record<string, string> = {
  pending: "Upcoming",
  in_progress: "In progress",
  passed: "Passed",
  failed: "Rejected here",
  skipped: "Skipped",
};

export const APPLICATION_STATUS_LABELS: Record<string, string> = {
  active: "In progress",
  hired: "Hired",
  rejected: "Rejected",
  declined: "Offer declined",
  withdrawn: "Withdrawn",
};

const DECLINABLE = new Set(["offer", "offer_accepted"]);
const LAST_ROUND = "offer_accepted";

export function availableActions(application: ApplicationDetail): StageAction[] {
  if (application.status !== "active" || !application.current_stage_key) return [];
  const key = application.current_stage_key;
  const actions: StageAction[] = ["advance"];
  if (key !== LAST_ROUND) actions.push("skip");
  actions.push("reject");
  if (DECLINABLE.has(key)) actions.push("decline");
  return actions;
}
```

- [ ] **Step 6: Run the tests and the type check**

Run: `cd web; npx vitest run src/lib/pipeline.test.ts; npm run typecheck`
Expected: 4 tests pass; typecheck clean.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a8.txt`:

```
feat(web): pipeline types, data helpers, and action rules

The action rules are a pure function with tests so the candidate page
cannot drift from the server's transition table without a failing test.
```

```powershell
git add web/src/lib/domain.ts web/src/lib/data.ts web/src/lib/pipeline.ts web/src/lib/pipeline.test.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a8.txt
```

---

### Task 9: Action proxy route and the client buttons

**Files:**
- Create: `web/src/app/api/applications/[id]/[action]/route.ts`
- Create: `web/src/components/stage-actions.tsx`

- [ ] **Step 1: Write the proxy route**

Create `web/src/app/api/applications/[id]/[action]/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Forward a pipeline action to the API with the httpOnly session token.
 *
 * Same shape as the jobs handlers: the backend's read-only gate is the
 * authority; this passes its status and body through untouched.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const ACTIONS = new Set(["advance", "skip", "reject", "decline"]);

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string; action: string }> },
) {
  const { id, action } = await context.params;
  if (!/^\d+$/.test(id)) {
    return NextResponse.json({ detail: "That is not a valid application id." }, { status: 400 });
  }
  if (!ACTIONS.has(action)) {
    return NextResponse.json({ detail: `Unknown action '${action}'.` }, { status: 404 });
  }

  const token = await getToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Sign in as an administrator to move candidates." },
      { status: 401 },
    );
  }

  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    // An empty body is fine: every action works without a note.
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/applications/${id}/${action}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
```

- [ ] **Step 2: Write the client component**

Create `web/src/components/stage-actions.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, SkipForward, UserX, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ACTION_LABELS, type StageAction } from "@/lib/pipeline";

/**
 * Advance, Skip, Reject, Decline for one application.
 *
 * Reject and Decline ask for confirmation and an optional note because they
 * are terminal. The timeline is a Server Component, so a refresh is what
 * re-renders it after the API answers.
 */
export function StageActions({
  applicationId,
  actions,
  stageName,
}: {
  applicationId: number;
  actions: StageAction[];
  stageName: string;
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState<StageAction | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<StageAction | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(action: StageAction) {
    if (busy) return;
    setBusy(action);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${applicationId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: note.trim() || null }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) {
        throw new Error(payload?.detail || `Could not ${action} (${response.status})`);
      }
      setConfirming(null);
      setNote("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (actions.length === 0) return null;

  if (confirming) {
    const terminal = confirming === "reject" ? "rejected" : "marked as declined";
    return (
      <div
        role="alertdialog"
        aria-label={`${ACTION_LABELS[confirming]}?`}
        className="space-y-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm"
      >
        <p className="font-medium text-rose-900">
          {ACTION_LABELS[confirming]} at {stageName}?
        </p>
        <p className="text-rose-800">
          The application will be {terminal} and every later stage skipped. This cannot be undone
          from here.
        </p>
        <label className="block">
          <span className="text-xs font-medium text-rose-900">Reason (optional)</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            maxLength={2000}
            className="mt-1 w-full rounded-md border border-rose-200 bg-white p-2 text-sm text-slate-800"
          />
        </label>
        {error ? <p className="font-medium text-rose-900">{error}</p> : null}
        <div className="flex gap-2">
          <Button
            type="button"
            onClick={() => run(confirming)}
            disabled={busy !== null}
            className="bg-rose-600 text-white hover:bg-rose-700"
          >
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
            {ACTION_LABELS[confirming]}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy !== null}
            onClick={() => {
              setConfirming(null);
              setError(null);
            }}
          >
            Keep them here
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {actions.includes("advance") ? (
          <Button type="button" onClick={() => run("advance")} disabled={busy !== null}>
            {busy === "advance" ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <ArrowRight className="mr-2 h-4 w-4" aria-hidden />
            )}
            Advance
          </Button>
        ) : null}
        {actions.includes("skip") ? (
          <Button type="button" variant="outline" onClick={() => run("skip")} disabled={busy !== null}>
            <SkipForward className="mr-2 h-4 w-4" aria-hidden />
            Skip stage
          </Button>
        ) : null}
        {actions.includes("decline") ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => setConfirming("decline")}
            disabled={busy !== null}
          >
            <UserX className="mr-2 h-4 w-4" aria-hidden />
            Candidate declined
          </Button>
        ) : null}
        {actions.includes("reject") ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => setConfirming("reject")}
            disabled={busy !== null}
            className="border-slate-200 text-slate-600 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700"
          >
            <X className="mr-2 h-4 w-4" aria-hidden />
            Reject
          </Button>
        ) : null}
      </div>
      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 3: Type check and lint**

Run: `cd web; npm run typecheck; npm run lint`
Expected: clean.

- [ ] **Step 4: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a9.txt`:

```
feat(web): stage action buttons and their proxy route

Reject and decline confirm first and take an optional reason, because they
end the application. The proxy allowlists the four actions and forwards
the backend's status untouched.
```

```powershell
git add "web/src/app/api/applications/[id]/[action]/route.ts" web/src/components/stage-actions.tsx
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a9.txt
```

---

### Task 10: Candidate page timeline

**Files:**
- Create: `web/src/components/application-timeline.tsx`
- Modify: `web/src/app/candidates/[id]/page.tsx`

- [ ] **Step 1: Write the timeline component**

Create `web/src/components/application-timeline.tsx`:

```tsx
import Link from "next/link";
import { Check, Circle, CircleDot, Minus, X } from "lucide-react";

import { StageActions } from "@/components/stage-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApplicationDetail } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { APPLICATION_STATUS_LABELS, STAGE_STATUS_LABELS, availableActions } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

const ICONS = {
  pending: Circle,
  in_progress: CircleDot,
  passed: Check,
  failed: X,
  skipped: Minus,
} as const;

const ICON_CLASSES: Record<string, string> = {
  pending: "text-slate-300",
  in_progress: "text-indigo-600",
  passed: "text-emerald-600",
  failed: "text-rose-600",
  skipped: "text-slate-400",
};

/**
 * One application's journey through its job's pipeline.
 *
 * Disabled stages are hidden unless something already happened at them, so
 * a job that turned off Case study does not show an empty row for it.
 */
export function ApplicationTimeline({
  application,
  writable,
}: {
  application: ApplicationDetail;
  writable: boolean;
}) {
  const actions = writable ? availableActions(application) : [];
  const current = application.stages.find((s) => s.status === "in_progress");
  const visible = application.stages.filter((s) => s.enabled || s.status !== "pending");

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-baseline justify-between gap-2">
        <CardTitle className="text-base">
          <Link href={`/jobs/${application.job_id}`} className="hover:underline">
            {application.job_title}
          </Link>
        </CardTitle>
        <span className="text-xs text-slate-500">
          {APPLICATION_STATUS_LABELS[application.status] ?? application.status}
          {application.applied_at ? ` · applied ${formatDate(application.applied_at)}` : ""}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        <ol className="space-y-1">
          {visible.map((stage) => {
            const Icon = ICONS[stage.status as keyof typeof ICONS] ?? Circle;
            const isCurrent = stage.status === "in_progress";
            return (
              <li
                key={stage.key}
                className={cn(
                  "flex items-start gap-3 rounded-md px-2 py-1.5 text-sm",
                  isCurrent && "bg-indigo-50",
                )}
              >
                <Icon
                  className={cn("mt-0.5 h-4 w-4 shrink-0", ICON_CLASSES[stage.status])}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className={cn("block", isCurrent ? "font-medium text-slate-900" : "text-slate-700")}>
                    {stage.name}
                    {stage.kind === "outcome" ? (
                      <span className="ml-2 text-xs text-slate-400">outcome</span>
                    ) : null}
                  </span>
                  {isCurrent && stage.description ? (
                    <span className="block text-xs text-slate-500">{stage.description}</span>
                  ) : null}
                  {stage.note ? (
                    <span className="block text-xs text-slate-500">Note: {stage.note}</span>
                  ) : null}
                </span>
                <span className="shrink-0 text-xs text-slate-400">
                  <span className="sr-only">{STAGE_STATUS_LABELS[stage.status]}</span>
                  {stage.completed_at
                    ? formatDate(stage.completed_at)
                    : stage.started_at
                      ? `since ${formatDate(stage.started_at)}`
                      : ""}
                </span>
              </li>
            );
          })}
        </ol>
        {actions.length > 0 && current ? (
          <StageActions
            applicationId={application.id}
            actions={actions}
            stageName={current.name}
          />
        ) : null}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Wire it into the candidate page**

In `web/src/app/candidates/[id]/page.tsx`:

Add imports:

```ts
import { ApplicationTimeline } from "@/components/application-timeline";
import { getApplication } from "@/lib/data";
import { canWrite } from "@/lib/session";
```

(merge `getApplication` into the existing `@/lib/data` import list.)

Change the parallel fetch to also load each application's detail and the write flag:

```ts
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

Replace the `<Card>` titled "Applications" (the first card inside `<div className="grid gap-6 md:grid-cols-2">`) and lift it out of that grid so it spans the right column. The right column becomes:

```tsx
        <div className="space-y-6 lg:col-span-2">
          {details.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Pipeline</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-slate-500">
                  Not in any pipeline yet. Open a job and add them to it.
                </p>
              </CardContent>
            </Card>
          ) : (
            details.map((detail) => (
              <ApplicationTimeline key={detail.id} application={detail} writable={writable} />
            ))
          )}

          {candidate.notes ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-line text-slate-700">{candidate.notes}</p>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recommended roles</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Suspense fallback={<RolesSkeleton />}>
                <RecommendedRoles candidateId={id} />
              </Suspense>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Saved jobs</CardTitle>
            </CardHeader>
            <CardContent>
              {savedJobs.length === 0 ? (
                <p className="text-sm text-slate-500">Nothing saved.</p>
              ) : (
                <ul className="divide-y divide-slate-100 text-sm">
                  {savedJobs.map((saved) => (
                    <li key={saved.id} className="py-2 first:pt-0 last:pb-0">
                      <Link href={`/jobs/${saved.job_id}`} className="font-medium hover:underline">
                        {saved.job_title ?? `Job #${saved.job_id}`}
                      </Link>
                      <p className="text-xs text-slate-500">Saved {formatDate(saved.saved_at)}</p>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
```

The `applications` variable is still used for the detail fetch; remove nothing else.

- [ ] **Step 3: Check it live**

Start the backend and web dev servers (`cd backend; poetry run python -m uvicorn main:app --port 8010` and `cd web; npm run dev`), open `http://localhost:3000/candidates`, click any candidate.

Expected as the demo: a Pipeline card per application with the timeline and no buttons. Sign in as admin (`/login`): Advance, Skip, Reject appear under the current stage; clicking Advance moves the highlight down one row and the header badge updates.

- [ ] **Step 4: Type check, lint, unit tests**

Run: `cd web; npm run typecheck; npm run lint; npm test`
Expected: clean, all tests pass.

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a10.txt`:

```
feat(web): candidate page shows the pipeline timeline with actions

Replaces the read-only Applications list. Writers get Advance, Skip,
Reject, and Decline under the current stage; the demo sees the timeline
only. Checked live as both roles.
```

```powershell
git add web/src/components/application-timeline.tsx "web/src/app/candidates/[id]/page.tsx"
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a10.txt
```

---

### Task 11: Job page board

**Files:**
- Create: `web/src/components/pipeline-board.tsx`
- Modify: `web/src/app/jobs/[id]/page.tsx`

- [ ] **Step 1: Write the board component**

Create `web/src/components/pipeline-board.tsx`:

```tsx
import Link from "next/link";

import type { JobPipeline } from "@/lib/domain";

/**
 * One column per enabled round, candidates as chips, outcomes as a footer.
 *
 * Horizontal scroll rather than wrapping: nine columns never fit, and a
 * board that wraps stops reading left to right as a funnel.
 */
export function PipelineBoard({ pipeline }: { pipeline: JobPipeline }) {
  const active = pipeline.columns.reduce((n, c) => n + c.applications.length, 0);
  const outcomes = pipeline.outcomes;

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">
        {active} in progress · {outcomes.hired ?? 0} hired · {outcomes.rejected ?? 0} rejected ·{" "}
        {outcomes.declined ?? 0} declined
      </p>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {pipeline.columns.map((column) => (
          <section
            key={column.stage_key}
            aria-label={column.stage_name}
            className="w-44 shrink-0 rounded-lg border border-slate-200 bg-slate-50"
          >
            <header className="flex items-baseline justify-between gap-2 border-b border-slate-200 px-3 py-2">
              <h3 className="truncate text-xs font-medium text-slate-700">{column.stage_name}</h3>
              <span className="text-xs text-slate-400">{column.applications.length}</span>
            </header>
            <ul className="space-y-1.5 p-2">
              {column.applications.length === 0 ? (
                <li className="px-1 py-2 text-center text-xs text-slate-300">Empty</li>
              ) : (
                column.applications.map((card) => (
                  <li key={card.application_id}>
                    <Link
                      href={`/candidates/${card.candidate_id}`}
                      className="block rounded-md border border-slate-200 bg-white px-2.5 py-2 text-sm hover:border-indigo-300 hover:bg-indigo-50"
                    >
                      <span className="block truncate font-medium text-slate-800">
                        {card.candidate_name}
                      </span>
                      {card.current_position ? (
                        <span className="block truncate text-xs text-slate-500">
                          {card.current_position}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                ))
              )}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add it to the job page**

In `web/src/app/jobs/[id]/page.tsx`:

Add imports:

```ts
import { PipelineBoard } from "@/components/pipeline-board";
import { getJobPipeline } from "@/lib/data";
```

(merge `getJobPipeline` into the existing `@/lib/data` import.)

Insert a new card as the first child of `<div className="space-y-6 lg:col-span-2">`, above the Overview card:

```tsx
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pipeline</CardTitle>
            </CardHeader>
            <CardContent>
              <Suspense fallback={<Skeleton className="h-40 w-full rounded-lg" />}>
                <Board jobId={job.id} />
              </Suspense>
            </CardContent>
          </Card>
```

Add the async component next to `Matches`:

```tsx
async function Board({ jobId }: { jobId: number }) {
  const pipeline = await getJobPipeline(jobId).catch(() => null);
  if (!pipeline) {
    return <p className="text-sm text-slate-500">The pipeline could not be loaded.</p>;
  }
  return <PipelineBoard pipeline={pipeline} />;
}
```

Also change the Details sidebar's applicant count so it stops reading the stored counter. Replace

```tsx
                <Detail label="Applicants" value={String(job.applications)} />
```

with

```tsx
                <Detail label="Applicants" value={String(job.applications)} />
```

(unchanged in Phase A; the counter is still maintained by `apply_to_job`. Noted here so nobody hunts for a change.)

- [ ] **Step 3: Check it live**

Open `http://localhost:3000/jobs`, click any job.

Expected: a Pipeline card with nine columns, seeded candidates spread across the first four and the Offer column, a one-line outcome summary, and each chip linking to the candidate page.

- [ ] **Step 4: Type check, lint, build, e2e**

Run: `cd web; npm run typecheck; npm run lint; npm test; npm run build`
Expected: clean.

Run: `$env:E2E_BASE_URL = "http://localhost:3000"; npx playwright test`
Expected: pass. If it fails, re-run against `https://recruitiq.io` before blaming the change (a rotted `next dev` fakes failures).

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-a11.txt`:

```
feat(web): pipeline board on the job page

Nine round columns with candidate chips and an outcome summary, streamed
under Suspense like the matching panel so the description paints first.
```

```powershell
git add web/src/components/pipeline-board.tsx "web/src/app/jobs/[id]/page.tsx"
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-a11.txt
```

---

### Task 12: Full verification, PR, deploy

**Files:** none new.

- [ ] **Step 1: Backend, the way CI does it**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
$env:OLLAMA_BASE_URL = "http://localhost:1"
poetry run ruff check backend --select E9,F63,F7,F82 --exclude backend/tests
poetry run python scripts/export_openapi.py --check
poetry run pytest -q
```

Expected: ruff clean, OpenAPI in sync, suite green except the two known embedding tests.

- [ ] **Step 2: Scratch-database pass (schema changed)**

```powershell
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
poetry run pytest -q
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
```

Expected: same result as step 1 on a database built from migrations alone.

- [ ] **Step 3: Push and open the PR**

Write `C:\Users\seaso\AppData\Local\Temp\claude\pr-a.md`:

```
## What

ATS Phase A: every job gets an 11-stage pipeline, every application gets a stage history, and the candidate page gains Advance, Skip, Reject, and Decline. The job page shows a board. Spec: docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md.

## Why

RecruitIQ could rank candidates but could not move them. This is the layer that makes it an applicant tracking system, modelled on the internal hiring process (11 stages, rounds vs outcomes).

## Verified

- backend: test_pipeline.py (23 tests) plus the full suite, on the dev database and on a scratch database built from migrations alone
- migration: upgrade, downgrade, upgrade; backfill positions every existing application from its candidate's status, so prod needs no reseed
- web: typecheck, lint, vitest, build, Playwright journey
- live: both roles on /candidates/[id] and /jobs/[id] against the dev backend

## Prod follow-up

None. alembic upgrade head in deploy.sh runs the backfill. No embedded text changed, so no re-embed.
```

```powershell
git push -u origin ats-pipeline-core
gh pr create --base main --title "feat: pipeline stages, transitions, and board (ATS Phase A)" --body-file C:\Users\seaso\AppData\Local\Temp\claude\pr-a.md
gh pr checks --watch
```

- [ ] **Step 4: Merge and deploy**

```powershell
gh pr merge --merge --delete-branch
git fetch origin
git switch main; git pull --ff-only
```

Deploy with the Bash tool:

```bash
ssh root@157.245.233.229 "free -h"
ssh root@157.245.233.229 "/opt/recruitiq/app/scripts/deploy.sh"
```

Expected: at least 500M available first; `==> deployed <sha>` matching `git rev-parse --short origin/main`.

- [ ] **Step 5: Smoke test prod**

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://recruitiq.io/
ssh root@157.245.233.229 "curl -sS http://127.0.0.1:8020/health"
ssh root@157.245.233.229 "curl -sS http://127.0.0.1:8020/api/jobs/1/pipeline | head -c 400"
curl -sS -o /dev/null -w "%{http_code}\n" https://recruitiq.io/jobs/1
```

Expected: 200, health ok, a JSON body starting with `{"job_id":1,"stages":[...`, and 200 on the job page.

---

## Self-review

**Spec coverage (section 8, Phase A acceptance):**
- 11 stages for any job, including pre-migration jobs: Task 2 backfill plus Task 3 lazy `ensure_job_stages`. Covered.
- Four transitions per section 4, atomic, 409 on terminal: Tasks 4 and 5. Covered.
- Demo gets 403: Task 5 test plus the existing route walk. Covered.
- Dashboard and candidates table unchanged: `sync_candidate_status` in Task 3 and 4. Covered.
- Fresh DB plus migrations plus seed gives a populated board: Task 7. Covered.
- Stage enable/disable/rename (decision 5): Task 5 `PUT`. The admin UI for it is deliberately API-only in Phase A; the job page board reads enabled stages. Noted as a gap to close in Phase E alongside custom stages.

**Placeholder scan:** none of "TBD", "TODO", "similar to", or "add validation" appear. Task 11 Step 2 contains an explicit no-change note, which is intentional.

**Type consistency:** `ps.ACTIONS` keys match the proxy allowlist and `StageAction`. `ApplicationDetail` fields used in `pipeline.test.ts` match `backend/models/pipeline.py`. `current_stage_key` and `current_stage` match between `CandidateApplicationSummary` and the test. `BoardColumn.stage_key`/`stage_name` match the component. `JobPipelineResponse.outcomes` keys (`hired`, `rejected`, `declined`) match the board footer and the route test.
