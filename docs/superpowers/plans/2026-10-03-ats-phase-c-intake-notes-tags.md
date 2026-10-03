# ATS Phase C: Intake, Notes, Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Getting people into a pipeline takes one step (upload, manual add, bulk upload, or "Consider for another role"). Candidates get a notes thread and tags. The candidates list gains a job filter, CSV export, and bulk advance and reject.

**Architecture:** Two new tables (`notes`, `candidate_tags`) and two small routers (`backend/routers/notes.py`, `backend/routers/tags.py`). A new `backend/services/intake_service.py` owns "put this candidate on this job's pipeline", and `apply_to_job`, `create_candidate` and `save-candidate` all call it. That keeps one way in. The bulk endpoint sits in the Phase A pipeline router and applies `pipeline_service.ACTIONS` per item inside savepoints. The CSV export and the candidate list share one filtered query, so the export can never show rows the list would hide. On the web side, Server Components fetch through `lib/data.ts`, client components post through thin Next route handlers built on one shared `lib/proxy.ts` helper, and every pure rule lives in `lib/intake.ts` with Vitest coverage.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic (backend), Next.js 16 App Router + Tailwind + Vitest (web), pytest with the transactional fixtures in `backend/tests/conftest.py`.

**Spec:** `docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md`, sections 3.1 (`notes`, `candidate_tags`), 3.2 (`candidates.notes` read-only), 5 (rows marked C), and 8 Phase C.
**Contract:** the ATS phases B-E shared contract. This plan owns everything under "Phase C owns" and only *uses* Phase B names.

---

## Depends on Phase B (merged first)

This plan uses these Phase B names exactly as the contract defines them and redefines none of them:

- `backend/utils/permissions.py`: `CANDIDATES_ADD`, `PIPELINE_MOVE`, `can(role, permission)`, `ROUTE_PERMISSIONS`.
- `backend/utils/auth.py`: `ROLE_ADMIN`, `ROLE_HIRING_MANAGER`, `ROLE_HIRING_TEAM`, `ROLE_INTERVIEWER`, `ROLE_DEMO`.
- `backend/services/access_service.py`: `visible_candidate_ids(db, user)`.
- `users.name` column.
- `web/src/lib/session.ts`: `canWrite()` (true for admin, hiring_manager, hiring_team).

### Assumptions about Phase B

Phase B is being planned in parallel. Where this plan needs a shape the contract does not pin down, it assumes the shapes below. **Before Task 1, open the merged Phase B code and check each one.** If one is wrong, adjust the matching step here before running it. Do not change Phase B's code to fit this plan.

1. **`ROUTE_PERMISSIONS` entries are `(method: str, path_regex: str, permission: str)` tuples.** `enforce_read_only` matches the regex with `re.fullmatch` against the request path with any trailing slash stripped (the same normalization it does today). Settled by the Phase B plan: it compiles an inner list of string tuples in a comprehension, so this plan appends plain string tuples to that inner list (Task 3 Step 8).
2. **Phase B may already map some intake routes**, namely `POST /api/candidates`, `POST /api/jobs/{id}/apply` and `POST /api/resume/save-candidate`, to `CANDIDATES_ADD` (the matrix row "Add candidates"). Task 3 adds an entry only when no existing entry covers that method and path. The permission tests in this plan decide what is correct, not the list.
3. **`visible_candidate_ids(db, user)` returns `None` for `user=None`, demo, admin, hiring manager and hiring team.** It returns a `set[str]`, possibly empty, for an interviewer.
4. **`users.name` is a nullable `String`.** Where it is empty, this plan falls back to the part of the email before the `@`.
5. **Phase B may have added a visibility filter inside `search_candidates`.** Task 8 moves the filtering into one helper shared with the export. If Phase B's filter is there, it is replaced by the helper's identical one rather than kept twice.
6. **Phase B's candidate page additions** (an interviewers section and a feedback section) sit in the right column. This plan anchors its insertions on three Phase A blocks: the left card's skills block, `{details.length === 0 ? (`, and `{candidate.notes ? (`. If Phase B moved any of them, insert at the equivalent spot.
7. **Phase B does not ship a test fixture for "a client signed in as role X".** This plan adds `backend/tests/intake_helpers.py::client_for_role`. If Phase B added an equivalent, use it and drop the helper.

---

## Decisions this plan makes (the spec left them open)

| Question | Decision | Why |
|---|---|---|
| Existing `candidates.notes` text | The migration copies every non-empty value into a candidate-level `notes` row with `author_id` NULL. The UI labels it "Earlier note". `candidates.notes` itself is left untouched in the database. New code never writes it, the candidate page stops rendering it, and `CandidateUpdate` loses its `notes` field. | Nothing is lost, the downgrade is lossless (the original column still holds the text), and spec 3.2 asks for the column to be read-only now and dropped one release later. |
| `notes` on `POST /api/candidates/` | Kept. It becomes the candidate's first note, authored by the caller. | Old API callers keep working, with the new meaning. |
| Who may write notes and tags | `PIPELINE_MOVE` (admin, hiring manager, hiring team). Anyone who can see the candidate may read them. | Interviewers write feedback (Phase B), not notes. Notes are for the people running the pipeline. |
| Note edit or delete | Not in Phase C. | YAGNI. An append-only thread is also an honest record. |
| Tag normalization | Lowercase, accents folded, `+` becomes `plus`, `#` becomes `sharp`, any other run of non-alphanumerics becomes `-`, trimmed, at most 50 characters. A tag that ends up empty is a 422. | The spec says lower-kebab-case. Without the `+`/`#` rule, `C++` and `C#` would both collapse to `c`. |
| Tags per candidate | At most 20 (409 beyond that). Removing a tag is idempotent. | Keeps the chips readable. |
| Bulk semantics | **Per-item results.** Each application runs in its own savepoint and the response lists which items succeeded and which failed, with the reason. | A bulk reject of 20 where 2 were already rejected by a colleague should move the other 18 and name the 2, not refuse the whole batch. The UI shows every failure by candidate name. |
| Bulk actions | `advance` and `reject` only (the spec's two). At most 100 ids per call, duplicates processed once. | Skip and decline are per-person judgments. |
| Bulk selection | Only when the candidates list is filtered to a job. | An application belongs to one job. Selecting people without a job would be ambiguous. |
| `job_id` on `POST /api/candidates/` | Now creates the application in the same transaction, and sets `position_applied` to the job title when blank. An unknown job is a 404 and creates nothing. | One person, one profile, many pipelines (spec decision 2). Before this, `job_id` was stored and ignored. |
| Saving the same resume twice to the same job | Returns the existing application with `already_in_pipeline: true`, not an error. | Re-uploading a corrected resume is normal. |
| "Consider for another role" | Lists open jobs the candidate has no application for. Source is `internal`. The candidate's derived status follows the newest application (spec 3.3, accepted). | Matches the spec. |
| CSV export contents | Name, email, phone, location, current role and company, source, status, tags, applications (`Job (stage)`), date added. **No scores, no notes.** Cells that would start a spreadsheet formula get an apostrophe prefix. UTF-8 with BOM so Excel shows accents. Capped at 5,000 rows. | Spec says no scores. Formula injection is a real risk for a file built from resumes. |
| Notes FKs | `candidate_id` cascades. `application_id`, `stage_id` and `author_id` are `SET NULL`. | Deleting a job must not delete what people wrote about the candidate. The note just loses its job label. |
| Parse quota and save-from-parse | Both now exempt or allow every role with `CANDIDATES_ADD`, not only admin. | Without this, a hiring team member's bulk upload would stop at the anonymous daily cap. |

---

## Conventions for every task

- Work on branch `ats-intake-notes-tags`, created from `origin/main` after Phase B has merged.
- Backend tests run from the repo root with the dev database:
  ```powershell
  $env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
  $env:OLLAMA_BASE_URL = "http://localhost:1"
  poetry run pytest backend/tests/test_notes_tags.py -q
  ```
- Web tests run from `web/`: `npm test`, `npm run typecheck`, `npm run lint`.
- Commit with `git commit -F <file>` (never `-m` with a here-string). No attribution trailers of any kind.
- No em dashes in any string a user can read. American spelling. Spec section 7 terminology ("Hiring team", "Stage", "Export").
- New endpoints that use `Depends(get_db)` are plain `def`, never `async def`.
- Any reset or setup that writes rows between route tests must `commit()`, not just `flush()`. A route that hits an error rolls the shared test session back to its last commit, which silently undoes anything that was only flushed (Phase A lesson).
- `backend/tests/test_openapi_is_current.py` fails from Task 3 until Task 9 regenerates `openapi.json`. Run only the named test files until then.
- Use PowerShell's `[IO.File]::WriteAllText` or the Edit tool for Python files, never `Set-Content -Encoding utf8` (it adds a BOM).

## File structure

| File | Responsibility |
|---|---|
| `backend/alembic/versions/e6a0c3d4f5b6_notes_and_candidate_tags.py` | Create: both tables, import legacy `candidates.notes` text |
| `backend/models/models.py` | Modify: `Note`, `CandidateTag` |
| `backend/models/intake.py` | Create: Pydantic shapes for notes and tags |
| `backend/models/pipeline.py` | Modify: bulk request and response shapes |
| `backend/models/candidate.py` | Modify: `CandidateUpdate` loses `notes` |
| `backend/models/job.py` | Modify: `JobResponse.active_applications` |
| `backend/utils/tags.py` | Create: `normalize_tag` |
| `backend/utils/permissions.py` | Modify: Phase C entries in `ROUTE_PERMISSIONS` |
| `backend/utils/parse_quota.py` | Modify: exempt `CANDIDATES_ADD` roles |
| `backend/services/intake_service.py` | Create: `add_to_job`, `IntakeError` |
| `backend/routers/notes.py` | Create: `GET/POST /api/candidates/{id}/notes`, `candidate_or_404` |
| `backend/routers/tags.py` | Create: candidate tags and `GET /api/tags` |
| `backend/routers/pipeline.py` | Modify: `POST /api/applications/bulk/{action}` above the single-application route |
| `backend/routers/candidates.py` | Modify: `create_candidate` with job, `_filtered_candidates`, `job_id` filter, `GET /api/candidates/export.csv` |
| `backend/routers/jobs.py` | Modify: `apply_to_job` via intake service, `active_applications` on list and detail |
| `backend/routers/resume.py` | Modify: `save-candidate` takes `job_id`, save allowed for `CANDIDATES_ADD` |
| `backend/main.py` | Modify: mount notes and tags routers |
| `backend/tests/intake_helpers.py` | Create: `client_for_role`, `new_candidate`, `job_with_applicants` |
| `backend/tests/test_notes_tags.py` | Create |
| `backend/tests/test_intake.py` | Create |
| `backend/tests/test_bulk_export.py` | Create |
| `backend/tests/test_seed_demo.py` | Modify: seed tag and note picks are deterministic |
| `scripts/seed_demo.py` | Modify: `seed_notes_and_tags` |
| `openapi.json`, `web/src/lib/schema.d.ts`, `backend/tests/golden/api_response_shapes.json` | Regenerated |
| `web/src/lib/proxy.ts` | Create: `forwardJson`, `readJson` for write route handlers |
| `web/src/lib/intake.ts` + `intake.test.ts` | Create: pure helpers |
| `web/src/lib/domain.ts`, `web/src/lib/data.ts` | Modify: aliases, `getCandidateNotes`, `getCandidateTags`, `listCandidates({jobId})` |
| `web/src/app/api/candidates/route.ts` | Create: POST proxy (add candidate) |
| `web/src/app/api/candidates/export/route.ts` | Create: GET CSV proxy |
| `web/src/app/api/candidates/[id]/notes/route.ts` | Create |
| `web/src/app/api/candidates/[id]/tags/route.ts` | Create |
| `web/src/app/api/candidates/[id]/tags/[tag]/route.ts` | Create |
| `web/src/app/api/jobs/[id]/apply/route.ts` | Create |
| `web/src/app/api/applications/bulk/[action]/route.ts` | Create |
| `web/src/app/api/resume/save/route.ts` | Modify: forward `job_id` |
| `web/src/components/notes-thread.tsx` | Create |
| `web/src/components/candidate-tags.tsx` | Create |
| `web/src/components/consider-for-role.tsx` | Create |
| `web/src/components/add-candidate-panel.tsx` | Create |
| `web/src/components/candidate-table.tsx` | Create: list table with bulk selection (moved out of the page) |
| `web/src/components/candidate-filters.tsx` | Modify: job filter |
| `web/src/components/bulk-uploader.tsx` | Create |
| `web/src/components/resume-uploader.tsx` | Modify: "Save and add to [job]", export `ACCEPT` |
| `web/src/app/candidates/page.tsx` | Modify |
| `web/src/app/candidates/[id]/page.tsx` | Modify |
| `web/src/app/upload/page.tsx` | Modify: one or several resumes |
| `web/src/app/jobs/page.tsx` | Modify: card count from the pipeline |

---

### Task 1: Branch and ORM models

**Files:**
- Modify: `backend/models/models.py` (append after `ApplicationStage`)
- Test: `backend/tests/test_notes_tags.py` (new)

- [ ] **Step 1: Create the branch**

```powershell
git fetch origin
git switch -c ats-intake-notes-tags origin/main
git log --oneline -3   # Phase B's merge commit must be in here
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_notes_tags.py`:

```python
"""Notes and tags on candidates (ATS Phase C).

Runs against the real schema inside the session-wide rolled-back transaction
from conftest. Writes go through the API wherever a route exists, so the
permission gate and the visibility filter are exercised with the data.
"""
from __future__ import annotations

import pytest

from backend.models.models import CandidateTag, Note


def test_models_import_and_map():
    assert Note.__tablename__ == "notes"
    assert CandidateTag.__tablename__ == "candidate_tags"
    assert {"author", "application", "stage"} <= set(Note.__mapper__.relationships.keys())
```

- [ ] **Step 3: Run it to verify it fails**

Run: `poetry run pytest backend/tests/test_notes_tags.py::test_models_import_and_map -q`
Expected: FAIL with `ImportError: cannot import name 'CandidateTag'`

- [ ] **Step 4: Add the models**

Append to `backend/models/models.py` after the `ApplicationStage` class:

```python
# ====================================================================
# Notes and tags (ATS Phase C, spec 2026-10-03 section 3.1)
# ====================================================================


class Note(Base):
    """One entry in a candidate's notes thread.

    `application_id` and `stage_id` are both null for a note about the person,
    and both set for a note about one stage of one application. `author_id` is
    null only for text imported from the old `candidates.notes` column. The
    three SET NULL foreign keys mean deleting a job or a user never deletes what
    someone wrote about a candidate; the note just loses its label.
    """
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(
        String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id = Column(
        Integer, ForeignKey("job_applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stage_id = Column(Integer, ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    author = relationship("User")
    application = relationship("JobApplication")
    stage = relationship("PipelineStage")

    def __repr__(self):
        return f"<Note(candidate_id={self.candidate_id}, application_id={self.application_id})>"


class CandidateTag(Base):
    """A lower-kebab-case label on a candidate. Normalized on write by `utils.tags`."""
    __tablename__ = "candidate_tags"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(
        String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("candidate_id", "tag", name="uq_candidate_tag"),)

    def __repr__(self):
        return f"<CandidateTag(candidate_id={self.candidate_id}, tag='{self.tag}')>"
```

- [ ] **Step 5: Run the test**

Run: `poetry run pytest backend/tests/test_notes_tags.py::test_models_import_and_map -q`
Expected: PASS

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c1.txt`:

```
feat: add note and candidate tag models

Phase C of the ATS blueprint. The tables arrive with the next commit's
migration; this registers the ORM classes so the routers can be written
against them. Notes keep their text when a job, stage, or author is
deleted (SET NULL), and go with the candidate (CASCADE).
```

```powershell
git add backend/models/models.py backend/tests/test_notes_tags.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c1.txt
```

---

### Task 2: Migration with legacy notes import

**Files:**
- Create: `backend/alembic/versions/e6a0c3d4f5b6_notes_and_candidate_tags.py`

- [ ] **Step 1: Confirm the head**

```powershell
cd backend; poetry run alembic heads; cd ..
```

Expected: exactly one head, `d5f9b2c3e4a5`. If it differs, stop and set `down_revision` below to the single head that is printed.

- [ ] **Step 2: Write the migration**

Create `backend/alembic/versions/e6a0c3d4f5b6_notes_and_candidate_tags.py`:

```python
"""notes and candidate_tags, importing the old candidates.notes text

ATS Phase C (spec 2026-10-03 section 3.1). Creates both tables, then copies
every non-empty candidates.notes value into a candidate-level note with no
author, which the UI shows as "Earlier note". candidates.notes itself is left
untouched: the spec makes it read-only now and drops it one release later,
and leaving it in place makes the downgrade lossless.

Revision ID: e6a0c3d4f5b6
Revises: d5f9b2c3e4a5
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6a0c3d4f5b6"
down_revision: Union[str, None] = "d5f9b2c3e4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("job_applications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "stage_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notes_candidate_id", "notes", ["candidate_id"])
    op.create_index("ix_notes_application_id", "notes", ["application_id"])

    op.create_table(
        "candidate_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("candidate_id", "tag", name="uq_candidate_tag"),
    )
    op.create_index("ix_candidate_tags_candidate_id", "candidate_tags", ["candidate_id"])
    op.create_index("ix_candidate_tags_tag", "candidate_tags", ["tag"])

    op.execute(
        "INSERT INTO notes (candidate_id, body, created_at) "
        "SELECT id, btrim(notes), COALESCE(updated_at, created_at, now()) "
        "FROM candidates WHERE notes IS NOT NULL AND btrim(notes) <> ''"
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_tags_tag", table_name="candidate_tags")
    op.drop_index("ix_candidate_tags_candidate_id", table_name="candidate_tags")
    op.drop_table("candidate_tags")
    op.drop_index("ix_notes_application_id", table_name="notes")
    op.drop_index("ix_notes_candidate_id", table_name="notes")
    op.drop_table("notes")
```

- [ ] **Step 3: Verify on a scratch database, including the import**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade d5f9b2c3e4a5; cd ..
docker exec recruitiq-db psql -U admin -d st_scratch -c "INSERT INTO candidates (id, first_name, last_name, email, status, notes, created_at, updated_at) VALUES ('00000000-0000-4000-8000-0000000c0001', 'Legacy', 'Note', 'legacy-note@example.com', 'active', '  Prefers morning interviews.  ', now(), now()), ('00000000-0000-4000-8000-0000000c0002', 'Blank', 'Note', 'blank-note@example.com', 'active', '   ', now(), now())"
cd backend; poetry run alembic upgrade head; cd ..
docker exec recruitiq-db psql -U admin -d st_scratch -c "SELECT candidate_id, author_id IS NULL AS imported, body FROM notes"
cd backend; poetry run alembic downgrade -1; poetry run alembic upgrade head; cd ..
docker exec recruitiq-db psql -U admin -d st_scratch -c "\d notes" -c "\d candidate_tags"
```

Expected: one imported row for `...c0001` with body `Prefers morning interviews.` (trimmed) and `imported = t`, and no row for the blank one. The downgrade and second upgrade both succeed, and the second upgrade imports the same single row again. Both tables show the FKs with `ON DELETE CASCADE` or `ON DELETE SET NULL` as written.

- [ ] **Step 4: Apply to the dev database**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
docker exec recruitiq-db psql -U admin -d ats_db -t -c "SELECT COUNT(*) FROM candidates WHERE notes IS NOT NULL AND btrim(notes) <> ''"
cd backend; poetry run alembic upgrade head; cd ..
docker exec recruitiq-db psql -U admin -d ats_db -t -c "SELECT COUNT(*) FROM notes WHERE author_id IS NULL"
```

Expected: the two counts are equal.

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c2.txt`:

```
feat: migration for notes and candidate tags, importing old notes

Every non-empty candidates.notes value becomes a candidate-level note
with no author, so nothing anyone wrote disappears when the page switches
to the thread. The old column is left as it was, which keeps the
downgrade lossless. Verified on a scratch database: a seeded legacy note
is imported trimmed, a blank one is skipped, and upgrade, downgrade,
upgrade all succeed.
```

```powershell
git add backend/alembic/versions/e6a0c3d4f5b6_notes_and_candidate_tags.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c2.txt
```

---

### Task 3: Tag normalization, test helpers, permission entries, tags router

**Files:**
- Create: `backend/utils/tags.py`, `backend/models/intake.py`, `backend/routers/notes.py` (only `candidate_or_404` for now), `backend/routers/tags.py`, `backend/tests/intake_helpers.py`
- Modify: `backend/utils/permissions.py`, `backend/main.py`
- Test: `backend/tests/test_notes_tags.py`

- [ ] **Step 1: Write the test helpers**

Create `backend/tests/intake_helpers.py`:

```python
"""Shared setup for the ATS Phase C tests.

`client_for_role` builds a signed-in TestClient for any role so each test file
can exercise Phase B's permission matrix without growing conftest. It commits
the user rather than flushing: a route that errors rolls the shared session
back to its last commit, and a merely flushed user would vanish mid-module.
Callers must depend on the `override_get_db` fixture (directly or through
`client`, `admin_client`, or `demo_client`) so the app reads the test session.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.models import User
from backend.utils.auth import create_access_token

from .conftest import SEED_EMAIL_DOMAIN, SEED_EPOCH

JOB_PAYLOAD = {
    "department": "Engineering",
    "job_overview": "Exists for the Phase C tests.",
    "required_qualifications": "Python",
    "skills": ["Python"],
}


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def client_for_role(db_session: Session, role: str) -> TestClient:
    user = User(
        email=f"{unique(role)}@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role=role,
        name=f"Test {role.replace('_', ' ').title()}",
        created_at=SEED_EPOCH,
    )
    db_session.add(user)
    db_session.commit()
    return TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Authorization": f"Bearer {create_access_token(user)}"},
    )


def new_candidate(admin_client: TestClient, job_id: Optional[int] = None, **extra) -> str:
    """Create a candidate through the API and return its id."""
    payload = {
        "first_name": "Intake",
        "last_name": "Test",
        "email": f"{unique('intake')}@{SEED_EMAIL_DOMAIN}",
        **extra,
    }
    if job_id is not None:
        payload["job_id"] = job_id
    response = admin_client.post("/api/candidates/", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def new_job(admin_client: TestClient, title_prefix: str = "Phase C Job") -> int:
    response = admin_client.post(
        "/api/jobs/", json={**JOB_PAYLOAD, "title": f"{title_prefix} {unique('j')}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def application_id_for(client: TestClient, candidate_id: str, job_id: int) -> int:
    rows = client.get(f"/api/jobs/applications/{candidate_id}").json()
    return next(row["id"] for row in rows if row["job_id"] == job_id)


def job_with_applicants(admin_client: TestClient, count: int) -> tuple[int, list[str], list[int]]:
    """A fresh job with `count` new candidates at Resume submitted."""
    job_id = new_job(admin_client, "Bulk Test")
    candidate_ids = [new_candidate(admin_client, job_id=job_id) for _ in range(count)]
    application_ids = [application_id_for(admin_client, cid, job_id) for cid in candidate_ids]
    return job_id, candidate_ids, application_ids
```

Note: `new_candidate(..., job_id=...)` only starts a pipeline once Task 5 lands. Task 3 and Task 4 use it without `job_id`.

- [ ] **Step 2: Write the failing tests**

Append to `backend/tests/test_notes_tags.py`:

```python
from backend.utils.tags import normalize_tag

from .intake_helpers import client_for_role, new_candidate

# The web mirror in web/src/lib/intake.test.ts pins the same table.
TAG_CASES = [
    ("Relocation OK", "relocation-ok"),
    ("  strong   SQL!! ", "strong-sql"),
    ("C++", "cplusplus"),
    ("C# developer", "csharp-developer"),
    ("Señor engineer", "senor-engineer"),
    ("already-kebab", "already-kebab"),
    ("--x--", "x"),
    ("a" * 80, "a" * 50),
]


@pytest.mark.parametrize("raw, expected", TAG_CASES)
def test_normalize_tag(raw, expected):
    assert normalize_tag(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "!!!", "---"])
def test_normalize_tag_refuses_nothing_left(raw):
    with pytest.raises(ValueError, match="letter or number"):
        normalize_tag(raw)


@pytest.fixture(scope="module")
def team_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "hiring_team")


@pytest.fixture(scope="module")
def interviewer_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "interviewer")


def test_add_tag_normalizes_dedupes_and_removes(admin_client):
    cid = new_candidate(admin_client)
    first = admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "Relocation OK"})
    assert first.status_code == 200, first.text
    assert first.json() == {"candidate_id": cid, "tags": ["relocation-ok"]}

    again = admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "relocation ok"})
    assert again.json()["tags"] == ["relocation-ok"]

    admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "Strong SQL"})
    listed = admin_client.get(f"/api/candidates/{cid}/tags")
    assert listed.json()["tags"] == ["relocation-ok", "strong-sql"]  # alphabetical

    removed = admin_client.delete(f"/api/candidates/{cid}/tags/relocation-ok")
    assert removed.status_code == 200
    assert removed.json()["tags"] == ["strong-sql"]
    # Idempotent: removing it twice is not an error.
    assert admin_client.delete(f"/api/candidates/{cid}/tags/relocation-ok").status_code == 200


def test_empty_tag_is_a_422_with_a_reason(admin_client):
    cid = new_candidate(admin_client)
    response = admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "!!!"})
    assert response.status_code == 422
    assert "letter or number" in response.json()["detail"]


def test_tag_limit_is_twenty(admin_client):
    cid = new_candidate(admin_client)
    for i in range(20):
        assert admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": f"t{i}"}).status_code == 200
    response = admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "one-too-many"})
    assert response.status_code == 409
    assert "at most 20" in response.json()["detail"]
    # Re-adding an existing tag at the limit is still fine.
    assert admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "t3"}).status_code == 200


def test_unknown_candidate_tags_is_404(admin_client):
    assert admin_client.get("/api/candidates/00000000-0000-4000-8000-00000000dead/tags").status_code == 404


def test_tag_counts_cover_every_candidate(admin_client, client):
    a = new_candidate(admin_client)
    b = new_candidate(admin_client)
    tag = "phase-c-count-check"
    admin_client.post(f"/api/candidates/{a}/tags", json={"tag": tag})
    admin_client.post(f"/api/candidates/{b}/tags", json={"tag": tag})
    counts = {row["tag"]: row["count"] for row in client.get("/api/tags").json()}
    assert counts[tag] == 2


def test_tag_writes_follow_the_permission_matrix(demo_client, team_client, interviewer_client, admin_client):
    cid = new_candidate(admin_client)
    path = f"/api/candidates/{cid}/tags"
    assert demo_client.post(path, json={"tag": "x"}).status_code == 403
    assert interviewer_client.post(path, json={"tag": "x"}).status_code == 403
    assert team_client.post(path, json={"tag": "x"}).status_code == 200
    assert interviewer_client.delete(f"{path}/x").status_code == 403
    assert team_client.delete(f"{path}/x").status_code == 200


def test_interviewer_cannot_read_tags_of_unassigned_candidates(admin_client, interviewer_client):
    cid = new_candidate(admin_client)
    assert interviewer_client.get(f"/api/candidates/{cid}/tags").status_code == 404
```

- [ ] **Step 3: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_notes_tags.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'backend.utils.tags'`

- [ ] **Step 4: Write `normalize_tag`**

Create `backend/utils/tags.py`:

```python
"""Tag normalization (ATS Phase C, spec 2026-10-03 section 3.1: lower-kebab-case on write).

Mirrored by `normalizeTag` in web/src/lib/intake.ts, and both are pinned by the
same table of cases, so the preview under the tag input always shows exactly
what the server will store.
"""
from __future__ import annotations

import re
import unicodedata

MAX_TAG_LENGTH = 50

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_tag(raw: str) -> str:
    """`"C# Developer"` -> `"csharp-developer"`. Raises ValueError when nothing usable is left."""
    folded = unicodedata.normalize("NFKD", raw or "").encode("ascii", "ignore").decode("ascii")
    text = folded.lower().replace("+", "plus").replace("#", "sharp")
    tag = _NON_ALNUM.sub("-", text).strip("-")[:MAX_TAG_LENGTH].rstrip("-")
    if not tag:
        raise ValueError("A tag needs at least one letter or number.")
    return tag
```

- [ ] **Step 5: Write the Pydantic shapes**

Create `backend/models/intake.py`:

```python
"""Request and response shapes for notes and tags (ATS Phase C)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    # Both null: a note about the person. application_id alone: about that
    # application in general. Both set: about one stage of it.
    application_id: Optional[int] = None
    stage_key: Optional[str] = None


class NoteOut(BaseModel):
    id: int
    candidate_id: str
    body: str
    created_at: datetime
    # Null only for text imported from the old candidates.notes column.
    author_name: Optional[str] = None
    application_id: Optional[int] = None
    job_title: Optional[str] = None
    stage_name: Optional[str] = None


class TagCreate(BaseModel):
    tag: str = Field(max_length=80)


class CandidateTagsResponse(BaseModel):
    candidate_id: str
    tags: List[str]


class TagCount(BaseModel):
    tag: str
    count: int
```

- [ ] **Step 6: Write the shared visibility guard**

Create `backend/routers/notes.py` with only the guard for now (Task 4 adds the routes):

```python
"""Notes on candidates (ATS Phase C, spec 2026-10-03 sections 3.1 and 5).

Plain `def` handlers (sync ORM, CLAUDE.md sharp edge). Writes are gated by
`ROUTE_PERMISSIONS` (PIPELINE_MOVE); reads by `visible_candidate_ids`, so an
interviewer only ever sees notes on candidates they are assigned to. Notes
never reach the scorer or any model prompt.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..models.intake import NoteCreate, NoteOut
from ..models.models import Candidate, JobApplication, Note, User
from ..services import pipeline_service as ps
from ..services.access_service import visible_candidate_ids
from ..services.feedback_service import display_name
from ..utils.auth import get_optional_user
from ..utils.database import get_db

router = APIRouter()


def candidate_or_404(db: Session, user: Optional[User], candidate_id: str) -> Candidate:
    """The candidate, or 404 when it does not exist or this user may not see it.

    One status for both on purpose: telling an interviewer "exists but not
    yours" would leak who is in the pipeline.
    """
    candidate = db.get(Candidate, candidate_id)
    visible = visible_candidate_ids(db, user)
    if candidate is None or (visible is not None and candidate_id not in visible):
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate
```

- [ ] **Step 7: Write the tags router**

Create `backend/routers/tags.py`:

```python
"""Tags on candidates (ATS Phase C).

Writes are gated by `ROUTE_PERMISSIONS` (PIPELINE_MOVE); reads by
`visible_candidate_ids` through `notes.candidate_or_404`.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.intake import CandidateTagsResponse, TagCount, TagCreate
from ..models.models import CandidateTag, User
from ..services.access_service import visible_candidate_ids
from ..utils.auth import get_optional_user
from ..utils.database import get_db
from ..utils.tags import normalize_tag
from .notes import candidate_or_404

router = APIRouter()

MAX_TAGS_PER_CANDIDATE = 20


def _tags(db: Session, candidate_id: str) -> List[str]:
    rows = (
        db.query(CandidateTag.tag)
        .filter(CandidateTag.candidate_id == candidate_id)
        .order_by(CandidateTag.tag)
        .all()
    )
    return [tag for (tag,) in rows]


@router.get("/candidates/{candidate_id}/tags", response_model=CandidateTagsResponse)
def list_candidate_tags(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> CandidateTagsResponse:
    candidate_or_404(db, user, candidate_id)
    return CandidateTagsResponse(candidate_id=candidate_id, tags=_tags(db, candidate_id))


@router.post("/candidates/{candidate_id}/tags", response_model=CandidateTagsResponse)
def add_candidate_tag(
    candidate_id: str,
    payload: TagCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> CandidateTagsResponse:
    """Add one tag, normalized. Adding a tag the candidate already has is a no-op."""
    candidate_or_404(db, user, candidate_id)
    try:
        tag = normalize_tag(payload.tag)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    current = _tags(db, candidate_id)
    if tag not in current:
        if len(current) >= MAX_TAGS_PER_CANDIDATE:
            raise HTTPException(
                status_code=409,
                detail=f"A candidate can carry at most {MAX_TAGS_PER_CANDIDATE} tags. Remove one first.",
            )
        db.add(CandidateTag(candidate_id=candidate_id, tag=tag))
        db.commit()
    return CandidateTagsResponse(candidate_id=candidate_id, tags=_tags(db, candidate_id))


@router.delete("/candidates/{candidate_id}/tags/{tag}", response_model=CandidateTagsResponse)
def remove_candidate_tag(
    candidate_id: str,
    tag: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> CandidateTagsResponse:
    """Remove one tag. Idempotent: removing a tag that is not there is not an error."""
    candidate_or_404(db, user, candidate_id)
    db.query(CandidateTag).filter(
        CandidateTag.candidate_id == candidate_id, CandidateTag.tag == tag
    ).delete(synchronize_session=False)
    db.commit()
    return CandidateTagsResponse(candidate_id=candidate_id, tags=_tags(db, candidate_id))


@router.get("/tags", response_model=List[TagCount])
def list_tags(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> List[TagCount]:
    """Every tag in use with how many candidates carry it, most used first."""
    count = func.count(CandidateTag.candidate_id)
    query = db.query(CandidateTag.tag, count).group_by(CandidateTag.tag)
    visible = visible_candidate_ids(db, user)
    if visible is not None:
        if not visible:
            return []
        query = query.filter(CandidateTag.candidate_id.in_(visible))
    return [TagCount(tag=tag, count=n) for tag, n in query.order_by(count.desc(), CandidateTag.tag).all()]
```

- [ ] **Step 8: Add the Phase C permission entries**

Open `backend/utils/permissions.py` and find `ROUTE_PERMISSIONS`. Phase B writes it as a comprehension over an inner list of `(method, pattern_string, permission)` tuples and compiles each pattern; append these rows to that **inner** list, as plain strings. Phase B's list already covers `POST /api/candidates`, `POST /api/jobs/\d+/apply`, and `POST /api/resume/(save-candidate|confirm)`, so skip those three lines (they are kept below only so the full set is visible in one place):

```python
    # ATS Phase C: intake, notes, tags, bulk moves.
    ("POST", r"/api/candidates", CANDIDATES_ADD),
    ("POST", r"/api/jobs/\d+/apply", CANDIDATES_ADD),
    ("POST", r"/api/resume/save-candidate", CANDIDATES_ADD),
    ("POST", r"/api/candidates/[^/]+/notes", PIPELINE_MOVE),
    ("POST", r"/api/candidates/[^/]+/tags", PIPELINE_MOVE),
    ("DELETE", r"/api/candidates/[^/]+/tags/[^/]+", PIPELINE_MOVE),
    ("POST", r"/api/applications/bulk/[a-z_]+", PIPELINE_MOVE),
```

Phase B's second gate (`enforce_interviewer_scope` in `backend/services/access_service.py`) denies interviewers every read path not in `INTERVIEWER_PATHS`, and it stops at the **first** pattern that matches. So that interviewers can read notes and tags on the candidates they interview (decision above), widen Phase B's candidate entry in `INTERVIEWER_PATHS` from

```python
        (r"/api/candidates/(?P<id>[^/]+)(/resumes)?", "candidate"),
```

to

```python
        (r"/api/candidates/(?P<id>[^/]+)(/resumes|/notes|/tags)?", "candidate"),
```

Unassigned candidates still answer 404 from the gate, which is what `test_interviewer_cannot_read_tags_of_unassigned_candidates` and `test_interviewer_cannot_read_notes_of_unassigned_candidates` expect. Task 8 adds the export path to the same list.

- [ ] **Step 9: Mount the routers**

In `backend/main.py`, add `notes` and `tags` to the second `from backend.routers import ...` line. After the `pipeline` router's `include_router` line, add:

```python
app.include_router(notes.router, prefix="/api", tags=["notes"])  # ATS Phase C candidate notes
app.include_router(tags.router, prefix="/api", tags=["tags"])  # ATS Phase C candidate tags
```

- [ ] **Step 10: Run the tests**

Run: `poetry run pytest backend/tests/test_notes_tags.py -q`
Expected: 20 passed (1 model, 8 normalize, 4 refuse-empty, 7 route tests).

Run: `poetry run pytest backend/tests/test_auth.py -q`
Expected: all pass. The route walk now includes the three new mutating routes and they refuse demo and anonymous callers.

- [ ] **Step 11: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c3.txt`:

```
feat: candidate tags with lower-kebab-case normalization

Tags are normalized on write (accents folded, + and # spelled out so C++
and C# survive, everything else kebab-cased, 50 characters max), capped at
20 per candidate, and removed idempotently. Writes need pipeline.move;
reads go through the same visibility guard notes will use, so an
interviewer sees nothing about candidates they are not assigned to.
Verified: 21 tests including demo, interviewer, and hiring team against
the permission matrix, plus the read-only route walk.
```

```powershell
git add backend/utils/tags.py backend/models/intake.py backend/routers/notes.py backend/routers/tags.py backend/utils/permissions.py backend/main.py backend/tests/intake_helpers.py backend/tests/test_notes_tags.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c3.txt
```

---

### Task 4: Notes thread API

**Files:**
- Modify: `backend/routers/notes.py`
- Test: `backend/tests/test_notes_tags.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_notes_tags.py`:

```python
from backend.models.models import JobApplication
from backend.services.feedback_service import display_name

from .intake_helpers import new_job


def test_general_note_round_trips_with_the_author(admin_client, admin_user):
    cid = new_candidate(admin_client)
    created = admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "  Great call.  "})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["body"] == "Great call."
    assert body["author_name"] == display_name(admin_user)
    assert "@" not in body["author_name"]  # never an email, even for a nameless admin
    assert body["application_id"] is None and body["stage_name"] is None


def test_notes_are_newest_first(admin_client):
    cid = new_candidate(admin_client)
    admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "first"})
    admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "second"})
    listed = admin_client.get(f"/api/candidates/{cid}/notes").json()
    assert [n["body"] for n in listed] == ["second", "first"]


def test_stage_note_carries_job_and_stage_labels(admin_client, seed):
    response = admin_client.post(
        f"/api/candidates/{seed['candidate_id']}/notes",
        json={"body": "Asked about SQL depth.", "application_id": seed["application_id"], "stage_key": "hm_review"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["job_title"] == "Senior Data Engineer"
    assert response.json()["stage_name"] == "Hiring manager review"


@pytest.mark.parametrize(
    "payload, fragment",
    [
        ({"body": "   "}, "some text"),
        ({"body": "x", "stage_key": "hm_review"}, "Pick the application"),
        ({"body": "x", "application_id": -1}, "different candidate"),
    ],
)
def test_bad_notes_are_422_with_a_reason(admin_client, payload, fragment):
    cid = new_candidate(admin_client)
    response = admin_client.post(f"/api/candidates/{cid}/notes", json=payload)
    assert response.status_code == 422
    assert fragment in str(response.json()["detail"])


def test_application_of_another_candidate_is_refused(admin_client, seed):
    other = new_candidate(admin_client)
    response = admin_client.post(
        f"/api/candidates/{other}/notes",
        json={"body": "x", "application_id": seed["application_id"]},
    )
    assert response.status_code == 422


def test_unknown_stage_key_is_refused(admin_client, seed):
    response = admin_client.post(
        f"/api/candidates/{seed['candidate_id']}/notes",
        json={"body": "x", "application_id": seed["application_id"], "stage_key": "lunch"},
    )
    assert response.status_code == 422
    assert "lunch" in response.json()["detail"]


def test_imported_notes_have_no_author(admin_client, db_session):
    cid = new_candidate(admin_client)
    db_session.add(Note(candidate_id=cid, author_id=None, body="From the old notes field."))
    db_session.commit()
    listed = admin_client.get(f"/api/candidates/{cid}/notes").json()
    assert listed[0]["author_name"] is None


def test_note_writes_follow_the_permission_matrix(demo_client, team_client, interviewer_client, admin_client):
    cid = new_candidate(admin_client)
    path = f"/api/candidates/{cid}/notes"
    assert demo_client.post(path, json={"body": "x"}).status_code == 403
    assert interviewer_client.post(path, json={"body": "x"}).status_code == 403
    assert team_client.post(path, json={"body": "x"}).status_code == 201


def test_interviewer_cannot_read_notes_of_unassigned_candidates(admin_client, interviewer_client):
    cid = new_candidate(admin_client)
    admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "private"})
    assert interviewer_client.get(f"/api/candidates/{cid}/notes").status_code == 404


def test_deleting_a_job_keeps_the_note_without_its_label(admin_client, db_session, seed):
    job_id = new_job(admin_client, "Note Survives")
    cid = new_candidate(admin_client)
    applied = admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid})
    application_id = applied.json()["id"]
    admin_client.post(
        f"/api/candidates/{cid}/notes",
        json={"body": "Stage note.", "application_id": application_id, "stage_key": "resume_submitted"},
    )
    assert admin_client.delete(f"/api/jobs/{job_id}").status_code == 200
    db_session.expire_all()
    listed = admin_client.get(f"/api/candidates/{cid}/notes").json()
    assert listed[0]["body"] == "Stage note."
    assert listed[0]["application_id"] is None and listed[0]["job_title"] is None


def test_deleting_a_candidate_removes_their_notes_and_tags(admin_client, db_session):
    cid = new_candidate(admin_client)
    admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "bye"})
    admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "bye"})
    assert admin_client.delete(f"/api/candidates/{cid}").status_code == 200
    db_session.expire_all()
    assert db_session.query(Note).filter(Note.candidate_id == cid).count() == 0
    assert db_session.query(CandidateTag).filter(CandidateTag.candidate_id == cid).count() == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_notes_tags.py -q -k "note"`
Expected: the new note tests fail with 404 or 405 (no route yet). `test_models_import_and_map` and the tag tests still pass.

- [ ] **Step 3: Add the routes**

Append to `backend/routers/notes.py`:

```python
def _author_name(author: Optional[User]) -> Optional[str]:
    # Phase B's display_name: a name or a role label, never an email address,
    # because the demo reads these notes too. None stays None so the UI can
    # say "Earlier note" for rows migrated from candidates.notes.
    if author is None:
        return None
    return display_name(author)


def _out(note: Note) -> NoteOut:
    application = note.application
    return NoteOut(
        id=note.id,
        candidate_id=note.candidate_id,
        body=note.body,
        created_at=note.created_at,
        author_name=_author_name(note.author),
        application_id=note.application_id,
        job_title=application.job.title if application is not None and application.job is not None else None,
        stage_name=note.stage.name if note.stage is not None else None,
    )


@router.get("/candidates/{candidate_id}/notes", response_model=List[NoteOut])
def list_notes(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> List[NoteOut]:
    """The candidate's notes thread, newest first."""
    candidate_or_404(db, user, candidate_id)
    notes = (
        db.query(Note)
        .options(
            joinedload(Note.author),
            joinedload(Note.stage),
            joinedload(Note.application).joinedload(JobApplication.job),
        )
        .filter(Note.candidate_id == candidate_id)
        .order_by(Note.created_at.desc(), Note.id.desc())
        .all()
    )
    return [_out(note) for note in notes]


@router.post("/candidates/{candidate_id}/notes", response_model=NoteOut, status_code=201)
def add_note(
    candidate_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> NoteOut:
    """Add a note about the person, one of their applications, or one stage of it."""
    candidate_or_404(db, user, candidate_id)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="A note needs some text.")
    if payload.stage_key and payload.application_id is None:
        raise HTTPException(status_code=422, detail="Pick the application a stage note belongs to.")

    application_id: Optional[int] = None
    stage_id: Optional[int] = None
    if payload.application_id is not None:
        application = db.get(JobApplication, payload.application_id)
        if application is None or application.candidate_id != candidate_id:
            raise HTTPException(status_code=422, detail="That application belongs to a different candidate.")
        application_id = application.id
        if payload.stage_key:
            stage = next(
                (s for s in ps.ensure_job_stages(db, application.job_id) if s.key == payload.stage_key),
                None,
            )
            if stage is None:
                raise HTTPException(
                    status_code=422, detail=f"This job has no stage named '{payload.stage_key}'."
                )
            stage_id = stage.id

    note = Note(
        candidate_id=candidate_id,
        application_id=application_id,
        stage_id=stage_id,
        author_id=user.id if user is not None else None,
        body=body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _out(note)
```

- [ ] **Step 4: Run the tests**

Run: `poetry run pytest backend/tests/test_notes_tags.py -q`
Expected: 33 passed. If `test_deleting_a_candidate_removes_their_notes_and_tags` fails with a foreign key error, the candidate has an application (only `new_candidate` without `job_id` is used here, so it should not). Look at the error before changing anything.

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c4.txt`:

```
feat: candidate notes thread, general or per stage

A note is about the person, one application, or one stage of it; the
labels come back with the note so the thread reads on its own. Imported
notes carry no author. Deleting a job keeps the note and drops its
label; deleting the candidate removes notes and tags. Interviewers get
404 on candidates they are not assigned to. Verified: 13 more tests
covering validation, ordering, permissions, visibility, and both delete
paths.
```

```powershell
git add backend/routers/notes.py backend/tests/test_notes_tags.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c4.txt
```

---

### Task 5: Intake service, apply, and manual add with a job

**Files:**
- Create: `backend/services/intake_service.py`
- Modify: `backend/routers/jobs.py` (`apply_to_job`), `backend/routers/candidates.py` (`create_candidate`), `backend/models/candidate.py` (`CandidateUpdate`)
- Test: `backend/tests/test_intake.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_intake.py`:

```python
"""Getting people into a pipeline (ATS Phase C).

Every way in (apply, manual add, resume save, consider for another role) goes
through `intake_service.add_to_job`, so these tests pin that function and then
each route that calls it.
"""
from __future__ import annotations

import pytest

from backend.models.models import Candidate, JobApplication, Note
from backend.services import intake_service

from .intake_helpers import application_id_for, client_for_role, new_candidate, new_job, unique
from .conftest import SEED_EMAIL_DOMAIN


@pytest.fixture(scope="module")
def team_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "hiring_team")


@pytest.fixture(scope="module")
def interviewer_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "interviewer")


def test_add_to_job_starts_the_pipeline_and_is_idempotent(admin_client, db_session):
    job_id = new_job(admin_client)
    cid = new_candidate(admin_client)
    application, created = intake_service.add_to_job(db_session, cid, job_id, source="referral")
    db_session.commit()
    assert created is True
    assert application.status == "active"
    again, created_again = intake_service.add_to_job(db_session, cid, job_id)
    assert created_again is False and again.id == application.id
    detail = admin_client.get(f"/api/applications/{application.id}").json()
    assert detail["current_stage_key"] == "resume_submitted"


def test_add_to_job_sets_position_applied_only_when_blank(admin_client, db_session):
    job_id = new_job(admin_client)
    cid = new_candidate(admin_client, position_applied="Already Chosen")
    intake_service.add_to_job(db_session, cid, job_id)
    db_session.commit()
    assert db_session.get(Candidate, cid).position_applied == "Already Chosen"


@pytest.mark.parametrize("missing", ["job", "candidate"])
def test_add_to_job_names_what_is_missing(admin_client, db_session, missing):
    job_id = new_job(admin_client) if missing == "candidate" else 99999999
    cid = new_candidate(admin_client) if missing == "job" else "00000000-0000-4000-8000-00000000beef"
    with pytest.raises(intake_service.IntakeError) as caught:
        intake_service.add_to_job(db_session, cid, job_id)
    assert caught.value.status_code == 404
    assert missing in caught.value.detail.lower()


def test_apply_still_refuses_a_duplicate(admin_client):
    job_id = new_job(admin_client)
    cid = new_candidate(admin_client)
    assert admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid}).status_code == 200
    second = admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid})
    assert second.status_code == 400
    assert second.json()["detail"] == "Already applied to this job"


def test_consider_for_another_role_gives_one_person_two_pipelines(admin_client):
    first_job, second_job = new_job(admin_client), new_job(admin_client)
    cid = new_candidate(admin_client, job_id=first_job)
    response = admin_client.post(
        f"/api/jobs/{second_job}/apply", json={"candidate_id": cid, "source": "internal"}
    )
    assert response.status_code == 200, response.text
    rows = admin_client.get(f"/api/jobs/applications/{cid}").json()
    assert sorted(r["job_id"] for r in rows) == sorted([first_job, second_job])
    assert all(r["current_stage_key"] == "resume_submitted" for r in rows)


def test_manual_add_with_a_job_lands_at_stage_one(admin_client, db_session):
    job_id = new_job(admin_client, "Manual Add")
    cid = new_candidate(admin_client, job_id=job_id)
    application_id = application_id_for(admin_client, cid, job_id)
    detail = admin_client.get(f"/api/applications/{application_id}").json()
    assert detail["current_stage_key"] == "resume_submitted"
    assert db_session.get(Candidate, cid).position_applied.startswith("Manual Add")


def test_manual_add_with_an_unknown_job_creates_nothing(admin_client, db_session):
    email = f"{unique('nojob')}@{SEED_EMAIL_DOMAIN}"
    response = admin_client.post(
        "/api/candidates/",
        json={"first_name": "No", "last_name": "Job", "email": email, "job_id": 99999999},
    )
    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.query(Candidate).filter(Candidate.email == email).count() == 0


def test_manual_add_notes_become_the_first_note(admin_client, admin_user, db_session):
    cid = new_candidate(admin_client, notes="  Met at the meetup.  ")
    db_session.expire_all()
    assert db_session.get(Candidate, cid).notes is None
    notes = db_session.query(Note).filter(Note.candidate_id == cid).all()
    assert [n.body for n in notes] == ["Met at the meetup."]
    assert notes[0].author_id == admin_user.id


def test_update_no_longer_writes_the_old_notes_column(admin_client, db_session):
    cid = new_candidate(admin_client)
    response = admin_client.put(f"/api/candidates/{cid}", json={"notes": "ignored", "headline": "Kept"})
    assert response.status_code == 200, response.text
    db_session.expire_all()
    candidate = db_session.get(Candidate, cid)
    assert candidate.notes is None and candidate.headline == "Kept"


def test_intake_follows_the_permission_matrix(team_client, interviewer_client, demo_client, admin_client):
    job_id = new_job(admin_client)
    def payload():
        return {"first_name": "Perm", "last_name": "Check", "email": f"{unique('perm')}@{SEED_EMAIL_DOMAIN}"}

    assert demo_client.post("/api/candidates/", json=payload()).status_code == 403
    assert interviewer_client.post("/api/candidates/", json=payload()).status_code == 403
    created = team_client.post("/api/candidates/", json={**payload(), "job_id": job_id})
    assert created.status_code == 200, created.text

    cid = new_candidate(admin_client)
    assert interviewer_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid}).status_code == 403
    assert team_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid}).status_code == 200
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_intake.py -q`
Expected: collection error, `ImportError: cannot import name 'intake_service'`

- [ ] **Step 3: Write the intake service**

Create `backend/services/intake_service.py`:

```python
"""Putting a candidate on a job's pipeline (ATS Phase C).

The one way in. `apply_to_job`, `create_candidate` with a job, the resume
save path, and "Consider for another role" all call `add_to_job`, so a new
application always starts at the first enabled round with the candidate's
derived status synced, however it arrived. Like `pipeline_service`, nothing
here commits: callers compose and commit once.
"""
from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from backend.models.models import Candidate, Job, JobApplication
from backend.services import pipeline_service as ps


class IntakeError(Exception):
    """A request the caller should see as an HTTP error, with a plain-English reason."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def add_to_job(
    db: Session,
    candidate_id: str,
    job_id: int,
    source: Optional[str] = "direct",
    cover_letter: Optional[str] = None,
) -> Tuple[JobApplication, bool]:
    """The candidate's application to this job, and whether it was just created.

    One application per candidate per job (spec decision 2): an existing one is
    returned untouched, whatever its status.
    """
    job = db.get(Job, job_id)
    if job is None:
        raise IntakeError(404, "Job not found")
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise IntakeError(404, "Candidate not found")

    existing = (
        db.query(JobApplication)
        .filter(JobApplication.job_id == job_id, JobApplication.candidate_id == candidate_id)
        .first()
    )
    if existing is not None:
        return existing, False

    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        cover_letter=cover_letter,
        source=source or "direct",
    )
    db.add(application)
    job.applications = (job.applications or 0) + 1
    db.flush()
    ps.start_application(db, application)
    if not (candidate.position_applied or "").strip():
        candidate.position_applied = job.title
    return application, True
```

- [ ] **Step 4: Route `apply_to_job` through it**

In `backend/routers/jobs.py`, replace the whole body of `apply_to_job` (keep the decorator and the plain `def` signature from Phase A) with:

```python
    """Apply to a job. One application per candidate per job (spec decision 2)."""
    from ..services import intake_service

    logger = logging.getLogger("backend.routers.jobs")
    try:
        db_application, created = intake_service.add_to_job(
            db,
            application.candidate_id,
            job_id,
            source=application.source or "direct",
            cover_letter=application.cover_letter,
        )
    except intake_service.IntakeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if not created:
        raise HTTPException(status_code=400, detail="Already applied to this job")
    db.commit()
    db.refresh(db_application)

    logger.info(f"Application created: job_id={job_id}, candidate_id={application.candidate_id}")

    return JobApplicationResponse(
        id=db_application.id,
        job_id=db_application.job_id,
        candidate_id=db_application.candidate_id,
        status=db_application.status,
        applied_at=db_application.applied_at.isoformat(),
        source=db_application.source,
    )
```

- [ ] **Step 5: Manual add with a job, notes as the first note**

In `backend/routers/candidates.py`:

Add to the imports:

```python
from ..models.models import Candidate, CandidateSkill, Job, Note, Resume, User
from ..services import intake_service
from ..utils.auth import get_optional_user
```

(merge into the existing `from ..models.models import ...` line rather than adding a second one). Replace the whole `create_candidate` function, decorator included, with:

```python
@router.post("/", response_model=CandidateResponse)
def create_candidate(
    candidate: CandidateCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Create a candidate.

    With `job_id`, they start that job's pipeline in the same transaction
    (ATS Phase C); an unknown job is a 404 and nothing is created. `notes`
    becomes their first note rather than the read-only `candidates.notes`.
    """
    existing_candidate = db.query(Candidate).filter(Candidate.email == candidate.email).first()
    if existing_candidate:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate with email {candidate.email} already exists"
        )

    job = None
    if candidate.job_id is not None:
        job = db.get(Job, candidate.job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"No job with ID {candidate.job_id} exists.")

    db_candidate = Candidate(
        first_name=candidate.first_name,
        last_name=candidate.last_name,
        email=candidate.email,
        phone=candidate.phone,
        location=candidate.location,
        headline=candidate.headline,
        source=candidate.source.value if candidate.source else None,
        status=candidate.status.value if isinstance(candidate.status, CandidateStatus) else candidate.status,
        position_applied=candidate.position_applied,
        job_id=candidate.job_id,
    )
    db.add(db_candidate)
    db.flush()

    if candidate.notes and candidate.notes.strip():
        db.add(
            Note(
                candidate_id=db_candidate.id,
                author_id=user.id if user is not None else None,
                body=candidate.notes.strip(),
            )
        )
    if job is not None:
        intake_service.add_to_job(db, db_candidate.id, job.id, source=db_candidate.source or "direct")

    db.commit()
    db.refresh(db_candidate)
    return db_candidate
```

- [ ] **Step 6: Make `candidates.notes` read-only through the API**

In `backend/models/candidate.py`, delete the line `notes: Optional[str] = None` from `CandidateUpdate` only. Leave `CandidateCreate` and `CandidateResponse` alone. Add this comment where the line was:

```python
    # No `notes`: candidates.notes is read-only since ATS Phase C. Notes live
    # in the notes table (POST /api/candidates/{id}/notes).
```

- [ ] **Step 7: Run the tests**

Run: `poetry run pytest backend/tests/test_intake.py backend/tests/test_pipeline.py backend/tests/test_notes_tags.py -q`
Expected: all pass (test_intake: 11).

- [ ] **Step 8: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c5.txt`:

```
feat: one intake path; manual add and apply both start the pipeline

intake_service.add_to_job is now the only way an application is created,
so every route starts it at the first enabled round and syncs the
candidate's status. Adding a candidate with a job does both in one
transaction (an unknown job creates nothing), and the old notes field on
create becomes their first note. candidates.notes can no longer be
written through the API. Consider for another role is just a second
application: one person, one profile, many pipelines.
```

```powershell
git add backend/services/intake_service.py backend/routers/jobs.py backend/routers/candidates.py backend/models/candidate.py backend/tests/test_intake.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c5.txt
```

---

### Task 6: Resume save adds to a job; staff roles can upload

**Files:**
- Modify: `backend/routers/resume.py` (`require_write_access_for_save`, `SaveCandidateResponse`, `save_candidate_from_parse`), `backend/utils/parse_quota.py`
- Test: `backend/tests/test_intake.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_intake.py`:

```python
import asyncio
import json
from types import SimpleNamespace

from backend.utils import parse_quota

SAVE_PATH = "/api/resume/save-candidate"


def _save_form(email: str, job_id=None):
    data = {
        "parsed_data": json.dumps(
            {
                "personal_info": {"name": "Upload Intake", "email": email},
                "skills": ["Python"],
                "experience": [{"company": "Analytical Engines", "title": "Engineer"}],
            }
        )
    }
    if job_id is not None:
        data["job_id"] = str(job_id)
    return {"files": {"file": ("resume.txt", b"Upload Intake. Engineer.", "text/plain")}, "data": data}


def test_save_with_a_job_lands_at_stage_one(admin_client):
    job_id = new_job(admin_client, "Upload Target")
    form = _save_form(f"{unique('upload')}@{SEED_EMAIL_DOMAIN}", job_id)
    response = admin_client.post(SAVE_PATH, **form)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["application_id"] and body["already_in_pipeline"] is False
    detail = admin_client.get(f"/api/applications/{body['application_id']}").json()
    assert detail["job_id"] == job_id
    assert detail["current_stage_key"] == "resume_submitted"

    # Saving the same person again to the same job is not an error.
    again = admin_client.post(SAVE_PATH, **form).json()
    assert again["application_id"] == body["application_id"]
    assert again["already_in_pipeline"] is True


def test_save_without_a_job_is_unchanged(admin_client):
    response = admin_client.post(SAVE_PATH, **_save_form(f"{unique('nojob')}@{SEED_EMAIL_DOMAIN}"))
    assert response.status_code == 200, response.text
    assert response.json()["application_id"] is None


def test_save_with_an_unknown_job_stores_nothing(admin_client, db_session):
    email = f"{unique('badjob')}@{SEED_EMAIL_DOMAIN}"
    response = admin_client.post(SAVE_PATH, **_save_form(email, 99999999))
    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.query(Candidate).filter(Candidate.email == email).count() == 0


def test_hiring_team_can_save_and_interviewers_cannot(team_client, interviewer_client):
    ok = team_client.post(SAVE_PATH, **_save_form(f"{unique('team')}@{SEED_EMAIL_DOMAIN}"))
    assert ok.status_code == 200, ok.text
    refused = interviewer_client.post(SAVE_PATH, **_save_form(f"{unique('int')}@{SEED_EMAIL_DOMAIN}"))
    assert refused.status_code == 403


def test_roles_that_add_candidates_skip_the_parse_quota(monkeypatch):
    calls = []

    async def fake_redis():
        calls.append(1)
        raise RuntimeError("the quota should not have been checked")

    monkeypatch.setattr("backend.utils.redis_client.get_redis_client", fake_redis)
    monkeypatch.setattr(parse_quota, "get_settings", lambda: SimpleNamespace(parse_daily_limit=20))
    request = SimpleNamespace(headers={}, client=None)

    for role in ("admin", "hiring_manager", "hiring_team"):
        asyncio.run(parse_quota.enforce_parse_quota(request, current_user=SimpleNamespace(role=role)))
    assert calls == []

    asyncio.run(parse_quota.enforce_parse_quota(request, current_user=SimpleNamespace(role="interviewer")))
    assert calls == [1]  # interviewers are counted like anyone else
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_intake.py -q -k "save or quota"`
Expected: failures: `KeyError: 'application_id'`, the unknown job saves anyway (200), the hiring team gets 403 from `require_write_access_for_save` if Phase B gated `save-candidate` that way (otherwise 200), and `calls == [1]` for `hiring_team`.

- [ ] **Step 3: Exempt `CANDIDATES_ADD` roles from the parse quota**

In `backend/utils/parse_quota.py`, change the import line and the first check in `enforce_parse_quota`:

```python
from backend.utils.auth import get_optional_user
from backend.utils.config import get_settings
from backend.utils.permissions import CANDIDATES_ADD, can
```

```python
    # Staff who add candidates are exempt: a hiring team bulk upload would
    # otherwise stop at the anonymous daily cap (ATS Phase C).
    if current_user is not None and can(current_user.role, CANDIDATES_ADD):
        return
```

Update the module docstring sentence "Admins are exempt." to "Roles that can add candidates are exempt."

- [ ] **Step 4: Let `CANDIDATES_ADD` roles save from a parse**

In `backend/routers/resume.py`, change the auth import to:

```python
from backend.utils.auth import get_optional_user
from backend.utils.permissions import CANDIDATES_ADD, can
```

and in `require_write_access_for_save`, replace

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
        detail="Saving a parsed resume requires an account that can add candidates.",
    )
```

Then grep for any other use of `ROLE_ADMIN` in `resume.py` (`Select-String -Path backend/routers/resume.py -Pattern ROLE_ADMIN`). If there is one, leave it and restore `ROLE_ADMIN` to the import.

- [ ] **Step 5: `job_id` on save-candidate**

In `backend/routers/resume.py`, extend `SaveCandidateResponse`:

```python
class SaveCandidateResponse(BaseModel):
    """API response model for saving a reviewed parse as a candidate."""
    success: bool = True
    candidate_id: Optional[str] = None
    resume_id: Optional[int] = None
    # ATS Phase C: set when the save also put them on a job's pipeline.
    application_id: Optional[int] = None
    already_in_pipeline: bool = False
    message: str = "Candidate saved"
```

Add `job_id: Optional[int] = Form(None),` to the `save_candidate_from_parse` signature, directly after `position_applied`. Then, directly after the `try/except` that validates `parsed_data` (before the file-extension check), insert:

```python
    # Checked before anything is stored, so a bad job id never leaves a
    # half-saved candidate behind.
    if job_id is not None and db.get(Job, job_id) is None:
        raise HTTPException(
            status_code=404, detail=f"No job with ID {job_id} exists to add this candidate to."
        )
```

Replace the tail of the function, from `db.commit()` through the `return`, with:

```python
    application_id = None
    already_in_pipeline = False
    if candidate_id and job_id is not None:
        from backend.services import intake_service

        application, created = intake_service.add_to_job(
            db, candidate_id, job_id, source="resume_upload"
        )
        application_id = application.id
        already_in_pipeline = not created
    db.commit()

    return SaveCandidateResponse(
        candidate_id=candidate_id,
        resume_id=resume_id,
        application_id=application_id,
        already_in_pipeline=already_in_pipeline,
        message=(
            "Candidate saved and added to the pipeline" if application_id else "Candidate saved"
        ),
    )
```

Note: this handler stays `async def` because it awaits `store_document`. That is pre-existing and out of Phase C's scope; do not add more sync work to it than this.

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_intake.py backend/tests/test_resume_save_candidate.py backend/tests/test_auth.py -q`
Expected: all pass (test_intake: 16).

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c6.txt`:

```
feat: saving a parsed resume can add the candidate to a job

save-candidate takes an optional job_id: the candidate lands at Resume
submitted on that job, and saving the same person again returns the
existing application instead of failing. A bad job id is refused before
anything is stored. Hiring managers and the hiring team can now save
from a parse and skip the anonymous daily parse cap, which a bulk upload
would otherwise hit; interviewers still cannot.
```

```powershell
git add backend/routers/resume.py backend/utils/parse_quota.py backend/tests/test_intake.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c6.txt
```

---

### Task 7: Bulk advance and reject

**Files:**
- Modify: `backend/models/pipeline.py`, `backend/routers/pipeline.py`
- Test: `backend/tests/test_bulk_export.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_bulk_export.py`:

```python
"""Bulk pipeline moves and the candidate CSV export (ATS Phase C)."""
from __future__ import annotations

import csv
import io

import pytest

from .conftest import SEED_EMAIL_DOMAIN
from .intake_helpers import client_for_role, job_with_applicants, new_candidate, unique


@pytest.fixture(scope="module")
def team_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "hiring_team")


@pytest.fixture(scope="module")
def interviewer_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "interviewer")


def _bulk(client, action, ids, note=None):
    return client.post(f"/api/applications/bulk/{action}", json={"application_ids": ids, "note": note})


def test_bulk_advance_moves_everyone(admin_client):
    _, _, app_ids = job_with_applicants(admin_client, 2)
    response = _bulk(admin_client, "advance", app_ids)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "action": "advance",
        "succeeded": 2,
        "failed": 0,
        "results": [
            {
                "application_id": app_id,
                "ok": True,
                "detail": None,
                "candidate_name": "Intake Test",
                "status": "active",
                "current_stage_key": "hm_review",
            }
            for app_id in app_ids
        ],
    }


def test_bulk_reports_each_failure_and_keeps_the_successes(admin_client):
    _, _, (a, b) = job_with_applicants(admin_client, 2)
    admin_client.post(f"/api/applications/{b}/reject", json={})
    body = _bulk(admin_client, "advance", [a, b, 99999999]).json()
    assert (body["succeeded"], body["failed"]) == (1, 2)
    by_id = {r["application_id"]: r for r in body["results"]}
    assert by_id[a]["ok"] is True
    assert "already rejected" in by_id[b]["detail"]
    assert by_id[99999999]["detail"] == "Application not found."
    # The success was committed despite the failures around it.
    assert admin_client.get(f"/api/applications/{a}").json()["current_stage_key"] == "hm_review"


def test_bulk_reject_records_the_reason(admin_client):
    _, _, app_ids = job_with_applicants(admin_client, 2)
    body = _bulk(admin_client, "reject", app_ids, note="Role filled internally.").json()
    assert body["succeeded"] == 2
    detail = admin_client.get(f"/api/applications/{app_ids[0]}").json()
    assert detail["status"] == "rejected"
    failed = next(s for s in detail["stages"] if s["status"] == "failed")
    assert failed["note"] == "Role filled internally."


def test_duplicate_ids_are_processed_once(admin_client):
    _, _, (a,) = job_with_applicants(admin_client, 1)
    body = _bulk(admin_client, "advance", [a, a]).json()
    assert body["succeeded"] == 1 and len(body["results"]) == 1


def test_only_advance_and_reject_exist_in_bulk(admin_client):
    _, _, (a,) = job_with_applicants(admin_client, 1)
    response = _bulk(admin_client, "skip", [a])
    # 404 from the bulk route, not a 422 from the single-application route
    # trying to read "bulk" as an id: proves the route order.
    assert response.status_code == 404
    assert "advance or reject" in response.json()["detail"]


@pytest.mark.parametrize("ids", [[], list(range(1, 102))])
def test_bulk_size_limits(admin_client, ids):
    assert _bulk(admin_client, "advance", ids).status_code == 422


def test_bulk_follows_the_permission_matrix(admin_client, demo_client, interviewer_client, team_client):
    _, _, (a,) = job_with_applicants(admin_client, 1)
    assert _bulk(demo_client, "advance", [a]).status_code == 403
    assert _bulk(interviewer_client, "advance", [a]).status_code == 403
    assert _bulk(team_client, "advance", [a]).status_code == 200
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_bulk_export.py -q`
Expected: the bulk tests fail with 422 (the single-application route parses `bulk` as an id) or 404.

- [ ] **Step 3: Add the request and response shapes**

Append to `backend/models/pipeline.py`:

```python
class BulkTransitionRequest(BaseModel):
    application_ids: List[int] = Field(min_length=1, max_length=100)
    note: Optional[str] = Field(default=None, max_length=2000)


class BulkItemResult(BaseModel):
    application_id: int
    ok: bool
    detail: Optional[str] = None
    candidate_name: Optional[str] = None
    status: Optional[str] = None
    current_stage_key: Optional[str] = None


class BulkTransitionResponse(BaseModel):
    action: str
    succeeded: int
    failed: int
    results: List[BulkItemResult]
```

- [ ] **Step 4: Add the bulk route above the single-application route**

In `backend/routers/pipeline.py`, add `BulkItemResult`, `BulkTransitionRequest` and `BulkTransitionResponse` to the `from ..models.pipeline import (...)` list. Insert this block **immediately above** `@router.post("/applications/{application_id}/{action}", ...)`:

```python
BULK_ACTIONS = ("advance", "reject")


@router.post("/applications/bulk/{action}", response_model=BulkTransitionResponse)
def bulk_transition(
    action: str,
    payload: BulkTransitionRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> BulkTransitionResponse:
    """Advance or reject many applications; each one succeeds or fails on its own.

    Every application runs in its own savepoint, so one that a colleague
    already rejected is reported by name instead of blocking the rest (ATS
    Phase C decision). Declared above the single-application route on
    purpose: that route's `{application_id}` would otherwise capture "bulk"
    and answer 422.
    """
    if action not in BULK_ACTIONS:
        raise HTTPException(status_code=404, detail=f"Bulk '{action}' is not available. Use advance or reject.")
    fn = ps.ACTIONS[action]
    note = (payload.note or "").strip() or None
    actor_id = user.id if user is not None else None

    results: list[BulkItemResult] = []
    for application_id in dict.fromkeys(payload.application_ids):
        application = (
            db.query(JobApplication)
            .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
            .filter(JobApplication.id == application_id)
            .first()
        )
        if application is None:
            results.append(BulkItemResult(application_id=application_id, ok=False, detail="Application not found."))
            continue
        candidate = db.get(Candidate, application.candidate_id)
        name = _name(candidate) if candidate else "Unnamed candidate"

        savepoint = db.begin_nested()
        try:
            ps.ensure_application_stages(db, application)
            fn(db, application, actor_id=actor_id, note=note)
            savepoint.commit()
        except ps.PipelineError as exc:
            savepoint.rollback()
            results.append(
                BulkItemResult(application_id=application_id, ok=False, candidate_name=name, detail=str(exc))
            )
            continue

        current = ps.current_stage(application)
        results.append(
            BulkItemResult(
                application_id=application_id,
                ok=True,
                candidate_name=name,
                status=application.status,
                current_stage_key=current.stage.key if current else None,
            )
        )

    db.commit()
    succeeded = sum(1 for r in results if r.ok)
    return BulkTransitionResponse(
        action=action, succeeded=succeeded, failed=len(results) - succeeded, results=results
    )
```

- [ ] **Step 5: Run the tests**

Run: `poetry run pytest backend/tests/test_bulk_export.py backend/tests/test_pipeline.py backend/tests/test_auth.py -q`
Expected: all pass (test_bulk_export: 8).

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c7.txt`:

```
feat: bulk advance and reject with per-candidate results

Each application moves in its own savepoint, so a batch where a colleague
already rejected two people moves the rest and names the two instead of
refusing everything. Only advance and reject exist in bulk; skip and
decline stay one at a time. The route sits above the single-application
route so "bulk" is never read as an id (a test pins the 404). Verified:
8 tests covering mixed outcomes, the reject note, dedupe, limits, and
the permission matrix.
```

```powershell
git add backend/models/pipeline.py backend/routers/pipeline.py backend/tests/test_bulk_export.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c7.txt
```

---

### Task 8: Job filter and CSV export

**Files:**
- Modify: `backend/routers/candidates.py`
- Test: `backend/tests/test_bulk_export.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_bulk_export.py`:

```python
EXPECTED_HEADER = [
    "First name", "Last name", "Email", "Phone", "Location", "Current role",
    "Current company", "Source", "Status", "Tags", "Applications", "Added",
]


def _rows(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    return list(csv.reader(io.StringIO(response.text.lstrip("\ufeff"))))


def test_export_header_has_no_scores(client):
    header = _rows(client.get("/api/candidates/export.csv"))[0]
    assert header == EXPECTED_HEADER
    assert not any("score" in h.lower() or "match" in h.lower() for h in header)


def test_export_respects_the_job_filter(client, seed):
    rows = _rows(client.get(f"/api/candidates/export.csv?job_id={seed['job_id']}"))
    emails = {row[2] for row in rows[1:]}
    assert f"ada@{SEED_EMAIL_DOMAIN}" in emails
    assert f"alan@{SEED_EMAIL_DOMAIN}" not in emails


def test_export_lists_tags_and_applications(admin_client):
    job_id, (cid,), _ = job_with_applicants(admin_client, 1)
    admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "export-check"})
    email = admin_client.get(f"/api/candidates/{cid}").json()["email"]
    rows = _rows(admin_client.get(f"/api/candidates/export.csv?keyword={email}"))
    assert len(rows) == 2
    row = dict(zip(rows[0], rows[1]))
    assert row["Tags"] == "export-check"
    assert row["Applications"].endswith("(Resume submitted)")


def test_export_neutralizes_spreadsheet_formulas(admin_client):
    email = f"{unique('formula')}@{SEED_EMAIL_DOMAIN}"
    admin_client.post(
        "/api/candidates/",
        json={"first_name": '=HYPERLINK("http://x","y")', "last_name": "@risk", "email": email},
    )
    rows = _rows(admin_client.get(f"/api/candidates/export.csv?keyword={email}"))
    row = dict(zip(rows[0], rows[1]))
    assert row["First name"].startswith("'=")
    assert row["Last name"] == "'@risk"


def test_interviewer_export_contains_only_assigned_candidates(interviewer_client):
    rows = _rows(interviewer_client.get("/api/candidates/export.csv"))
    assert rows == [EXPECTED_HEADER]


def test_candidate_list_filters_by_job(client, seed):
    body = client.get(f"/api/candidates/?job_id={seed['job_id']}&page_size=100").json()
    ids = {c["id"] for c in body["results"]}
    assert seed["candidate_id"] in ids
    assert seed["candidate_ids"][2] not in ids
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poetry run pytest backend/tests/test_bulk_export.py -q -k "export or filters"`
Expected: the export tests fail with 404, because `/{candidate_id}` captures `export.csv` and finds no such candidate. `test_candidate_list_filters_by_job` fails because the filter is ignored.

- [ ] **Step 3: One filtered query for the list and the export**

In `backend/routers/candidates.py`, add to the imports:

```python
import csv
import io
from collections import defaultdict

from fastapi import Response
from sqlalchemy import and_

from ..models.models import ApplicationStage, CandidateTag, JobApplication, PipelineStage
from ..services.access_service import visible_candidate_ids
```

(merge model names into the existing `from ..models.models import ...` line and `Response` into the `fastapi` import line). Add this helper above `create_candidate`:

```python
def _filtered_candidates(
    db: Session,
    user: Optional[User],
    *,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    position: Optional[str] = None,
    skills: Optional[str] = None,
    job_id: Optional[int] = None,
):
    """The candidate query behind both the list and the CSV export.

    One function so the export can never contain a row the list would hide,
    including the interviewer visibility rule (ATS Phase B and C).
    """
    query = db.query(Candidate)

    visible = visible_candidate_ids(db, user)
    if visible is not None:
        query = query.filter(Candidate.id.in_(visible))

    if keyword:
        # Name, email, *and* the fields a recruiter actually searches by.
        term = f"%{keyword}%"
        # EXISTS rather than a join: joining candidate_skills multiplies a
        # candidate by their skill count, which would both duplicate rows
        # and inflate the `total` used for pagination.
        has_skill = (
            db.query(CandidateSkill)
            .filter(
                CandidateSkill.candidate_id == Candidate.id,
                CandidateSkill.skill_name.ilike(term),
            )
            .exists()
        )
        query = query.filter(
            or_(
                Candidate.first_name.ilike(term),
                Candidate.last_name.ilike(term),
                Candidate.email.ilike(term),
                Candidate.headline.ilike(term),
                Candidate.position_applied.ilike(term),
                Candidate.current_position.ilike(term),
                Candidate.current_company.ilike(term),
                Candidate.location.ilike(term),
                has_skill,
            )
        )

    if status:
        query = query.filter(Candidate.status == status)

    if position:
        query = query.filter(Candidate.position_applied.ilike(f"%{position}%"))

    if skills:
        for skill in [s.strip() for s in skills.split(",")]:
            query = query.filter(
                Candidate.headline.ilike(f"%{skill}%") | Candidate.notes.ilike(f"%{skill}%")
            )

    if job_id is not None:
        applied = (
            db.query(JobApplication)
            .filter(JobApplication.candidate_id == Candidate.id, JobApplication.job_id == job_id)
            .exists()
        )
        query = query.filter(applied)

    return query
```

- [ ] **Step 4: Use it in `search_candidates`**

In `search_candidates`:

1. Add two parameters after `skills: Optional[str] = None,`:
   ```python
       job_id: Optional[int] = None,
   ```
   and after `db: Session = Depends(get_db),`:
   ```python
       user: Optional[User] = Depends(get_optional_user),
   ```
   If Phase B already added a user dependency under another name, keep Phase B's and pass that name below instead.
2. Replace everything from `query = db.query(Candidate)` down to (but not including) the `# Apply sorting` comment with:
   ```python
           query = _filtered_candidates(
               db,
               user,
               keyword=keyword,
               status=status.value if status else None,
               position=position,
               skills=skills,
               job_id=job_id,
           )
   ```
   If Phase B added a `visible_candidate_ids` filter in that span, it goes away with the replaced block. The helper applies the same filter.

- [ ] **Step 5: The export route, declared before `/{candidate_id}`**

Insert this block **directly after the `get_skills_breakdown` function and before** `@router.get("/{candidate_id}", ...)`:

```python
EXPORT_HEADER = [
    "First name", "Last name", "Email", "Phone", "Location", "Current role",
    "Current company", "Source", "Status", "Tags", "Applications", "Added",
]
EXPORT_ROW_LIMIT = 5000
_APPLICATION_LABELS = {
    "active": "In progress",
    "hired": "Hired",
    "rejected": "Rejected",
    "declined": "Offer declined",
    "withdrawn": "Withdrawn",
}


def _csv_cell(value) -> str:
    """A cell Excel and Sheets will show as text, never run as a formula."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


@router.get(
    "/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "The filtered candidate list. No scores."}},
)
def export_candidates_csv(
    keyword: Optional[str] = None,
    status: Optional[CandidateStatus] = None,
    job_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> Response:
    """The candidate list as CSV, with the same filters as the list (ATS Phase C).

    Deliberately contains no match scores and no notes. Declared before
    `/{candidate_id}`, which would otherwise read "export.csv" as an id.
    """
    candidates = (
        _filtered_candidates(db, user, keyword=keyword, status=status.value if status else None, job_id=job_id)
        .order_by(Candidate.last_name, Candidate.first_name, Candidate.id)
        .limit(EXPORT_ROW_LIMIT)
        .all()
    )
    ids = [c.id for c in candidates]

    tags_by: dict[str, list[str]] = defaultdict(list)
    applications_by: dict[str, list[str]] = defaultdict(list)
    if ids:
        for candidate_id, tag in (
            db.query(CandidateTag.candidate_id, CandidateTag.tag)
            .filter(CandidateTag.candidate_id.in_(ids))
            .order_by(CandidateTag.tag)
        ):
            tags_by[candidate_id].append(tag)
        rows = (
            db.query(JobApplication.candidate_id, Job.title, JobApplication.status, PipelineStage.name)
            .join(Job, Job.id == JobApplication.job_id)
            .outerjoin(
                ApplicationStage,
                and_(
                    ApplicationStage.application_id == JobApplication.id,
                    ApplicationStage.status == "in_progress",
                ),
            )
            .outerjoin(PipelineStage, PipelineStage.id == ApplicationStage.stage_id)
            .filter(JobApplication.candidate_id.in_(ids))
            .order_by(Job.title)
            .all()
        )
        for candidate_id, title, app_status, stage_name in rows:
            where = stage_name if app_status == "active" and stage_name else _APPLICATION_LABELS.get(app_status, app_status)
            applications_by[candidate_id].append(f"{title} ({where})")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_HEADER)
    for c in candidates:
        writer.writerow(
            [
                _csv_cell(value)
                for value in (
                    c.first_name,
                    c.last_name,
                    c.email,
                    c.phone,
                    c.location,
                    c.current_position,
                    c.current_company,
                    c.source,
                    c.status,
                    "; ".join(tags_by[c.id]),
                    "; ".join(applications_by[c.id]),
                    c.created_at.date().isoformat() if c.created_at else "",
                )
            ]
        )

    filename = f"candidates-{datetime.utcnow().date().isoformat()}.csv"
    # The BOM makes Excel read the file as UTF-8, so accented names survive.
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

Let interviewers reach the export (it filters them itself through `visible_candidate_ids`). In `backend/services/access_service.py`, add this entry to `INTERVIEWER_PATHS` **above** the `/api/candidates/(?P<id>...)` entry. The gate stops at the first match, and below it `export.csv` would be read as a candidate id the interviewer cannot see and answer 404, failing `test_interviewer_export_contains_only_assigned_candidates`:

```python
        (r"/api/candidates/export\.csv", None),  # the handler filters by visible_candidate_ids
```

- [ ] **Step 6: Run the tests**

Run: `poetry run pytest backend/tests/test_bulk_export.py backend/tests/test_candidate_search.py backend/tests/test_enhanced_candidate_search.py -q`
Expected: all pass (test_bulk_export: 14). The two search suites prove the refactor kept the keyword behavior.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c8.txt`:

```
feat: candidate list job filter and CSV export

The list and the export now share one filtered query, so the export can
never contain someone the list would hide, interviewers included. The
CSV carries tags and each application with its current stage, and no
scores or notes. Cells that would start a spreadsheet formula are
prefixed so an imported name can never execute. Verified: 6 export and
filter tests plus both existing candidate search suites unchanged.
```

```powershell
git add backend/routers/candidates.py backend/tests/test_bulk_export.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c8.txt
```

---

### Task 9: Job card counts from the pipeline, then contract and types

**Files:**
- Modify: `backend/models/job.py`, `backend/routers/jobs.py`
- Regenerate: `backend/tests/golden/api_response_shapes.json`, `openapi.json`, `web/src/lib/schema.d.ts`
- Test: `backend/tests/test_intake.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_intake.py`:

```python
def test_jobs_report_active_applications_from_the_pipeline(admin_client):
    job_id = new_job(admin_client, "Count Check")
    first = new_candidate(admin_client, job_id=job_id)
    new_candidate(admin_client, job_id=job_id)
    admin_client.post(f"/api/applications/{application_id_for(admin_client, first, job_id)}/reject", json={})

    detail = admin_client.get(f"/api/jobs/{job_id}").json()
    assert detail["active_applications"] == 1
    assert detail["applications"] == 2  # the stored all-time counter is unchanged
    listed = admin_client.get("/api/jobs/?page_size=100&keyword=Count Check").json()["results"]
    assert next(j for j in listed if j["id"] == job_id)["active_applications"] == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `poetry run pytest backend/tests/test_intake.py -q -k active_applications`
Expected: FAIL with `KeyError: 'active_applications'`

- [ ] **Step 3: Add the field**

In `backend/models/job.py`, in `JobResponse`, directly after `applications: int = 0`:

```python
    # ATS Phase C: applications still in progress, counted from the pipeline.
    # `applications` stays the stored all-time counter.
    active_applications: int = 0
```

- [ ] **Step 4: Fill it on the list and the detail**

In `backend/routers/jobs.py`, change `from sqlalchemy import desc, asc` to `from sqlalchemy import desc, asc, func` and add `Dict` to the `typing` import if it is missing. Add above `create_job`:

```python
def _active_counts(db: Session, job_ids: List[int]) -> Dict[int, int]:
    """Applications still in progress per job, in one query."""
    if not job_ids:
        return {}
    rows = (
        db.query(JobApplication.job_id, func.count(JobApplication.id))
        .filter(JobApplication.job_id.in_(job_ids), JobApplication.status == "active")
        .group_by(JobApplication.job_id)
        .all()
    )
    return {job_id: count for job_id, count in rows}
```

In `search_jobs`, directly after `jobs = query.all()`, add:

```python
    counts = _active_counts(db, [job.id for job in jobs])
    for job in jobs:
        job.active_applications = counts.get(job.id, 0)
```

In `get_job`, directly before `return job`, add:

```python
    job.active_applications = _active_counts(db, [job.id]).get(job.id, 0)
```

- [ ] **Step 5: Run the test**

Run: `poetry run pytest backend/tests/test_intake.py -q`
Expected: 17 passed.

- [ ] **Step 6: Regenerate the contract golden and check it is additions only**

```powershell
$env:UPDATE_API_GOLDEN = "1"
poetry run pytest backend/tests/test_api_contract.py -q
Remove-Item Env:UPDATE_API_GOLDEN
git diff backend/tests/golden/api_response_shapes.json
```

Expected diff: only `+` lines, adding `"active_applications": "int"` under the job shapes (and `application_id`/`already_in_pipeline` under save-candidate if the golden captures it). Any `-` line is a regression. Stop and fix it.

- [ ] **Step 7: Regenerate OpenAPI and the web types**

```powershell
poetry run python scripts/export_openapi.py
poetry run python scripts/export_openapi.py --check
cd web; npm run types:api; cd ..
Select-String -Path web/src/lib/schema.d.ts -Pattern "NoteOut:|CandidateTagsResponse:|TagCount:|BulkTransitionResponse:|active_applications"
```

Expected: `--check` passes. `schema.d.ts` contains `NoteOut`, `CandidateTagsResponse`, `TagCount`, `BulkTransitionResponse`, and `active_applications`. `CandidateUpdate` no longer has `notes`.

- [ ] **Step 8: Run the backend suites touched so far**

```powershell
poetry run pytest backend/tests/test_intake.py backend/tests/test_notes_tags.py backend/tests/test_bulk_export.py backend/tests/test_pipeline.py backend/tests/test_auth.py backend/tests/test_api_contract.py backend/tests/test_openapi_is_current.py backend/tests/test_jobs_admin.py backend/tests/test_resume_save_candidate.py -q
```

Expected: all pass.

- [ ] **Step 9: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c9.txt`:

```
feat: jobs report active applications from the pipeline

The jobs list card will show how many people are still in progress
rather than the stored all-time counter, which never went down when
someone was rejected. Golden contract regenerated (additions only),
openapi.json and the generated web types updated for every Phase C
route.
```

```powershell
git add backend/models/job.py backend/routers/jobs.py backend/tests/test_intake.py backend/tests/golden/api_response_shapes.json openapi.json web/src/lib/schema.d.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c9.txt
```

---

### Task 10: Seed notes and tags

**Files:**
- Modify: `scripts/seed_demo.py`, `backend/tests/test_seed_demo.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_seed_demo.py`:

```python
from scripts.seed_demo import SEED_NOTES, SEED_TAGS, seed_note_for, seed_tags_for
from backend.utils.tags import normalize_tag


def test_seed_tags_are_normalized_and_stable():
    for tag in SEED_TAGS:
        assert normalize_tag(tag) == tag
    emails = [f"person{i}@demo.recruitiq.dev" for i in range(40)]
    first = [seed_tags_for(e) for e in emails]
    assert first == [seed_tags_for(e) for e in emails]
    assert sum(1 for tags in first if tags) >= 15  # a believable share are tagged
    assert all(len(tags) <= 2 for tags in first)


def test_seed_notes_are_stable_and_from_the_fixed_list():
    emails = [f"person{i}@demo.recruitiq.dev" for i in range(40)]
    notes = [seed_note_for(e) for e in emails]
    assert notes == [seed_note_for(e) for e in emails]
    assert all(n is None or n in SEED_NOTES for n in notes)
    assert sum(1 for n in notes if n) >= 8
```

- [ ] **Step 2: Run it to verify it fails**

Run: `poetry run pytest backend/tests/test_seed_demo.py -q`
Expected: FAIL with `ImportError: cannot import name 'SEED_NOTES'`

- [ ] **Step 3: Add the seed functions**

In `scripts/seed_demo.py`, add `CandidateTag`, `Note` and `User` to the `from backend.models.models import (...)` list. Add after `STATUS_TO_STAGE_INDEX`:

```python
# Synthetic tags and notes (ATS Phase C). Keyed on the candidate's email rather
# than their id: ids are random per database, emails are fixed, so every fresh
# database gets the same tags on the same people.
SEED_TAGS = [
    "referral",
    "relocation-ok",
    "remote-only",
    "visa-sponsorship",
    "returning-candidate",
    "strong-sql",
    "leadership",
    "contract-to-hire",
]

SEED_NOTES = [
    "Phone screen went well. Clear on why they want to move.",
    "Open to two office days a week. Prefers mornings for interviews.",
    "Strong portfolio. Ask about the data platform migration they led.",
    "Prefers a start date after the end of the quarter.",
    "Referred by a former colleague on the platform team.",
]


def seed_tags_for(email: str) -> list[str]:
    """Zero to two tags, decided by the email alone."""
    if stable_index(f"tags-{email}", 100) >= 60:
        return []
    picks = {
        SEED_TAGS[stable_index(f"tag-a-{email}", len(SEED_TAGS))],
        SEED_TAGS[stable_index(f"tag-b-{email}", len(SEED_TAGS))],
    }
    return sorted(picks)


def seed_note_for(email: str):
    """One note for about four in ten candidates, or None."""
    if stable_index(f"note-{email}", 100) >= 40:
        return None
    return SEED_NOTES[stable_index(f"note-body-{email}", len(SEED_NOTES))]
```

Add after `seed_pipeline`:

```python
def seed_notes_and_tags(db, candidates: list[Candidate]) -> None:
    """Tags and a candidate-level note, added only where missing (idempotent).

    Authored by the first hiring manager or hiring team user Phase B's seed
    created, so the thread shows a name; null (shown as "Earlier note") if
    there is none.
    """
    author = (
        db.query(User)
        .filter(User.role.in_(("hiring_manager", "hiring_team")))
        .order_by(User.email)
        .first()
    )
    for candidate in candidates:
        email = candidate.email or candidate.id
        for tag in seed_tags_for(email):
            exists = (
                db.query(CandidateTag)
                .filter(CandidateTag.candidate_id == candidate.id, CandidateTag.tag == tag)
                .first()
            )
            if exists is None:
                db.add(CandidateTag(candidate_id=candidate.id, tag=tag))
        body = seed_note_for(email)
        if body is not None:
            exists = (
                db.query(Note)
                .filter(Note.candidate_id == candidate.id, Note.body == body)
                .first()
            )
            if exists is None:
                db.add(
                    Note(candidate_id=candidate.id, author_id=author.id if author else None, body=body)
                )
    db.commit()
```

In `main()`, call it directly after `seed_pipeline(db, candidates, jobs)`:

```python
        seed_notes_and_tags(db, candidates)
```

and extend the summary print with one line after the `applications:` line:

```python
        print(f"  notes: {db.query(Note).count()}  tagged: "
              f"{db.query(CandidateTag.candidate_id).distinct().count()}")
```

- [ ] **Step 4: Run the test**

Run: `poetry run pytest backend/tests/test_seed_demo.py -q`
Expected: all pass.

- [ ] **Step 5: Verify against a fresh database, twice**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
$env:OLLAMA_BASE_URL = "http://localhost:1"
cd backend; poetry run alembic upgrade head; cd ..
poetry run python scripts/seed_demo.py --no-embeddings
docker exec recruitiq-db psql -U admin -d st_scratch -t -c "SELECT (SELECT COUNT(*) FROM notes), (SELECT COUNT(*) FROM candidate_tags)"
poetry run python scripts/seed_demo.py --no-embeddings
docker exec recruitiq-db psql -U admin -d st_scratch -t -c "SELECT (SELECT COUNT(*) FROM notes), (SELECT COUNT(*) FROM candidate_tags)"
```

Expected: both runs print the same two counts (idempotent), with notes between 8 and 25 and tags between 15 and 80.

Then run the whole suite against the scratch database:

```powershell
poetry run pytest -q
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
```

Expected: green apart from the two known embedding tests under the unreachable-Ollama env.

- [ ] **Step 6: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c10.txt`:

```
feat: seed data gives candidates tags and notes

Keyed on email, so every fresh database tags the same people the same
way, and re-running adds nothing. Notes are attributed to the first
seeded hiring manager or hiring team user. All text is synthetic.
Verified: two seed runs on a migrations-only database give identical
counts, and the full suite passes on that database.
```

```powershell
git add scripts/seed_demo.py backend/tests/test_seed_demo.py
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c10.txt
```

---

### Task 11: Web proxy helper and route handlers

**Files:**
- Create: `web/src/lib/proxy.ts`, and the seven route handlers listed in the file structure
- Modify: `web/src/app/api/resume/save/route.ts`

- [ ] **Step 1: The shared forwarder**

Create `web/src/lib/proxy.ts`:

```ts
import "server-only";

import { NextResponse } from "next/server";

import { API_BASE_URL } from "./config";
import { getToken } from "./session";

/**
 * Forward one JSON write to FastAPI with the httpOnly session token.
 *
 * Same contract as the hand-written jobs and applications handlers: the
 * backend's permission gate is the authority, this only attaches the token
 * and passes the status and body through untouched. Phase C has seven of
 * these, so they share one implementation instead of seven copies.
 */
export async function forwardJson(
  upstreamPath: string,
  {
    method,
    body,
    signedOutMessage,
  }: { method: "POST" | "PUT" | "DELETE"; body?: unknown; signedOutMessage: string },
): Promise<NextResponse> {
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ detail: signedOutMessage }, { status: 401 });
  }

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
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  if (upstream.status === 204) return new NextResponse(null, { status: 204 });
  const text = await upstream.text();
  return new NextResponse(text || "{}", {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The request's JSON body, or an empty object when there is none. */
export async function readJson(request: Request): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

/** Candidate ids are UUIDs; anything else never reaches the upstream URL. */
export function isCandidateId(id: string): boolean {
  return /^[0-9a-f-]{1,36}$/i.test(id);
}
```

- [ ] **Step 2: The route handlers**

Create `web/src/app/api/candidates/route.ts`:

```ts
import type { NextRequest } from "next/server";

import { forwardJson, readJson } from "@/lib/proxy";

/** Add a candidate by hand (ATS Phase C). A job_id starts their pipeline too. */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  return forwardJson("/api/candidates/", {
    method: "POST",
    body: await readJson(request),
    signedOutMessage: "Sign in to add candidates.",
  });
}
```

Create `web/src/app/api/candidates/export/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Download the filtered candidate list as CSV.
 *
 * A GET the browser can follow as a plain link. The token lives in an
 * httpOnly cookie, so the browser cannot call FastAPI directly.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const PASSED_THROUGH = ["keyword", "status", "job_id"];

export async function GET(request: NextRequest) {
  const query = new URLSearchParams();
  for (const key of PASSED_THROUGH) {
    const value = request.nextUrl.searchParams.get(key);
    if (value) query.set(key, value);
  }
  const token = await getToken();

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/candidates/export.csv?${query}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  if (!upstream.ok) {
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  }
  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition":
        upstream.headers.get("Content-Disposition") ?? 'attachment; filename="candidates.csv"',
    },
  });
}
```

Create `web/src/app/api/candidates/[id]/notes/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

import { forwardJson, isCandidateId, readJson } from "@/lib/proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!isCandidateId(id)) {
    return NextResponse.json({ detail: "That is not a valid candidate id." }, { status: 400 });
  }
  return forwardJson(`/api/candidates/${id}/notes`, {
    method: "POST",
    body: await readJson(request),
    signedOutMessage: "Sign in to add notes.",
  });
}
```

Create `web/src/app/api/candidates/[id]/tags/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

import { forwardJson, isCandidateId, readJson } from "@/lib/proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!isCandidateId(id)) {
    return NextResponse.json({ detail: "That is not a valid candidate id." }, { status: 400 });
  }
  return forwardJson(`/api/candidates/${id}/tags`, {
    method: "POST",
    body: await readJson(request),
    signedOutMessage: "Sign in to tag candidates.",
  });
}
```

Create `web/src/app/api/candidates/[id]/tags/[tag]/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

import { forwardJson, isCandidateId } from "@/lib/proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function DELETE(
  _request: NextRequest,
  context: { params: Promise<{ id: string; tag: string }> },
) {
  const { id, tag } = await context.params;
  if (!isCandidateId(id) || !/^[a-z0-9-]{1,50}$/.test(tag)) {
    return NextResponse.json({ detail: "That is not a valid tag." }, { status: 400 });
  }
  return forwardJson(`/api/candidates/${id}/tags/${tag}`, {
    method: "DELETE",
    signedOutMessage: "Sign in to tag candidates.",
  });
}
```

Create `web/src/app/api/jobs/[id]/apply/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

import { forwardJson, readJson } from "@/lib/proxy";

/** Put an existing candidate on this job's pipeline ("Consider for another role"). */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!/^\d+$/.test(id)) {
    return NextResponse.json({ detail: "That is not a valid job id." }, { status: 400 });
  }
  return forwardJson(`/api/jobs/${id}/apply`, {
    method: "POST",
    body: await readJson(request),
    signedOutMessage: "Sign in to add candidates to a pipeline.",
  });
}
```

Create `web/src/app/api/applications/bulk/[action]/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

import { forwardJson, readJson } from "@/lib/proxy";

/**
 * Bulk advance or reject. A static `bulk` segment beats the sibling
 * `[id]/[action]` handler in Next's routing, so the two never collide.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const ACTIONS = new Set(["advance", "reject"]);

export async function POST(request: NextRequest, context: { params: Promise<{ action: string }> }) {
  const { action } = await context.params;
  if (!ACTIONS.has(action)) {
    return NextResponse.json({ detail: `Bulk '${action}' is not available.` }, { status: 404 });
  }
  return forwardJson(`/api/applications/bulk/${action}`, {
    method: "POST",
    body: await readJson(request),
    signedOutMessage: "Sign in to move candidates.",
  });
}
```

- [ ] **Step 3: Forward `job_id` on save**

In `web/src/app/api/resume/save/route.ts`, directly after the two `position_applied` lines, add:

```ts
  // ATS Phase C: save straight onto a job's pipeline. Validated here so a
  // malformed id is a readable 400, not a FastAPI 422.
  const jobId = incoming.get("job_id");
  if (typeof jobId === "string" && jobId) {
    if (!/^\d+$/.test(jobId)) {
      return NextResponse.json({ detail: "That is not a valid job id." }, { status: 400 });
    }
    outgoing.set("job_id", jobId);
  }
```

and change the signed-out message `"Sign in as an administrator to save candidates."` to `"Sign in to save candidates."`.

- [ ] **Step 4: Type check and lint**

Run: `cd web; npm run typecheck; npm run lint`
Expected: clean.

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c11.txt`:

```
feat(web): route handlers for intake, notes, tags, bulk, and export

The seven new write paths share one forwarder that attaches the session
token and passes the backend's status through, so the permission gate
stays the only authority. The CSV export is a plain GET the browser can
download. Saving a parsed resume now forwards the chosen job.
```

```powershell
git add web/src/lib/proxy.ts web/src/app/api/candidates "web/src/app/api/jobs/[id]/apply/route.ts" web/src/app/api/applications/bulk web/src/app/api/resume/save/route.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c11.txt
```

---

### Task 12: Pure web helpers, types, and data functions

**Files:**
- Create: `web/src/lib/intake.ts`, `web/src/lib/intake.test.ts`
- Modify: `web/src/lib/domain.ts`, `web/src/lib/data.ts`

- [ ] **Step 1: Add the type aliases**

In `web/src/lib/domain.ts`, after the ATS Phase A aliases, add:

```ts
/** ATS Phase C: notes, tags, and bulk moves. */
export type Note = Schemas["NoteOut"];
export type CandidateTags = Schemas["CandidateTagsResponse"];
export type BulkTransitionResult = Schemas["BulkTransitionResponse"];
```

- [ ] **Step 2: Write the failing tests**

Create `web/src/lib/intake.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { JobPipeline } from "./domain";
import {
  MAX_BULK_FILES,
  applicationsByCandidate,
  bulkSummary,
  candidateNameFromParse,
  describeError,
  exportHref,
  normalizeTag,
  queueFiles,
  updateItem,
  uploadProgress,
} from "./intake";

// Same table as backend/tests/test_notes_tags.py::TAG_CASES.
const TAG_CASES: [string, string][] = [
  ["Relocation OK", "relocation-ok"],
  ["  strong   SQL!! ", "strong-sql"],
  ["C++", "cplusplus"],
  ["C# developer", "csharp-developer"],
  ["Señor engineer", "senor-engineer"],
  ["already-kebab", "already-kebab"],
  ["--x--", "x"],
  ["a".repeat(80), "a".repeat(50)],
];

describe("normalizeTag", () => {
  it.each(TAG_CASES)("%s -> %s", (raw, expected) => {
    expect(normalizeTag(raw)).toBe(expected);
  });

  it("returns an empty string when nothing usable is left", () => {
    expect(normalizeTag("!!!")).toBe("");
  });
});

describe("describeError", () => {
  it("passes a string detail through", () => {
    expect(describeError("Job not found", 404)).toBe("Job not found");
  });

  it("flattens a 422 list into field: message", () => {
    expect(
      describeError([{ loc: ["body", "email"], msg: "value is not a valid email address" }], 422),
    ).toBe("email: value is not a valid email address");
  });

  it("falls back to the status", () => {
    expect(describeError(undefined, 500)).toBe("Request failed (500)");
  });
});

describe("exportHref", () => {
  it("passes only the filters that are set", () => {
    expect(exportHref({})).toBe("/api/candidates/export");
    expect(exportHref({ keyword: "sql", jobId: "7" })).toBe(
      "/api/candidates/export?keyword=sql&job_id=7",
    );
  });
});

describe("applicationsByCandidate", () => {
  it("maps each in-progress candidate to their application and stage", () => {
    const pipeline = {
      job_id: 1,
      stages: [],
      outcomes: {},
      columns: [
        {
          stage_key: "resume_submitted",
          stage_name: "Resume submitted",
          applications: [{ application_id: 10, candidate_id: "a", candidate_name: "A" }],
        },
        {
          stage_key: "hm_review",
          stage_name: "Hiring manager review",
          applications: [{ application_id: 11, candidate_id: "b", candidate_name: "B" }],
        },
      ],
    } as JobPipeline;
    expect(applicationsByCandidate(pipeline)).toEqual({
      a: { applicationId: 10, stageName: "Resume submitted" },
      b: { applicationId: 11, stageName: "Hiring manager review" },
    });
  });
});

describe("bulkSummary", () => {
  it("counts in plain English", () => {
    expect(bulkSummary("advance", 1, 0)).toBe("Advanced 1 candidate.");
    expect(bulkSummary("reject", 3, 2)).toBe("Rejected 3 candidates. 2 could not be rejected.");
  });
});

describe("bulk upload queue", () => {
  it("queues valid files and explains the rest", () => {
    const files = [
      { name: "a.pdf", size: 1000 },
      { name: "empty.pdf", size: 0 },
      { name: "huge.pdf", size: 9 * 1024 * 1024 },
    ];
    const { items, skipped } = queueFiles(files);
    expect(items.map((i) => [i.fileName, i.index, i.status])).toEqual([["a.pdf", 0, "queued"]]);
    expect(skipped).toEqual(["empty.pdf: the file is empty", "huge.pdf: larger than 8 MB"]);
  });

  it("caps a batch", () => {
    const files = Array.from({ length: MAX_BULK_FILES + 2 }, (_, i) => ({ name: `${i}.pdf`, size: 1 }));
    const { items, skipped } = queueFiles(files);
    expect(items).toHaveLength(MAX_BULK_FILES);
    expect(skipped).toHaveLength(2);
  });

  it("updates one item and reports progress", () => {
    const { items } = queueFiles([
      { name: "a.pdf", size: 1 },
      { name: "b.pdf", size: 1 },
    ]);
    const next = updateItem(updateItem(items, items[0].id, { status: "done" }), items[1].id, {
      status: "failed",
      detail: "Parsing failed",
    });
    expect(next[0].status).toBe("done");
    expect(next[1].detail).toBe("Parsing failed");
    expect(uploadProgress(next)).toEqual({ total: 2, done: 1, failed: 1, finished: true });
    expect(uploadProgress(items).finished).toBe(false);
  });
});

describe("candidateNameFromParse", () => {
  it("prefers personal_info.name, then parsed_data", () => {
    expect(candidateNameFromParse({ personal_info: { name: " Ada " } })).toBe("Ada");
    expect(candidateNameFromParse({ parsed_data: { personal_info: { name: "Grace" } } })).toBe(
      "Grace",
    );
    expect(candidateNameFromParse({})).toBeNull();
  });
});
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd web; npx vitest run src/lib/intake.test.ts`
Expected: FAIL, cannot resolve `./intake`

- [ ] **Step 4: Write the helpers**

Create `web/src/lib/intake.ts`:

```ts
/**
 * Pure rules for the ATS Phase C screens: tags, errors, export links, bulk
 * results, and the bulk upload queue. No React and no fetch, so every rule
 * here has a unit test.
 */
import type { JobPipeline } from "./domain";

export const MAX_TAGS_PER_CANDIDATE = 20;
export const MAX_BULK_FILES = 20;
export const MAX_FILE_BYTES = 8 * 1024 * 1024;

/**
 * Mirror of backend/utils/tags.py::normalize_tag, pinned by the same cases.
 * Returns "" where the server would refuse the tag.
 */
export function normalizeTag(raw: string): string {
  const slug = raw
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\+/g, "plus")
    .replace(/#/g, "sharp")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug.slice(0, 50).replace(/-+$/, "");
}

/** FastAPI's detail is a string for HTTPException and a list for a 422. */
export function describeError(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        const e = item as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(e.loc) && e.loc.length ? String(e.loc[e.loc.length - 1]) : "";
        return field ? `${field}: ${e.msg ?? "invalid"}` : (e.msg ?? "invalid");
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

export interface CandidateExportQuery {
  keyword?: string;
  status?: string;
  jobId?: string;
}

/** The CSV link for whatever the candidates list is currently filtered to. */
export function exportHref({ keyword, status, jobId }: CandidateExportQuery): string {
  const query = new URLSearchParams();
  if (keyword) query.set("keyword", keyword);
  if (status) query.set("status", status);
  if (jobId) query.set("job_id", jobId);
  const qs = query.toString();
  return qs ? `/api/candidates/export?${qs}` : "/api/candidates/export";
}

export interface ActiveApplication {
  applicationId: number;
  stageName: string;
}

/** Candidate id to their in-progress application on this job, read off the board. */
export function applicationsByCandidate(pipeline: JobPipeline): Record<string, ActiveApplication> {
  const out: Record<string, ActiveApplication> = {};
  for (const column of pipeline.columns) {
    for (const card of column.applications) {
      out[card.candidate_id] = { applicationId: card.application_id, stageName: column.stage_name };
    }
  }
  return out;
}

export function bulkSummary(action: "advance" | "reject", succeeded: number, failed: number): string {
  const verb = action === "advance" ? "Advanced" : "Rejected";
  const moved = `${verb} ${succeeded} ${succeeded === 1 ? "candidate" : "candidates"}.`;
  if (failed === 0) return moved;
  return `${moved} ${failed} could not be ${action === "advance" ? "advanced" : "rejected"}.`;
}

export type UploadStatus = "queued" | "parsing" | "saving" | "done" | "failed";

export interface UploadItem {
  id: string;
  /** Position in the files the user picked, used to find the File again. */
  index: number;
  fileName: string;
  status: UploadStatus;
  candidateName?: string;
  candidateId?: string;
  detail?: string;
}

/** Which picked files will be uploaded, and a reason for each one that will not. */
export function queueFiles(files: { name: string; size: number }[]): {
  items: UploadItem[];
  skipped: string[];
} {
  const items: UploadItem[] = [];
  const skipped: string[] = [];
  files.forEach((file, index) => {
    if (file.size === 0) {
      skipped.push(`${file.name}: the file is empty`);
    } else if (file.size > MAX_FILE_BYTES) {
      skipped.push(`${file.name}: larger than 8 MB`);
    } else if (items.length >= MAX_BULK_FILES) {
      skipped.push(`${file.name}: only ${MAX_BULK_FILES} files per batch`);
    } else {
      items.push({ id: `${index}:${file.name}`, index, fileName: file.name, status: "queued" });
    }
  });
  return { items, skipped };
}

export function updateItem(items: UploadItem[], id: string, patch: Partial<UploadItem>): UploadItem[] {
  return items.map((item) => (item.id === id ? { ...item, ...patch } : item));
}

export function uploadProgress(items: UploadItem[]): {
  total: number;
  done: number;
  failed: number;
  finished: boolean;
} {
  const done = items.filter((i) => i.status === "done").length;
  const failed = items.filter((i) => i.status === "failed").length;
  return { total: items.length, done, failed, finished: items.length > 0 && done + failed === items.length };
}

/** The person's name from a parse response, wherever this parser path put it. */
export function candidateNameFromParse(payload: {
  personal_info?: Record<string, unknown> | null;
  parsed_data?: Record<string, unknown> | null;
}): string | null {
  const direct = payload.personal_info?.name;
  const nested = (payload.parsed_data?.personal_info as Record<string, unknown> | undefined)?.name;
  const name = typeof direct === "string" && direct.trim() ? direct : nested;
  return typeof name === "string" && name.trim() ? name.trim() : null;
}
```

- [ ] **Step 5: Data functions**

In `web/src/lib/data.ts`, add `CandidateTags` and `Note` to the type import from `./domain`. Change `CandidateQuery` and `listCandidates` to:

```ts
export interface CandidateQuery {
  keyword?: string;
  status?: string;
  jobId?: string;
  page?: number;
  pageSize?: number;
}

export async function listCandidates({
  keyword,
  status,
  jobId,
  page = 1,
  pageSize = 25,
}: CandidateQuery = {}): Promise<CandidateSearch> {
  return apiFetch<CandidateSearch>("/api/candidates/", {
    token: await getToken(),
    query: { keyword, status, job_id: jobId, page, page_size: pageSize },
  });
}
```

Append:

```ts
/** A candidate's notes thread, newest first (ATS Phase C). */
export async function getCandidateNotes(candidateId: string): Promise<Note[]> {
  return (
    (await apiFetchOptional<Note[]>(`/api/candidates/${encodeURIComponent(candidateId)}/notes`, {
      token: await getToken(),
    })) ?? []
  );
}

/** A candidate's tags, alphabetical. */
export async function getCandidateTags(candidateId: string): Promise<string[]> {
  const result = await apiFetchOptional<CandidateTags>(
    `/api/candidates/${encodeURIComponent(candidateId)}/tags`,
    { token: await getToken() },
  );
  return result?.tags ?? [];
}
```

- [ ] **Step 6: Run the tests and the type check**

Run: `cd web; npx vitest run src/lib/intake.test.ts; npm run typecheck`
Expected: 19 tests pass, typecheck clean.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c12.txt`:

```
feat(web): intake helpers, types, and data functions

The tag preview uses the same normalization table as the server, so what
the input shows is what gets stored. The bulk upload queue, error text,
export link, and bulk summary are pure functions with tests.
```

```powershell
git add web/src/lib/intake.ts web/src/lib/intake.test.ts web/src/lib/domain.ts web/src/lib/data.ts
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c12.txt
```

---

### Task 13: Candidate page: notes thread, tags, consider for another role

**Files:**
- Create: `web/src/components/notes-thread.tsx`, `web/src/components/candidate-tags.tsx`, `web/src/components/consider-for-role.tsx`
- Modify: `web/src/app/candidates/[id]/page.tsx`

- [ ] **Step 1: Notes thread**

Create `web/src/components/notes-thread.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, MessageSquarePlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { Note } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { describeError } from "@/lib/intake";

/** One choice in the "About" picker: an application at its current stage. */
export interface NoteContext {
  value: string;
  label: string;
  applicationId: number;
  stageKey: string | null;
}

const GENERAL = "general";

/**
 * The candidate's notes, newest first, with a composer for writers.
 *
 * A note can be about the person or about the stage an application is at.
 * One thread rather than a thread per stage: a recruiter reads a person's
 * history top to bottom, and the label on each note says where it belongs.
 */
export function NotesThread({
  candidateId,
  notes,
  contexts,
  writable,
}: {
  candidateId: string;
  notes: Note[];
  contexts: NoteContext[];
  writable: boolean;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [about, setAbout] = useState(GENERAL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !body.trim()) return;
    setBusy(true);
    setError(null);
    const context = contexts.find((c) => c.value === about);
    try {
      const response = await fetch(`/api/candidates/${encodeURIComponent(candidateId)}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          body: body.trim(),
          application_id: context?.applicationId ?? null,
          stage_key: context?.stageKey ?? null,
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(describeError(payload?.detail, response.status));
      }
      setBody("");
      setAbout(GENERAL);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Notes</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {writable ? (
          <form onSubmit={submit} className="space-y-2">
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={3}
              maxLength={5000}
              placeholder="Add a note for the hiring team"
              aria-label="New note"
            />
            <div className="flex flex-wrap items-center gap-2">
              {contexts.length ? (
                <label className="flex items-center gap-2 text-xs text-slate-500">
                  About
                  <select
                    value={about}
                    onChange={(e) => setAbout(e.target.value)}
                    className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-700"
                  >
                    <option value={GENERAL}>This candidate in general</option>
                    {contexts.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <Button type="submit" size="sm" disabled={busy || !body.trim()} className="ml-auto">
                {busy ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <MessageSquarePlus className="mr-2 h-4 w-4" aria-hidden />
                )}
                Add note
              </Button>
            </div>
            {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
          </form>
        ) : null}

        {notes.length === 0 ? (
          <p className="text-sm text-slate-500">No notes yet.</p>
        ) : (
          <ul className="space-y-3">
            {notes.map((note) => (
              <li key={note.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs text-slate-500">
                  <span className="font-medium text-slate-700">
                    {note.author_name ?? "Earlier note"}
                  </span>
                  <span>{formatDate(note.created_at)}</span>
                  {note.job_title ? (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
                      {[note.job_title, note.stage_name].filter(Boolean).join(", ")}
                    </span>
                  ) : null}
                </p>
                <p className="mt-1 whitespace-pre-line text-slate-700">{note.body}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Tags**

Create `web/src/components/candidate-tags.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MAX_TAGS_PER_CANDIDATE, describeError, normalizeTag } from "@/lib/intake";

/**
 * Tag chips, with add and remove for writers.
 *
 * Shows what a typed tag will be saved as before it is sent, because the
 * server normalizes ("Relocation OK" becomes relocation-ok).
 */
export function CandidateTags({
  candidateId,
  tags,
  writable,
}: {
  candidateId: string;
  tags: string[];
  writable: boolean;
}) {
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const preview = draft.trim() ? normalizeTag(draft) : "";
  const base = `/api/candidates/${encodeURIComponent(candidateId)}/tags`;

  async function send(method: "POST" | "DELETE", tag: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response =
        method === "POST"
          ? await fetch(base, {
              method,
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tag }),
            })
          : await fetch(`${base}/${encodeURIComponent(tag)}`, { method });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(describeError(payload?.detail, response.status));
      }
      if (method === "POST") setDraft("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!writable && tags.length === 0) return null;

  return (
    <div>
      <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">Tags</h3>
      <div className="flex flex-wrap gap-1.5">
        {tags.length === 0 ? (
          <span className="text-xs text-slate-400">No tags yet.</span>
        ) : (
          tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700"
            >
              {tag}
              {writable ? (
                <button
                  type="button"
                  onClick={() => send("DELETE", tag)}
                  disabled={busy}
                  aria-label={`Remove tag ${tag}`}
                  className="rounded-full text-indigo-400 hover:text-indigo-700"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              ) : null}
            </span>
          ))
        )}
      </div>
      {writable && tags.length < MAX_TAGS_PER_CANDIDATE ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (preview) send("POST", draft);
          }}
          className="mt-2 flex gap-2"
        >
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add a tag"
            aria-label="New tag"
            maxLength={80}
            className="h-8 text-sm"
          />
          <Button type="submit" size="sm" variant="outline" disabled={!preview || busy}>
            Add
          </Button>
        </form>
      ) : null}
      {writable && draft.trim() && preview !== draft.trim() ? (
        <p className="mt-1 text-xs text-slate-500">
          {preview ? `Saved as ${preview}` : "Use at least one letter or number."}
        </p>
      ) : null}
      {error ? <p className="mt-1 text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 3: Consider for another role**

Create `web/src/components/consider-for-role.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { describeError } from "@/lib/intake";

/**
 * Put this person on another open job's pipeline.
 *
 * Creates a second application, not a second candidate: one person, one
 * profile, many pipelines (spec decision 2). Only open jobs they have not
 * applied to are offered.
 */
export function ConsiderForRole({
  candidateId,
  jobs,
}: {
  candidateId: string;
  jobs: { id: number; title: string; department: string }[];
}) {
  const router = useRouter();
  const [jobId, setJobId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!jobId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${jobId}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, source: "internal" }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(describeError(payload?.detail, response.status));
      }
      setJobId("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (jobs.length === 0) return null;

  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-white p-3 text-sm"
    >
      <label htmlFor="consider-job" className="font-medium text-slate-700">
        Consider for another role
      </label>
      <select
        id="consider-job"
        value={jobId}
        onChange={(e) => setJobId(e.target.value)}
        className="min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-700"
      >
        <option value="">Choose a job</option>
        {jobs.map((job) => (
          <option key={job.id} value={job.id}>
            {job.title} ({job.department})
          </option>
        ))}
      </select>
      <Button type="submit" size="sm" disabled={!jobId || busy}>
        {busy ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
        ) : (
          <Plus className="mr-2 h-4 w-4" aria-hidden />
        )}
        Add to pipeline
      </Button>
      {error ? <p className="w-full text-sm font-medium text-rose-700">{error}</p> : null}
    </form>
  );
}
```

- [ ] **Step 4: Wire them into the candidate page**

In `web/src/app/candidates/[id]/page.tsx`:

Add imports (merge `getCandidateNotes`, `getCandidateTags` and `listJobs` into the existing `@/lib/data` import list):

```ts
import { CandidateTags } from "@/components/candidate-tags";
import { ConsiderForRole } from "@/components/consider-for-role";
import { NotesThread } from "@/components/notes-thread";
```

Extend the page's `Promise.all` with three more entries and names. Append them to whatever Phase B left in that list:

```ts
  const [applications, savedJobs, resumes, writable, notes, tags, jobList] = await Promise.all([
    getCandidateApplications(id),
    getCandidateSavedJobs(id),
    getCandidateResumes(id),
    canWrite(),
    getCandidateNotes(id),
    getCandidateTags(id),
    // Optional context: a failed job list only hides "Consider for another role".
    listJobs().catch(() => null),
  ]);
```

Directly after the existing `const details = ...` statement, add:

```ts
  const appliedJobIds = new Set(applications.map((application) => application.job_id));
  const otherJobs = (jobList?.results ?? [])
    .filter((job) => job.status === "open" && !appliedJobIds.has(job.id))
    .map(({ id: jobId, title, department }) => ({ id: jobId, title, department }));
  const noteContexts = details
    .filter((detail) => detail.status === "active" && detail.current_stage_key)
    .map((detail) => ({
      value: `${detail.id}:${detail.current_stage_key}`,
      label: `${detail.job_title}, ${detail.current_stage_name ?? detail.current_stage_key}`,
      applicationId: detail.id,
      stageKey: detail.current_stage_key ?? null,
    }));
```

In the left profile card, directly after the skills block (the `{candidate.skills?.length ? ( ... ) : null}` expression), add:

```tsx
              <CandidateTags candidateId={id} tags={tags} writable={writable} />
```

In the right column, directly before `{details.length === 0 ? (`, add:

```tsx
          {writable ? <ConsiderForRole candidateId={id} jobs={otherJobs} /> : null}
```

Replace the whole `{candidate.notes ? ( <Card> ... </Card> ) : null}` block with:

```tsx
          <NotesThread
            candidateId={id}
            notes={notes}
            contexts={noteContexts}
            writable={writable}
          />
```

In the empty-pipeline card, change the copy `Not in any pipeline yet. Open a job and add them to it.` to `Not in any pipeline yet.`. The control above it now does the adding.

- [ ] **Step 5: Type check, lint, tests**

Run: `cd web; npm run typecheck; npm run lint; npm test`
Expected: clean, all tests pass.

- [ ] **Step 6: Check it live**

Start both servers (`cd backend; poetry run python -m uvicorn main:app --port 8010` and `cd web; npm run dev`). Open a seeded candidate as the demo user: the Notes card lists the seeded note with an author name, tags show as chips, and there are no composer, add-tag, or consider controls. Sign in as admin (`/login`). Add a note "About" the current stage and check it appears at the top with the job and stage label. Add the tag `Relocation OK` and check the preview reads `Saved as relocation-ok` and the chip appears. Use "Consider for another role" and check a second Pipeline card appears at Resume submitted.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c13.txt`:

```
feat(web): candidate notes thread, tags, and consider for another role

The single notes field becomes a thread where each note can be pinned
to the stage an application is at. Tags preview their normalized form
before saving. Consider for another role adds a second pipeline for the
same person. Writers get the controls; the demo sees the thread and
chips only. Checked live as both.
```

```powershell
git add web/src/components/notes-thread.tsx web/src/components/candidate-tags.tsx web/src/components/consider-for-role.tsx "web/src/app/candidates/[id]/page.tsx"
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c13.txt
```

---

### Task 14: Candidates list: job filter, add candidate, export, bulk

**Files:**
- Create: `web/src/components/add-candidate-panel.tsx`, `web/src/components/candidate-table.tsx`
- Modify: `web/src/components/candidate-filters.tsx`, `web/src/app/candidates/page.tsx`

- [ ] **Step 1: Add candidate panel**

Create `web/src/components/add-candidate-panel.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { describeError } from "@/lib/intake";

/**
 * Add a person by hand: name, email, and optionally the job they are for.
 *
 * Choosing a job puts them at Resume submitted on it in the same request,
 * so the new profile opens with its pipeline already started.
 */
export function AddCandidatePanel({
  jobs,
}: {
  jobs: { id: number; title: string; department: string }[];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [jobId, setJobId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/candidates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim(),
          job_id: jobId ? Number(jobId) : null,
        }),
      });
      const payload = (await response.json().catch(() => null)) as {
        id?: string;
        detail?: unknown;
      } | null;
      if (!response.ok || !payload?.id) {
        throw new Error(describeError(payload?.detail, response.status));
      }
      router.push(`/candidates/${payload.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <div className="mb-4 flex justify-end">
        <Button type="button" onClick={() => setOpen(true)}>
          <UserPlus className="mr-2 h-4 w-4" aria-hidden />
          Add candidate
        </Button>
      </div>
    );
  }

  return (
    <Card className="mb-4">
      <CardContent className="p-4">
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Input
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            placeholder="First name"
            aria-label="First name"
            required
          />
          <Input
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            placeholder="Last name"
            aria-label="Last name"
            required
          />
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            aria-label="Email"
            required
          />
          <select
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            aria-label="Job"
            className="rounded-md border border-slate-200 bg-white px-2 py-2 text-sm text-slate-700"
          >
            <option value="">No job yet</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title} ({job.department})
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2 sm:col-span-2 lg:col-span-4">
            <Button type="submit" disabled={busy}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
              {jobId ? "Add and start pipeline" : "Add candidate"}
            </Button>
            <Button type="button" variant="outline" disabled={busy} onClick={() => setOpen(false)}>
              Cancel
            </Button>
            {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: The table with bulk selection**

Create `web/src/components/candidate-table.tsx`. It takes over the table markup and `SkillChips` from the page:

```tsx
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, X } from "lucide-react";

import { StageBadge } from "@/components/stage-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { type BulkTransitionResult, type Candidate, fullName, initials } from "@/lib/domain";
import { type ActiveApplication, bulkSummary, describeError } from "@/lib/intake";

/** Present when the list is filtered to one job: who can be moved, and where they are. */
export interface BulkContext {
  jobTitle: string;
  applications: Record<string, ActiveApplication>;
}

interface Outcome {
  summary: string;
  failures: { name: string; detail: string }[];
}

/**
 * The candidates table. With a job filter it gains checkboxes and a bar to
 * advance or reject the selection; every candidate who could not be moved is
 * listed by name with the reason, because the server moves the rest anyway.
 */
export function CandidateTable({
  candidates,
  bulk,
}: {
  candidates: Candidate[];
  bulk: BulkContext | null;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirmReject, setConfirmReject] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"advance" | "reject" | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectable = useMemo(
    () =>
      bulk
        ? candidates.flatMap((c) => (bulk.applications[c.id] ? [bulk.applications[c.id].applicationId] : []))
        : [],
    [bulk, candidates],
  );
  const allSelected = selectable.length > 0 && selectable.every((id) => selected.has(id));

  function toggle(id: number) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function run(action: "advance" | "reject") {
    if (busy || selected.size === 0) return;
    setBusy(action);
    setError(null);
    setOutcome(null);
    try {
      const response = await fetch(`/api/applications/bulk/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          application_ids: [...selected],
          note: action === "reject" ? note.trim() || null : null,
        }),
      });
      const payload = (await response.json().catch(() => null)) as
        | (BulkTransitionResult & { detail?: unknown })
        | null;
      if (!response.ok || !payload?.results) {
        throw new Error(describeError(payload?.detail, response.status));
      }
      setOutcome({
        summary: bulkSummary(action, payload.succeeded, payload.failed),
        failures: payload.results
          .filter((r) => !r.ok)
          .map((r) => ({
            name: r.candidate_name ?? `Application ${r.application_id}`,
            detail: r.detail ?? "Not moved.",
          })),
      });
      setSelected(new Set());
      setConfirmReject(false);
      setNote("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      {bulk ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <span className="text-slate-600">
            {selected.size === 0
              ? `Select candidates in ${bulk.jobTitle} to move them together.`
              : `${selected.size} selected in ${bulk.jobTitle}`}
          </span>
          <span className="ml-auto flex gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => run("advance")}
              disabled={selected.size === 0 || busy !== null}
            >
              {busy === "advance" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <ArrowRight className="mr-2 h-4 w-4" aria-hidden />
              )}
              Advance
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setConfirmReject(true)}
              disabled={selected.size === 0 || busy !== null}
            >
              <X className="mr-2 h-4 w-4" aria-hidden />
              Reject
            </Button>
          </span>
          {confirmReject ? (
            <div
              role="alertdialog"
              aria-label="Reject the selected candidates?"
              className="w-full space-y-2 rounded-md border border-rose-200 bg-rose-50 p-3"
            >
              <p className="font-medium text-rose-900">
                Reject {selected.size} {selected.size === 1 ? "candidate" : "candidates"} in{" "}
                {bulk.jobTitle}? Each application ends at its current stage.
              </p>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Reason (optional)"
                aria-label="Reason"
                className="w-full rounded-md border border-rose-200 bg-white p-2 text-sm text-slate-800"
              />
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={() => run("reject")}
                  disabled={busy !== null}
                  className="bg-rose-600 text-white hover:bg-rose-700"
                >
                  {busy === "reject" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
                  Reject
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() => setConfirmReject(false)}
                >
                  Keep them
                </Button>
              </div>
            </div>
          ) : null}
          {outcome ? (
            <div className="w-full text-sm" role="status">
              <p className="font-medium text-slate-800">{outcome.summary}</p>
              {outcome.failures.length ? (
                <ul className="mt-1 list-disc pl-5 text-rose-700">
                  {outcome.failures.map((failure) => (
                    <li key={`${failure.name}-${failure.detail}`}>
                      {failure.name}: {failure.detail}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {error ? <p className="w-full text-sm font-medium text-rose-700">{error}</p> : null}
        </div>
      ) : null}

      <Card className="overflow-hidden py-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {bulk ? (
                <TableHead className="w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    disabled={selectable.length === 0}
                    onChange={() => setSelected(allSelected ? new Set() : new Set(selectable))}
                    aria-label="Select everyone who can be moved"
                  />
                </TableHead>
              ) : null}
              <TableHead>Name</TableHead>
              <TableHead className="hidden md:table-cell">Current role</TableHead>
              <TableHead className="hidden lg:table-cell">Location</TableHead>
              <TableHead className="hidden xl:table-cell">Skills</TableHead>
              <TableHead className="text-right">Stage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {candidates.map((candidate) => {
              const application = bulk?.applications[candidate.id];
              return (
                <TableRow key={candidate.id}>
                  {bulk ? (
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={application ? selected.has(application.applicationId) : false}
                        disabled={!application}
                        onChange={() => application && toggle(application.applicationId)}
                        aria-label={`Select ${fullName(candidate)}`}
                      />
                    </TableCell>
                  ) : null}
                  <TableCell>
                    <Link
                      href={`/candidates/${candidate.id}`}
                      className="flex items-center gap-3 font-medium hover:underline"
                    >
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700">
                        {initials(candidate)}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate">{fullName(candidate)}</span>
                        <span className="block truncate text-xs font-normal text-slate-500">
                          {candidate.email ?? "No email"}
                        </span>
                      </span>
                    </Link>
                  </TableCell>
                  <TableCell className="hidden max-w-56 truncate text-slate-600 md:table-cell">
                    {candidate.current_position ?? candidate.position_applied ?? "Not listed"}
                    {candidate.current_company ? (
                      <span className="block text-xs text-slate-400">{candidate.current_company}</span>
                    ) : null}
                  </TableCell>
                  <TableCell className="hidden text-slate-600 lg:table-cell">
                    {candidate.location ?? "Not listed"}
                  </TableCell>
                  <TableCell className="hidden xl:table-cell">
                    <SkillChips skills={candidate.skills} />
                  </TableCell>
                  <TableCell className="text-right">
                    {bulk ? (
                      <span className="text-xs text-slate-600">
                        {application ? application.stageName : "Not in progress here"}
                      </span>
                    ) : (
                      <StageBadge status={candidate.status} />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

function SkillChips({ skills }: { skills: string[] | null | undefined }) {
  if (!skills?.length) return <span className="text-xs text-slate-400">None listed</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {skills.slice(0, 3).map((skill) => (
        <span key={skill} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
          {skill}
        </span>
      ))}
      {skills.length > 3 ? (
        <span className="px-1 py-0.5 text-xs text-slate-400">+{skills.length - 3}</span>
      ) : null}
    </span>
  );
}
```

- [ ] **Step 3: Job filter**

In `web/src/components/candidate-filters.tsx`, change the props and add a job select. Replace the function signature with:

```tsx
export function CandidateFilters({
  initialKeyword,
  initialStatus,
  initialJob,
  jobs,
}: {
  initialKeyword: string;
  initialStatus: string;
  initialJob: string;
  jobs: { id: number; title: string }[];
}) {
```

Add next to `setStatus`:

```tsx
  function setJob(job: string) {
    const next = new URLSearchParams(params.toString());
    if (job) next.set("job", job);
    else next.delete("job");
    next.delete("page");
    startTransition(() => router.replace(`/candidates?${next}`, { scroll: false }));
  }
```

Replace the search box wrapper `<div className="relative max-w-md"> ... </div>` with a row that holds it and the select:

```tsx
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-md">
          <Search className="absolute top-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
          <Input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="Search by name, skill, or position"
            aria-label="Search candidates"
            className={cn("pl-9", pending && "opacity-70")}
          />
        </div>
        {jobs.length ? (
          <select
            value={initialJob}
            onChange={(e) => setJob(e.target.value)}
            aria-label="Filter by job"
            className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          >
            <option value="">All jobs</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>
        ) : null}
      </div>
```

- [ ] **Step 4: The page**

Replace `web/src/app/candidates/page.tsx` with:

```tsx
import { Download } from "lucide-react";

import { AddCandidatePanel } from "@/components/add-candidate-panel";
import { CandidateFilters } from "@/components/candidate-filters";
import { type BulkContext, CandidateTable } from "@/components/candidate-table";
import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { getJobPipeline, listCandidates, listJobs } from "@/lib/data";
import type { CandidateSearch } from "@/lib/domain";
import { applicationsByCandidate, exportHref } from "@/lib/intake";
import { canWrite } from "@/lib/session";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 25;

export default async function CandidatesPage({ searchParams }: PageProps<"/candidates">) {
  const params = await searchParams;
  const keyword = first(params.q);
  const status = first(params.status);
  const jobId = first(params.job);
  // A hand-edited `?page=abc` should land on page 1, not send NaN to the API.
  const page = Math.max(1, Number(first(params.page)) || 1);

  const [writable, jobList] = await Promise.all([canWrite(), listJobs().catch(() => null)]);
  const jobs = (jobList?.results ?? [])
    .map(({ id, title, department, status: jobStatus }) => ({ id, title, department, status: jobStatus }))
    .sort((a, b) => a.title.localeCompare(b.title));
  const exportLink = (
    <a
      href={exportHref({ keyword, status, jobId })}
      className={buttonVariants({ variant: "outline" })}
      download
    >
      <Download className="mr-1.5 h-4 w-4" aria-hidden />
      Export CSV
    </a>
  );

  let data: CandidateSearch;
  try {
    data = await listCandidates({ keyword, status, jobId, page, pageSize: PAGE_SIZE });
  } catch (error) {
    return (
      <>
        <PageHeader title="Candidates" />
        <ErrorState
          title="Could not load candidates"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  // Bulk moves need applications, and an application belongs to one job, so
  // the checkboxes only appear once the list is filtered to a job.
  let bulk: BulkContext | null = null;
  if (writable && jobId) {
    const pipeline = await getJobPipeline(jobId).catch(() => null);
    const job = jobs.find((j) => String(j.id) === jobId);
    if (pipeline && job) {
      bulk = { jobTitle: job.title, applications: applicationsByCandidate(pipeline) };
    }
  }

  const lastPage = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const from = data.total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, data.total);

  return (
    <>
      <PageHeader
        title="Candidates"
        description={
          data.total === 1 ? "1 candidate" : `${data.total} candidates in the pipeline`
        }
        actions={exportLink}
      />

      {writable ? <AddCandidatePanel jobs={jobs.filter((j) => j.status === "open")} /> : null}

      <CandidateFilters
        initialKeyword={keyword ?? ""}
        initialStatus={status ?? ""}
        initialJob={jobId ?? ""}
        jobs={jobs}
      />

      {data.results.length === 0 ? (
        <EmptyState
          title="No candidates match those filters"
          detail="Clear the search box, pick a different stage, or choose All jobs."
        />
      ) : (
        <CandidateTable candidates={data.results} bulk={bulk} />
      )}

      {data.total > PAGE_SIZE ? (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            Showing {from} to {to} of {data.total}
          </span>
          <span className="flex gap-2">
            <PageLink params={params} page={page - 1} disabled={page <= 1}>
              Previous
            </PageLink>
            <PageLink params={params} page={page + 1} disabled={page >= lastPage}>
              Next
            </PageLink>
          </span>
        </div>
      ) : null}
    </>
  );
}
```

then keep the existing `first` and `PageLink` functions below it unchanged, and add `import Link from "next/link";` back at the top, since `PageLink` uses it. Delete the page's old `SkillChips` (it moved into `candidate-table.tsx`). Note that the "Showing x to y" copy replaces the old en dash range.

- [ ] **Step 5: Type check, lint, tests**

Run: `cd web; npm run typecheck; npm run lint; npm test`
Expected: clean, all pass.

- [ ] **Step 6: Check it live**

With both dev servers running:
- As the demo: `/candidates` shows Export CSV and the job filter, with no Add candidate and no checkboxes even with a job chosen. Export CSV downloads a file whose header has no score column.
- As admin: choose a job. Checkboxes appear only on people in progress there and the Stage column shows the stage name. Select two and Advance. The summary reads "Advanced 2 candidates." and the stages update. Reject one with a reason. Add a candidate with a job and confirm you land on their page at Resume submitted.

- [ ] **Step 7: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c14.txt`:

```
feat(web): candidates list gains job filter, add, export, and bulk moves

Filtering to a job turns on checkboxes for everyone in progress there,
and the bulk bar names anyone who could not be moved instead of failing
the batch. Add candidate takes a name, an email, and optionally a job,
and opens the new profile with its pipeline started. Export CSV
downloads exactly the filtered list. Checked live as the demo and as
admin.
```

```powershell
git add web/src/components/add-candidate-panel.tsx web/src/components/candidate-table.tsx web/src/components/candidate-filters.tsx web/src/app/candidates/page.tsx
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c14.txt
```

---

### Task 15: Upload: add to a job's pipeline, and bulk upload

**Files:**
- Create: `web/src/components/bulk-uploader.tsx`
- Modify: `web/src/components/resume-uploader.tsx`, `web/src/app/upload/page.tsx`

- [ ] **Step 1: Single upload saves onto the chosen job**

In `web/src/components/resume-uploader.tsx`:

1. Export the accept list: change `const ACCEPT = ...` to `export const ACCEPT = ...`.
2. In `save()`, directly after `if (roleLabel) form.set("position_applied", roleLabel);`, add:
   ```ts
         // ATS Phase C: a real requisition means "add them to its pipeline".
         if (selectedJob) form.set("job_id", String(selectedJob.id));
   ```
3. Replace the save button's idle label:
   ```tsx
                 <>
                   <UserPlus className="mr-2 h-4 w-4" aria-hidden />
                   {selectedJob ? `Save and add to ${selectedJob.title}` : "Save as candidate"}
                 </>
   ```
4. Replace the writer help text `"Parsing alone saves nothing. Save as candidate adds this person to the pipeline with the resume attached."` with:
   ```tsx
                 ? selectedJob
                   ? `Parsing alone saves nothing. Saving adds this person to ${selectedJob.title} at Resume submitted, with the resume attached.`
                   : "Parsing alone saves nothing. Pick a job above to also start their pipeline."
   ```

- [ ] **Step 2: Bulk uploader**

Create `web/src/components/bulk-uploader.tsx`:

```tsx
"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, CircleDashed, Loader2, Upload, XCircle } from "lucide-react";

import { ACCEPT, type SelectableJob } from "@/components/resume-uploader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type UploadItem,
  candidateNameFromParse,
  describeError,
  queueFiles,
  updateItem,
  uploadProgress,
} from "@/lib/intake";

const STATUS_LABELS: Record<UploadItem["status"], string> = {
  queued: "Waiting",
  parsing: "Reading the resume",
  saving: "Saving",
  done: "Added",
  failed: "Not added",
};

/**
 * Several resumes into one job's pipeline, one file at a time.
 *
 * Sequential on purpose: each parse is a model call of ten to thirty seconds,
 * and nginx rate-limits /api/resume/. Parallel uploads would trip the limit
 * and make the progress list lie about what is happening.
 */
export function BulkUploader({ jobs }: { jobs: SelectableJob[] }) {
  const [jobId, setJobId] = useState("");
  const [items, setItems] = useState<UploadItem[]>([]);
  const [skipped, setSkipped] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const files = useRef<File[]>([]);
  const stop = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const progress = uploadProgress(items);
  const job = jobs.find((j) => String(j.id) === jobId) ?? null;

  function choose(list: FileList | null) {
    if (!list || running) return;
    files.current = Array.from(list);
    const queued = queueFiles(files.current.map((f) => ({ name: f.name, size: f.size })));
    setItems(queued.items);
    setSkipped(queued.skipped);
  }

  async function processOne(item: UploadItem) {
    const file = files.current[item.index];
    const patch = (next: Partial<UploadItem>) => setItems((current) => updateItem(current, item.id, next));
    patch({ status: "parsing", detail: undefined });
    try {
      const parseForm = new FormData();
      parseForm.set("file", file);
      const parsed = await fetch("/api/resume/parse", { method: "POST", body: parseForm });
      const parsedBody = (await parsed.json().catch(() => null)) as {
        success?: boolean;
        message?: string;
        detail?: unknown;
        personal_info?: Record<string, unknown> | null;
        parsed_data?: Record<string, unknown> | null;
      } | null;
      if (!parsed.ok || !parsedBody || parsedBody.success === false) {
        throw new Error(parsedBody?.message ?? describeError(parsedBody?.detail, parsed.status));
      }
      patch({ status: "saving", candidateName: candidateNameFromParse(parsedBody) ?? undefined });

      const saveForm = new FormData();
      saveForm.set("file", file);
      saveForm.set("parsed_data", JSON.stringify(parsedBody.parsed_data ?? {}));
      saveForm.set("job_id", jobId);
      if (job) saveForm.set("position_applied", job.title);
      const saved = await fetch("/api/resume/save", { method: "POST", body: saveForm });
      const savedBody = (await saved.json().catch(() => null)) as {
        candidate_id?: string | null;
        already_in_pipeline?: boolean;
        detail?: unknown;
      } | null;
      if (!saved.ok || !savedBody?.candidate_id) {
        throw new Error(describeError(savedBody?.detail, saved.status));
      }
      patch({
        status: "done",
        candidateId: savedBody.candidate_id,
        detail: savedBody.already_in_pipeline ? "Already in this pipeline. Resume updated." : undefined,
      });
    } catch (err) {
      patch({ status: "failed", detail: (err as Error).message });
    }
  }

  async function start() {
    if (!jobId || running) return;
    setRunning(true);
    stop.current = false;
    for (const item of items) {
      if (stop.current) break;
      if (item.status === "queued" || item.status === "failed") await processOne(item);
    }
    setRunning(false);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardContent className="space-y-4 p-6">
          <button
            type="button"
            onClick={() => input.current?.click()}
            disabled={running}
            className="grid w-full cursor-pointer place-items-center gap-2 rounded-lg border-2 border-dashed border-slate-300 p-10 text-center hover:border-indigo-400"
          >
            <Upload className="h-6 w-6 text-slate-400" aria-hidden />
            <span className="font-medium text-slate-700">
              {items.length ? `${items.length} files ready` : "Choose up to 20 resumes"}
            </span>
            <span className="text-xs text-slate-500">PDF, Word, text, or an image. Up to 8 MB each.</span>
          </button>
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            multiple
            className="hidden"
            aria-label="Resume files"
            onChange={(e) => choose(e.target.files)}
          />

          <label className="block text-sm font-medium text-slate-700">
            Add everyone to
            <select
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              disabled={running}
              className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm font-normal text-slate-700"
            >
              <option value="">Choose a job</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} ({j.department})
                </option>
              ))}
            </select>
          </label>

          <div className="flex gap-2">
            <Button onClick={start} disabled={!jobId || items.length === 0 || running} className="flex-1">
              {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
              {running ? "Adding" : progress.failed ? "Retry the ones not added" : "Add to pipeline"}
            </Button>
            {running ? (
              <Button variant="outline" onClick={() => (stop.current = true)}>
                Stop after this file
              </Button>
            ) : null}
          </div>

          {skipped.length ? (
            <ul className="space-y-1 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              {skipped.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Progress</CardTitle>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p className="text-sm text-slate-500">Each file is read and saved in turn. Results appear here.</p>
          ) : (
            <>
              <p className="mb-3 text-xs text-slate-500" role="status">
                {progress.done} of {progress.total} added
                {progress.failed ? `, ${progress.failed} not added` : ""}
              </p>
              <ul className="space-y-2 text-sm">
                {items.map((item) => (
                  <li key={item.id} className="flex items-start gap-2">
                    <StatusIcon status={item.status} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-slate-800">
                        {item.candidateId ? (
                          <Link href={`/candidates/${item.candidateId}`} className="hover:underline">
                            {item.candidateName ?? item.fileName}
                          </Link>
                        ) : (
                          item.candidateName ?? item.fileName
                        )}
                      </span>
                      <span className="block text-xs text-slate-500">
                        {STATUS_LABELS[item.status]}
                        {item.detail ? `. ${item.detail}` : ""}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatusIcon({ status }: { status: UploadItem["status"] }) {
  if (status === "done") return <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" aria-hidden />;
  if (status === "failed") return <XCircle className="mt-0.5 h-4 w-4 text-rose-600" aria-hidden />;
  if (status === "queued") return <CircleDashed className="mt-0.5 h-4 w-4 text-slate-300" aria-hidden />;
  return <Loader2 className="mt-0.5 h-4 w-4 animate-spin text-indigo-600" aria-hidden />;
}
```

- [ ] **Step 3: The upload page offers both for writers**

In `web/src/app/upload/page.tsx`, add the imports:

```ts
import { BulkUploader } from "@/components/bulk-uploader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
```

Replace `<ResumeUploader canWrite={writable} jobs={jobs} />` with:

```tsx
      {writable ? (
        <Tabs defaultValue="one">
          <TabsList className="mb-4">
            <TabsTrigger value="one">One resume</TabsTrigger>
            <TabsTrigger value="many">Several resumes</TabsTrigger>
          </TabsList>
          <TabsContent value="one">
            <ResumeUploader canWrite jobs={jobs} />
          </TabsContent>
          <TabsContent value="many">
            <BulkUploader jobs={jobs} />
          </TabsContent>
        </Tabs>
      ) : (
        <ResumeUploader canWrite={false} jobs={jobs} />
      )}
```

and change the writer description to `"Parse a resume, review it, then save it straight onto a job's pipeline. Or add several at once."`.

- [ ] **Step 4: Type check, lint, tests, build**

Run: `cd web; npm run typecheck; npm run lint; npm test; npm run build`
Expected: clean.

- [ ] **Step 5: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c15.txt`:

```
feat(web): upload saves onto a job's pipeline; bulk upload

Choosing a requisition before saving now means "add them to it": the
button says which job, and the profile opens at Resume submitted. Writers
also get a Several resumes tab that reads and saves up to 20 files one
at a time with a progress list, and lists every file that was not added
with the reason. The demo keeps the single parse-only view.
```

```powershell
git add web/src/components/bulk-uploader.tsx web/src/components/resume-uploader.tsx web/src/app/upload/page.tsx
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c15.txt
```

---

### Task 16: Jobs list card count, and the live upload check

**Files:**
- Modify: `web/src/app/jobs/page.tsx`

- [ ] **Step 1: Card count from the pipeline**

In `web/src/app/jobs/page.tsx`, replace

```tsx
                    {job.applications} {job.applications === 1 ? "applicant" : "applicants"}
```

with

```tsx
                    {job.active_applications}{" "}
                    {job.active_applications === 1 ? "candidate" : "candidates"} in progress
```

- [ ] **Step 2: Type check and lint**

Run: `cd web; npm run typecheck; npm run lint`
Expected: clean.

- [ ] **Step 3: Live check of the acceptance criterion (upload to stage 1)**

Unit tests have missed real save-path bugs before (PR #18), so this runs the whole flow in a browser against the dev servers. With both dev servers running and a dev admin token printed by the scratchpad `admin_token.py` helper from Phase A (re-create it if the scratchpad was cleared: it signs a token for the first `admin` user with `create_access_token`), create `web/shot-upload.mjs`:

```js
// Scratch: upload the sample resume onto a job as admin and confirm stage 1.
import { chromium } from "@playwright/test";

const [token] = process.argv.slice(2);
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await context.addCookies([{ name: "recruitiq_session", value: token, domain: "localhost", path: "/" }]);
const page = await context.newPage();
await page.goto("http://localhost:3000/upload", { waitUntil: "networkidle", timeout: 120000 });
await page.getByRole("button", { name: "Try a sample resume" }).click();
const save = page.getByRole("button", { name: /^Save and add to / });
await save.waitFor({ timeout: 120000 });
const label = await save.textContent();
await save.click();
await page.waitForURL(/\/candidates\/[0-9a-f-]+$/, { timeout: 60000 });
await page.waitForTimeout(1500);
const jobTitle = label.replace("Save and add to ", "").trim();
const card = page.locator("div", { hasText: jobTitle }).filter({ hasText: "Resume submitted" }).first();
console.log(JSON.stringify({ url: page.url(), jobTitle, timelineVisible: await card.isVisible() }));
await page.screenshot({ path: "upload-check.png", fullPage: true });
await browser.close();
```

```powershell
cd web; node shot-upload.mjs <admin token>; cd ..
```

Expected: `timelineVisible: true` and a candidate URL. Open `upload-check.png` and confirm the Pipeline card for that job highlights Resume submitted. Then exercise bulk upload by hand: Several resumes, pick the sample file twice under different names, choose a job, and check both rows end "Added", the second with "Already in this pipeline. Resume updated." Delete `web/shot-upload.mjs` and `web/upload-check.png` afterward. Put any dev candidates you moved back where they were, or leave the new test candidates, which are synthetic.

- [ ] **Step 4: Commit**

Write `C:\Users\seaso\AppData\Local\Temp\claude\commit-c16.txt`:

```
feat(web): job cards count people in progress from the pipeline

The card used the stored all-time counter, which never dropped when
someone was rejected. Verified the Phase C acceptance live: the sample
resume uploaded as admin with a job chosen lands on a new profile at
Resume submitted on that job, and a repeat bulk upload of the same file
reports it as already in the pipeline.
```

```powershell
git add web/src/app/jobs/page.tsx
git commit -F C:\Users\seaso\AppData\Local\Temp\claude\commit-c16.txt
```

---

### Task 17: Full verification, PR, deploy

**Files:** none new.

- [ ] **Step 1: Backend, the way CI does it**

```powershell
$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.*)$' | Select-Object -First 1).Matches[0].Groups[1].Value.Trim().Trim('"',"'")
$env:OLLAMA_BASE_URL = "http://localhost:1"
poetry run ruff check backend --select E9,F63,F7,F82 --exclude backend/tests
poetry run python scripts/export_openapi.py --check
poetry run pytest -q
```

Expected: ruff clean, OpenAPI in sync, suite green except the two known embedding tests. Run the suite in the background and draft the PR body meanwhile.

- [ ] **Step 2: Scratch-database pass (schema changed)**

```powershell
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE IF EXISTS st_scratch" -c "CREATE DATABASE st_scratch"
$env:POSTGRES_CONN = $env:POSTGRES_CONN -replace '/ats_db', '/st_scratch'
cd backend; poetry run alembic upgrade head; cd ..
poetry run pytest -q
docker exec recruitiq-db psql -U admin -d ats_db -c "DROP DATABASE st_scratch"
```

Expected: the same result as step 1, on a database built from migrations alone.

- [ ] **Step 3: Web**

```powershell
cd web; npm run typecheck; npm run lint; npm test; npm run build
$env:E2E_BASE_URL = "http://localhost:3000"; npx playwright test; cd ..
```

Expected: clean, and the Playwright journey passes. If e2e fails, re-run it against `https://recruitiq.io` and restart a long-running `next dev` before blaming the change.

- [ ] **Step 4: Push and open the PR**

Write `C:\Users\seaso\AppData\Local\Temp\claude\pr-c.md`:

```
## What

ATS Phase C: intake, notes, tags. Upload saves straight onto a job's pipeline, several resumes can be added at once, candidates can be added by hand with a job, and "Consider for another role" gives one person a second pipeline. Candidates get a notes thread (general or pinned to a stage) and tags. The candidates list gains a job filter, CSV export, and bulk advance and reject. Job cards count people in progress from the pipeline. Spec: docs/superpowers/specs/2026-10-03-recruitiq-ats-workflow-design.md; plan: docs/superpowers/plans/2026-10-03-ats-phase-c-intake-notes-tags.md.

## Decisions worth a look

- Old candidates.notes text is imported as "Earlier note" entries; the column is left in place (read-only) for a lossless downgrade.
- Bulk moves report per candidate: one already rejected does not block the rest, and the UI names it.
- The CSV has no scores and no notes, and neutralizes spreadsheet formulas.
- Hiring managers and the hiring team can now save from a parse and skip the anonymous parse cap.

## Verified

- backend: test_notes_tags, test_intake, test_bulk_export, seed determinism, test_auth route walk, API contract (golden additions only), full suite on the dev database and on a scratch database built from migrations alone
- migration: legacy note import checked on a scratch database (trimmed, blanks skipped), upgrade, downgrade, upgrade
- seed: two runs on a fresh database give identical note and tag counts
- web: typecheck, lint, vitest, next build, Playwright journey
- live: sample resume uploaded as admin with a job lands at Resume submitted on that job; bulk upload, bulk advance and reject, notes, tags, consider for another role, and export checked as admin and as the demo

## Prod follow-up

None required: alembic upgrade head imports any existing notes, and no embedded text changed, so no re-embed. Optional and additive: running seed_demo.py on the droplet adds demo tags and notes to the seeded candidates. It only inserts missing rows, but it is a seed run, so it waits for Sean's go-ahead.
```

```powershell
git push -u origin ats-intake-notes-tags
gh pr create --base main --title "feat: intake, notes, and tags (ATS Phase C)" --body-file C:\Users\seaso\AppData\Local\Temp\claude\pr-c.md
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

Expected: at least 500M available first, no deploy already running, and `==> deployed <sha>` matching `git rev-parse --short origin/main`.

- [ ] **Step 6: Smoke test prod**

```bash
curl -sS -o /dev/null -w "home %{http_code}\n" https://recruitiq.io/
ssh root@157.245.233.229 'curl -sS http://127.0.0.1:8020/health; echo; J=$(curl -s "http://127.0.0.1:8020/api/jobs/?page_size=1" | grep -o "\"id\":[0-9]*" | head -1 | cut -d: -f2); echo "job=$J"; curl -s "http://127.0.0.1:8020/api/jobs/$J" | grep -o "\"active_applications\":[0-9]*"; curl -s "http://127.0.0.1:8020/api/candidates/export.csv?job_id=$J" | head -2; curl -s http://127.0.0.1:8020/api/tags | head -c 200; echo'
curl -sS -o /dev/null -w "candidates %{http_code}\n" https://recruitiq.io/candidates
curl -sS -o /dev/null -w "upload %{http_code}\n" https://recruitiq.io/upload
```

Expected: 200, health ok, a real job id with an `active_applications` count, a CSV header row starting `First name,Last name,Email` (after the BOM) plus one data row, a JSON array from `/api/tags` (empty is fine without the optional seed), and 200 on both pages.

---

## Self-review

**Spec coverage (section 8 Phase C and section 5 rows marked C):**
- Upload ends with "Add to [job] pipeline": Task 6 (`job_id` on save) and Task 15 ("Save and add to [job]"). Covered.
- Manual add candidate (name, email, job): Task 5 (backend, one transaction) and Task 14 (panel). Covered.
- Bulk upload, sequential with a progress list: Task 15 and the Task 12 queue helpers. Covered.
- `notes` table, candidate-level and stage-level threads: Tasks 1, 2, 4, 13. Covered. One thread with stage labels rather than one thread per stage. This is a UI decision, documented in the component.
- `candidate_tags`, lower-kebab-case on write: Tasks 1, 2, 3, 13, with the shared case table pinned on both sides. Covered.
- "Consider for another role": Task 5 (one person, two applications, tested) and Task 13. Covered.
- Candidates page: Add candidate, job filter, CSV export, bulk advance and reject: Tasks 7, 8, 14. Covered.
- Jobs list card count from the pipeline (the deferred Phase A row the contract assigns to C): Tasks 9 and 16. Covered.
- `candidates.notes` read-only (spec 3.2): Task 2 imports it, Task 5 removes it from `CandidateUpdate` and redirects create, and Task 13 stops rendering it. Covered. Dropping the column is a later cleanup, not this phase.
- Acceptance "a resume dropped on Upload becomes a candidate at stage 1 of the chosen job, exercised live": Task 6 tests plus the Task 16 browser check. Covered.
- Contract obligations: new mutating routes are in `ROUTE_PERMISSIONS`, with demo and wrong-staff-role 403 tests (Tasks 3, 4, 5, 6, 7). Lists and exports go through `visible_candidate_ids` (Tasks 3, 4, 8). No scores in the export (Task 8). The seed is synthetic and idempotent (Task 10). The demo keeps working on every screen (checked live in Tasks 13 and 14).

**Placeholder scan:** none of "TBD", "TODO", "similar to", or "add validation" appear. The steps that say "if Phase B already did X" name the exact check and both outcomes.

**Type consistency:** `NoteOut`, `CandidateTagsResponse`, `TagCount` and `BulkTransitionResponse` (backend) match `Note`, `CandidateTags` and `BulkTransitionResult` (web aliases) and the fields the components read (`author_name`, `job_title`, `stage_name`, `succeeded`, `failed`, `results[].candidate_name`, `results[].detail`). `SaveCandidateResponse.application_id` and `already_in_pipeline` match the bulk uploader. `JobResponse.active_applications` matches the jobs page. The bulk route's `BULK_ACTIONS` match the web handler's allowlist and `bulkSummary`'s union. `normalize_tag` and `normalizeTag` share `TAG_CASES`. The `job` URL param on `/candidates` maps to `jobId` in `listCandidates` and to `job_id` in `exportHref`.

## Notes for Phases D and E

- **D:** the filtered-list export already exists. Link to `exportHref({ keyword, status, jobId })` from `web/src/lib/intake.ts` (backend: `GET /api/candidates/export.csv`, built on `_filtered_candidates` in `backend/routers/candidates.py`) rather than writing a second export. `JobResponse.active_applications` is available for dashboard tiles. Notes have timestamps if the activity feed ever wants them, but spec D defines the feed from `application_stages` only.
- **D and E:** any new static route under `/applications/...` in `backend/routers/pipeline.py` must sit above `/applications/{application_id}/{action}`, or it is captured and answers 422 (the Phase C bulk route and its test show the pattern). The same applies to new static paths under `/api/candidates/` relative to `/{candidate_id}`.
- **E:** the public status page must never include notes or tags. Add both to its "carries nothing private" test. Deleting a custom stage sets `notes.stage_id` to NULL rather than deleting the note.
