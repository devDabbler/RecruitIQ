# RecruitIQ Phase 1a — Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean the working tree, remove ~4,300 lines of dead scope (travel, transformation, stub frontend modules), fix the 9 genuinely-failing tests, and consolidate four Alembic trees into one — leaving a repo where `git clone` + `poetry install` + Postgres gives a bootable app and a green test suite.

**Architecture:** Pure consolidation, no new features. Commit the two finished WIP strands; track the untracked ORM package that a fresh clone is currently missing; strip a leaked credential; delete the travel/transformation stack and its four wiring points; debug the 9 real test failures; re-baseline Alembic against the live schema. Neo4j → pgvector, LangChain removal, docker-compose, and CI are **Plan B** (`phase-1b`), planned after this lands.

**Tech Stack:** git, Poetry (Python ^3.11), pytest, Alembic, PostgreSQL 16 (`ats_db`, service `postgresql-x64-16`).

---

## Context You Need Before Starting

Facts verified 2026-08-27 (post-Phase-0, commit `183f0b3` on `main`):

- **Backend imports with 95 routes, 6 agents.** Suite: 50 passed / 9 failed / 92 skipped in ~24 s. Every task must end with these invariants intact or deliberately changed (agent count drops to 5 when the travel agent is deleted).
- **`backend/models/` is entirely untracked** — including `models.py` (the SQLAlchemy ORM imported by 46 files). A fresh clone of the public repo cannot boot. This was hidden by the pre-Phase-0 `.gitignore` and missed in Phase 0 because Task 10 only staged test directories.
- **`backend/alembic.ini:53` contains the real local-Postgres `admin` password** and is tracked in the public repo. `.env` was checked in the spec's security review; this file was missed. The DB listens on localhost only, so exposure is low, but the file must stop carrying it and rotation is recommended (owner action, see Task 2).
- **Four Alembic trees exist:** root `alembic/` (2 files, no versions dir), `backend/alembic/` (7 revisions, head `35a0f301dcaf`), `backend/migrations/` (9 revisions with a merge commit), and untracked `backend/models/alembic/` (2 revisions). The live DB is stamped **`40d08a3d3c48` which exists in none of them** — consolidation must re-baseline, not merge.
- **The travel routers are orphaned** — `backend/routers/travel.py` and `backend/routers/transformation.py` are never imported by `backend/main.py`. Deleting them changes no routes. The travel *services* have four live references (Task 7 lists them).
- **The 9 failures cluster:** 2 × `test_cache_utils` (TypeError in a decorator), 6 × resume-parsing regex tests (experience formats, military section, LinkedIn URL, at-pattern, Roger Waters production parse), 1 × end-to-end integration parse.

### Safety rules for every task

1. **Never `git add -A` or `git add .`** Stage explicit paths.
2. Before every commit run the **PII guard (Task 3 defines it)**. Note: the guard checks *extensions and directories*, not the word "resume" — Phase 0 proved path-name matching false-positives on `resume_parsing/`.
3. Real resumes live under `storage/`, `backend/storage/`, `data/resumes/` — all gitignored. Do not disturb.
4. If `poetry run python -c "import main"` (from `backend/`) stops printing `routes: 95` (or the expected post-deletion count), stop and fix before committing.

---

## File Structure

| File / dir | Change | Responsibility |
|---|---|---|
| `backend/alembic.ini` | Edit line 53 | Stop carrying the DB password; read env var |
| `backend/utils/resume_parsing/{contracts,extractors}` + `pyproject.toml` + `poetry.lock` | Commit as-is | WIP strand 1 (resume parsing) |
| `backend/routers/assistant.py`, `backend/services/{intent_processor,llm_service}.py` | Commit as-is | WIP strand 2 (candidate search) |
| `backend/models/*.py` (except `transformation.py`) | Track | The ORM a fresh clone is missing |
| `backend/utils/resume_parsing/models/` | Track | Pydantic resume schema |
| `dev.py`, `backend/dev.py`, `tools/llm_*.py` | Track | Working dev helpers |
| `mcp_server.py`, `mcp_resume_parsing_tools.py`, `models/__init__.py` | Delete | Incomplete/stray experiments |
| `backend/services/*travel*.py` (4 files), `routers/{travel,transformation}.py`, `travel_assistant_agent.py` | Delete | ~3,750 lines of scope cut |
| `service_registry.py`, `agent_factory.py`, `intent_processor.py`, `tools/check_openroute.py` | Edit/delete | De-wire travel |
| `frontend/modules/{transformation,company_policies,communications,metrics,cache_management}.py` | Delete | Demo-data-only screens |
| `frontend/app.py` | Edit | Imports, fallback stubs, page dict, sidebar |
| `backend/utils/cache_utils.py` + 7 source files TBD by debugging | Fix | The 9 failing tests |
| `backend/alembic/versions/*` | Replace | Single fresh baseline revision |
| root `alembic/`, `alembic.ini`, `backend/migrations/`, `backend/models/alembic/` | Delete | Redundant migration trees |

---

## Task 1: Branch and Baseline

**Files:** none (git refs only)

- [ ] **Step 1: Branch from main**

```powershell
cd C:\Users\seaso\RecruitIQ
git checkout main
git pull origin main
git checkout -b phase-1a-consolidation
```

- [ ] **Step 2: Record the baseline**

```powershell
cd backend
$env:PYTHONIOENCODING='utf-8'
poetry run python -c "import main; print('routes:', len(main.app.routes))"
cd ..
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
```

Expected: `routes: 95`; `9 failed, 50 passed, 92 skipped`. If different, stop — the baseline has drifted and this plan's expectations need re-checking.

---

## Task 2: Strip the Leaked Credential from backend/alembic.ini

**Files:**
- Modify: `backend/alembic.ini:53`
- Modify: `backend/migrations/env.py` and `backend/alembic/env.py` (only if they read `sqlalchemy.url` — verify in Step 2)

- [ ] **Step 1: Replace the hardcoded URL with an env-var override**

In `backend/alembic.ini`, replace line 53 (the `sqlalchemy.url = postgresql+psycopg2://admin:...@localhost:5432/ats_db` line) with:

```ini
sqlalchemy.url =
```

- [ ] **Step 2: Make env.py read POSTGRES_CONN**

Open `backend/migrations/env.py` (this is the env.py the ini's `script_location = migrations` points at). After the `config = context.config` line, add:

```python
import os

database_url = os.getenv("POSTGRES_CONN")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url.replace("postgresql://", "postgresql+psycopg2://", 1))
```

Apply the same edit to `backend/alembic/env.py` if it also calls `config.get_main_option("sqlalchemy.url")` — check with:

```powershell
Select-String -Path backend\alembic\env.py, backend\migrations\env.py -Pattern 'sqlalchemy.url|get_main_option'
```

- [ ] **Step 3: Verify alembic still connects**

```powershell
cd C:\Users\seaso\RecruitIQ\backend
poetry run alembic current
cd ..
```

Expected: prints the stamped revision (`40d08a3d3c48`) with no auth error. `.env` provides `POSTGRES_CONN` via the app settings; if alembic doesn't load `.env`, run with the env var set explicitly:
`$env:POSTGRES_CONN = (Select-String -Path .env -Pattern '^POSTGRES_CONN=(.+)$').Matches[0].Groups[1].Value`

- [ ] **Step 4: Verify no other tracked file carries the password**

```powershell
$pw = (Select-String -Path .env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
git grep -l $pw -- . | ForEach-Object { "*** TRACKED FILE CARRIES PASSWORD: $_ ***" }
"(no output above = clean)"
```

Expected: no output.

- [ ] **Step 5: Commit**

```powershell
git add backend/alembic.ini backend/migrations/env.py backend/alembic/env.py
git commit -m "fix: stop tracking the Postgres password in alembic.ini

The admin credential was hardcoded at backend/alembic.ini:53 in the public
repo. Alembic now reads POSTGRES_CONN from the environment. The password
remains in git history; the DB is localhost-only, and rotation is
recommended as an owner action."
```

> **Owner action (recommended, not blocking):** rotate the local `admin`
> Postgres password and update `.env`. The old value is in public git
> history. Localhost-only exposure, so severity is low.

---

## Task 3: PII Guard (run before every commit in this plan)

**Files:** none — reusable verification.

- [ ] **Step 1: Learn the guard**

```powershell
$staged = git diff --cached --name-only
$bad = $staged | Where-Object { $_ -match '(?i)\.(pdf|docx?|rtf|safetensors|bin|db|sqlite3?)$|^storage/|^backend/storage/|^data/resumes/|^\.env$' }
if ($bad) { "*** ABORT - sensitive files staged ***"; $bad } else { "OK - nothing sensitive staged" }
$big = $staged | Where-Object { Test-Path $_ } | Where-Object { (Get-Item $_).Length -gt 2MB }
if ($big) { "*** ABORT - files over 2 MB staged ***"; $big } else { "OK - no large files staged" }
```

This is the Phase 0 guard corrected: it checks extensions and sensitive directories, not the substring "resume", which false-positived on 60 legitimate `resume_parsing/` test paths.

---

## Task 4: Commit WIP Strand 1 — Resume Parsing

**Files:**
- Stage: `backend/utils/resume_parsing/contracts/resume_contract.py`, `backend/utils/resume_parsing/extractors/structured_extractor.py`, `pyproject.toml`, `poetry.lock`, `backend/utils/resume_parsing/models/`
- Move then stage: `backend/README_Nebius_AI_Parser_Migration.md` → `documentation/NEBIUS_AI_PARSER_MIGRATION.md`

- [ ] **Step 1: Confirm the strand is what the triage said**

```powershell
git diff --stat backend/utils/resume_parsing/contracts/resume_contract.py backend/utils/resume_parsing/extractors/structured_extractor.py pyproject.toml
```

Expected: ~27 added lines in resume_contract (validators for military `branch` and achievement bullets), a one-line method rename in structured_extractor (`generate_text` → `generate_text_async`), and `rapidfuzz` + `pypdfium2` added in pyproject.

- [ ] **Step 2: Move the migration README into documentation/**

```powershell
Move-Item backend\README_Nebius_AI_Parser_Migration.md documentation\NEBIUS_AI_PARSER_MIGRATION.md
```

- [ ] **Step 3: Verify the untracked schema package is imported by the code being committed**

```powershell
Select-String -Path (Get-ChildItem backend\utils\resume_parsing -Recurse -Filter *.py).FullName -Pattern 'from .*models.resume_schema|from \.models|import resume_schema' | Select-Object -First 5
```

Expected: at least one hit (proves `backend/utils/resume_parsing/models/` is load-bearing, not junk). If zero hits, leave that directory out of the commit and note it for Plan B triage.

- [ ] **Step 4: Stage, guard, commit**

```powershell
git add -- backend/utils/resume_parsing/contracts/resume_contract.py backend/utils/resume_parsing/extractors/structured_extractor.py pyproject.toml poetry.lock backend/utils/resume_parsing/models documentation/NEBIUS_AI_PARSER_MIGRATION.md
```

Run the Task 3 guard, then:

```powershell
git commit -m "feat: resume parsing hardening - contract validators, async extraction

Pre-revival WIP, verified working in the live backend. Adds military-branch
and achievement-bullet validators to ResumeContract, switches the structured
extractor to generate_text_async, adds rapidfuzz + pypdfium2, and tracks the
resume_schema Pydantic package. Migration notes in
documentation/NEBIUS_AI_PARSER_MIGRATION.md."
```

- [ ] **Step 5: Verify the backend still imports**

```powershell
cd backend; $env:PYTHONIOENCODING='utf-8'; poetry run python -c "import main; print('routes:', len(main.app.routes))"; cd ..
```

Expected: `routes: 95`.

---

## Task 5: Commit WIP Strand 2 — Skill-Aware Candidate Search

**Files:**
- Stage: `backend/routers/assistant.py`, `backend/services/intent_processor.py`, `backend/services/llm_service.py`

- [ ] **Step 1: Stage, guard, commit**

```powershell
git add -- backend/routers/assistant.py backend/services/intent_processor.py backend/services/llm_service.py
```

Run the Task 3 guard, then:

```powershell
git commit -m "feat: skill-aware candidate search and llm_service cleanup

Pre-revival WIP, verified working. assistant.py gains dual role+skill
scoring with weighted averages and better not-found messages;
intent_processor prioritises database-query intents and adds
role-with-skill patterns; llm_service gets Optional[] annotations, dead
Cohere fallback removal, and drops the orphaned _initialize_nebius_ai."
```

- [ ] **Step 2: Run the test suite — this strand touches intent routing**

```powershell
$env:PYTHONIOENCODING='utf-8'
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
```

Expected: still `9 failed, 50 passed, 92 skipped` — the WIP was already in the working tree during the Phase 0 baseline, so numbers must not move.

---

## Task 6: Track the ORM and Settle Remaining Tree State

**Files:**
- Stage: `backend/models/__init__.py` (if present), `backend/models/models.py`, `backend/models/candidate.py`, `backend/models/job.py`, `backend/models/resume.py`, `backend/models/common.py`
- Do **not** stage: `backend/models/transformation.py` (dies in Task 7), `backend/models/alembic/` (dies in Task 10), `backend/models/sentence_transformers/` (ignored cache), `__pycache__`
- Stage deletions: `April_Drake_Test_Resume_parsed.json`, `tmp_import_check.py`
- Stage: `dev.py`, `backend/dev.py`, `tools/llm_openrouter_test.py`, `tools/llm_smoke_test.py`
- Delete: `mcp_server.py`, `mcp_resume_parsing_tools.py`, `models/__init__.py` (root)

- [ ] **Step 1: Confirm the ORM is untracked and imported**

```powershell
git ls-files backend/models
(Select-String -Path (Get-ChildItem backend -Recurse -Filter *.py).FullName -Pattern 'from backend\.models|from models\.models|models\.models import' | Measure-Object).Count
```

Expected: first command prints nothing (untracked); second prints a count ≥ 40.

- [ ] **Step 2: Stage the ORM files explicitly**

```powershell
git add -- backend/models/models.py backend/models/candidate.py backend/models/job.py backend/models/resume.py backend/models/common.py
if (Test-Path backend\models\__init__.py) { git add -- backend/models/__init__.py }
```

- [ ] **Step 3: Stage the pending tracked deletions and dev helpers**

```powershell
git add -- April_Drake_Test_Resume_parsed.json tmp_import_check.py
git add -- dev.py backend/dev.py tools/llm_openrouter_test.py tools/llm_smoke_test.py
```

- [ ] **Step 4: Delete the experiments**

```powershell
Remove-Item mcp_server.py, mcp_resume_parsing_tools.py, models\__init__.py
```

(These are untracked — deletion is permanent and intended; Sean approved discard on 2026-08-27.)

- [ ] **Step 5: Triage backend/scripts/**

```powershell
Get-ChildItem backend\scripts -Filter *.py | Select-Object Name
```

Delete every file whose name references neo4j/sync/vector-index (they target the store Plan B removes): expect `sync_jobs_to_neo4j.py`, `sync_ats_jobs_to_neo4j.py`, `setup_neo4j_indexes.py`, `check_neo4j_status.py`, `create_vector_indexes.py`, `test_job_sync.py`, `generate_job_embeddings.py`, `import_sample_jobs.py`.

```powershell
Remove-Item backend\scripts\sync_jobs_to_neo4j.py, backend\scripts\sync_ats_jobs_to_neo4j.py, backend\scripts\setup_neo4j_indexes.py, backend\scripts\check_neo4j_status.py, backend\scripts\create_vector_indexes.py, backend\scripts\test_job_sync.py, backend\scripts\generate_job_embeddings.py, backend\scripts\import_sample_jobs.py -ErrorAction SilentlyContinue
Get-ChildItem backend\scripts -Filter *.py | Select-Object Name
```

If files remain that are not Neo4j-related, read each briefly: track it if it is a working utility, delete it if it is scratch. If the directory ends up empty, remove it.

- [ ] **Step 6: Guard, commit**

Run the Task 3 guard, then:

```powershell
git commit -m "fix: track the ORM package a fresh clone was missing

backend/models/ (SQLAlchemy models imported by 46 files) was never
tracked - hidden by the pre-Phase-0 gitignore, so the public repo could
not boot from a fresh clone. Also tracks the dev launch helpers and LLM
smoke tests, removes two parsed-resume/debug leftovers, and drops the
incomplete MCP server experiment and Neo4j sync scripts."
```

- [ ] **Step 7: Verify import and suite once more**

```powershell
cd backend; $env:PYTHONIOENCODING='utf-8'; poetry run python -c "import main; print('routes:', len(main.app.routes))"; cd ..
```

Expected: `routes: 95`.

---

## Task 7: Backend Scope Cuts — Travel and Transformation

**Files:**
- Delete: `backend/services/recruitiq_travel_service.py` (2,526 lines), `backend/services/interview_travel_assistant.py` (456), `backend/services/free_travel_service.py` (284), `backend/services/travel_service.py` (457), `backend/routers/travel.py` (23), `backend/routers/transformation.py` (29), `backend/services/agent_framework/agents/travel_assistant_agent.py`, `backend/models/transformation.py` (untracked), `tools/check_openroute.py`
- Modify: `backend/services/service_registry.py`, `backend/services/agent_framework/agent_factory.py`, `backend/services/intent_processor.py`

- [ ] **Step 1: Find every reference before deleting**

```powershell
Select-String -Path (Get-ChildItem backend,frontend,tools -Recurse -Filter *.py).FullName -Pattern 'travel_service|TravelService|RecruitIQTravelService|TravelAssistantAgent|interview_travel|free_travel|transformation_service|TransformationService' | Group-Object Filename | Select-Object Name, Count
```

Expected referencing files: the four travel services themselves, `service_registry.py`, `agent_factory.py`, `travel_assistant_agent.py`, `intent_processor.py`, `routers/travel.py`, `routers/transformation.py`, `tools/check_openroute.py`, possibly a `transformation_service.py`. Any file NOT on this list must be inspected before proceeding.

- [ ] **Step 2: Edit service_registry.py**

Remove these exact pieces:
- Line 6: `from .recruitiq_travel_service import RecruitIQTravelService`
- Line 29: `self._travel_service = None`
- Lines 62–66: the whole `travel_service` property
- Lines 201–202: `def provide_travel_service(): return registry.travel_service`

- [ ] **Step 3: Edit agent_factory.py**

Remove:
- Line 10: the `TravelAssistantAgent` import
- Line 23: the `"travel": TravelAssistantAgent` registry entry
- Lines 82–87: the `elif agent_type == "travel":` construction branch

- [ ] **Step 4: Excise travel from intent_processor.py**

Known anchor points (line numbers from the pre-edit file; re-grep after each edit):
- Line 19: `from .travel_service import TravelService` — delete
- Line 39: `self.travel_service = None` — delete
- Lines ~141–160: the `"travel_time"` and `"transportation_options"` intent pattern blocks — delete both intents entirely
- Line ~506: remove `"travel_time", "transportation_options"` from `assistant_meta_llama_intents` (leave the list itself)
- Line ~526 onward: the travel synonyms block — delete

Then find the handler methods:

```powershell
Select-String -Path backend\services\intent_processor.py -Pattern 'def .*(travel|transport)|travel_time|transportation_options|travel_service' | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" }
```

Delete every handler method and dispatch branch the grep reveals. Repeat the grep until it returns **zero** lines.

- [ ] **Step 5: Delete the files**

```powershell
Remove-Item backend\services\recruitiq_travel_service.py, backend\services\interview_travel_assistant.py, backend\services\free_travel_service.py, backend\services\travel_service.py, backend\routers\travel.py, backend\routers\transformation.py, backend\services\agent_framework\agents\travel_assistant_agent.py, tools\check_openroute.py
Remove-Item backend\models\transformation.py -ErrorAction SilentlyContinue
```

If Step 1 found a `transformation_service.py` referenced only by the deleted router, delete it too.

- [ ] **Step 6: Verify — import, agents, tests**

```powershell
cd backend; $env:PYTHONIOENCODING='utf-8'; poetry run python -c "import main; print('routes:', len(main.app.routes))"; cd ..
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
```

Expected: `routes: 95` (both deleted routers were never registered), the startup log now registers **5 agents** (no `TravelAssistantAgent`), and the suite is unchanged: `9 failed, 50 passed, 92 skipped`. If import fails, the traceback names the missed reference — fix it, don't restore the files.

- [ ] **Step 7: Stage, guard, commit**

```powershell
git add -- backend/services/recruitiq_travel_service.py backend/services/interview_travel_assistant.py backend/services/free_travel_service.py backend/services/travel_service.py backend/routers/travel.py backend/routers/transformation.py backend/services/agent_framework/agents/travel_assistant_agent.py tools/check_openroute.py backend/services/service_registry.py backend/services/agent_framework/agent_factory.py backend/services/intent_processor.py
```

Run the Task 3 guard, then:

```powershell
git commit -m "refactor: delete the travel and transformation stack (~3,800 lines)

Spec section 5 scope cut. Both routers were orphaned (never registered in
main.py), so the route count is unchanged at 95. The travel agent, its
three services, and their wiring in service_registry, agent_factory and
intent_processor are removed. Agents drop from 6 to 5."
```

---

## Task 8: Frontend Scope Cuts — Five Stub Modules

**Files:**
- Delete: `frontend/modules/transformation.py`, `frontend/modules/company_policies.py`, `frontend/modules/communications.py`, `frontend/modules/metrics.py`, `frontend/modules/cache_management.py`
- Modify: `frontend/app.py`

- [ ] **Step 1: Edit frontend/app.py**

Five edit sites (line numbers pre-edit):
1. Lines 30–33 imports: remove `metrics`, `communications`, `company_policies`, `transformation`, `cache_management` from the `from modules import ...` lists (keep everything else).
2. Lines 40–41 fallback stubs: remove the same five names from the `EmptyModule()` assignment chain and the `.page = lambda: None` chain.
3. Page dict: delete the entries at lines 143 (`"metrics"`), 148 (`"communications"`), 151 (`"company_policies"`), 152 (`"transformation"`), 157 (`"cache_management"`).
4. Line 169: remove `"metrics"` from the recruitment category's module list.
5. Lines 171–174: delete the whole `"transformation"` category. Line 184: remove `"communications"`, `"company_policies"`, `"cache_management"` from the admin category list — if that empties the category, delete the category.

- [ ] **Step 2: Delete the modules**

```powershell
Remove-Item frontend\modules\transformation.py, frontend\modules\company_policies.py, frontend\modules\communications.py, frontend\modules\metrics.py, frontend\modules\cache_management.py
```

- [ ] **Step 3: Verify the frontend parses and has no dangling references**

```powershell
poetry run python -m py_compile frontend/app.py
Select-String -Path frontend\app.py -Pattern 'transformation|company_policies|communications|cache_management|metrics\.'
```

Expected: compile succeeds; grep returns nothing (a hit means a missed wiring point — remove it).

- [ ] **Step 4: Stage, guard, commit**

```powershell
git add -- frontend/modules/transformation.py frontend/modules/company_policies.py frontend/modules/communications.py frontend/modules/metrics.py frontend/modules/cache_management.py frontend/app.py
```

Run the Task 3 guard, then:

```powershell
git commit -m "refactor: remove five demo-data-only frontend screens

transformation, company_policies, communications, metrics and
cache_management rendered hardcoded demo data (spec section 5: 'Nothing
ships stubbed'). Sidebar and fallback wiring in app.py updated to match."
```

---

## Task 9: Fix the Cache-Utils Failures (2 tests)

**Files:**
- Modify: `backend/utils/cache_utils.py` (probable) — confirmed by diagnosis
- Test: `backend/tests/test_cache_utils.py`

Both failures are `TypeError` in `test_cache_result_decorator` / `test_cache_result_decorator_with_cached_value`.

- [ ] **Step 1: Reproduce with full traceback**

```powershell
$env:PYTHONIOENCODING='utf-8'
poetry run pytest backend/tests/test_cache_utils.py -q --tb=long 2>&1 | Select-Object -Last 40
```

- [ ] **Step 2: Diagnose using superpowers:systematic-debugging**

Read the traceback, then read both the test and `backend/utils/cache_utils.py`. Typical causes for a decorator TypeError: signature drift (decorator now requires an argument the test doesn't pass, or vice versa) or an async/sync mismatch. Establish which side changed by checking `git log -p --follow backend/utils/cache_utils.py | Select-Object -First 80`.

- [ ] **Step 3: Fix the product code if it is defective; fix the test only if it asserts a legitimately-changed contract**

Rule: the public decorator API (`@cache_result(...)` as used by callers found via `git grep cache_result -- backend`) is the contract. Make the failing usage consistent with real callers.

- [ ] **Step 4: Verify both tests pass and nothing else regressed**

```powershell
poetry run pytest backend/tests/test_cache_utils.py -q
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
```

Expected: `2 passed` locally; overall failures drop 9 → 7.

- [ ] **Step 5: Commit**

```powershell
git add -- backend/utils/cache_utils.py backend/tests/test_cache_utils.py
git commit -m "fix: repair cache_result decorator contract

(Adjust message to describe the actual root cause found in diagnosis.)"
```

---

## Task 10: Fix the Six Parsing-Regex Failures

**Files:**
- Modify: `backend/utils/resume_parsing/extractors/regex_extractor.py` and/or `backend/utils/resume_parsing/extractors/military_extractor.py` (probable) — confirmed by diagnosis
- Tests: `backend/tests/simple_experience_test.py` (2), `backend/tests/test_military_extraction_regex.py` (1), `backend/tests/test_resume_linkedin_extraction.py` (1), `backend/tests/test_resume_parsing.py::test_parse_roger_waters_resume_production` (1), `backend/utils/resume_parsing/tests/test_experience_at_pattern.py` (1)

These six likely share root causes in experience-block segmentation. The known marquee defect is character corruption: `Expected 'Full Stack Developer', got 'Full Stack "eveloper'`.

- [ ] **Step 1: Capture all six tracebacks in one run**

```powershell
$env:PYTHONIOENCODING='utf-8'
poetry run pytest backend/tests/simple_experience_test.py backend/tests/test_military_extraction_regex.py backend/tests/test_resume_linkedin_extraction.py "backend/tests/test_resume_parsing.py::TestRealResumeParsing::test_parse_roger_waters_resume_production" backend/utils/resume_parsing/tests/test_experience_at_pattern.py -q --tb=long 2>&1 | Out-File -Encoding utf8 parsing_failures.log
Get-Content parsing_failures.log -Tail 60
```

- [ ] **Step 2: Diagnose with superpowers:systematic-debugging — one root cause at a time**

Group the tracebacks by the function they die in (expect most to land in `regex_extractor.py`). For the `"eveloper` corruption specifically: reproduce with a minimal string through the same code path and find where a character is consumed (typical culprits: an off-by-one slice after a quote-stripping regex, or a `re.sub` with a capture group that swallows a leading character). Write the failing minimal repro as a new test case **first**, then fix.

- [ ] **Step 3: Fix product code, not assertions**

These tests were kept in Phase 0 precisely because they assert real desired behaviour. Only adjust a test if diagnosis proves the assertion describes behaviour that was deliberately changed — and record why in the commit message.

- [ ] **Step 4: Verify after each root-cause fix**

```powershell
poetry run pytest backend/tests/simple_experience_test.py backend/tests/test_military_extraction_regex.py backend/tests/test_resume_linkedin_extraction.py backend/tests/test_resume_parsing.py backend/utils/resume_parsing/tests/test_experience_at_pattern.py -q --tb=no 2>&1 | Select-Object -Last 2
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
```

Expected end state: those five files fully pass; overall failures drop to 1.

- [ ] **Step 5: Clean up and commit (one commit per root cause is fine)**

```powershell
Remove-Item parsing_failures.log
git add -- backend/utils/resume_parsing backend/tests
git commit -m "fix: <root cause> in experience extraction

(Describe the actual defect: e.g. the quote-stripping regex consumed the
following character, corrupting titles like 'Full Stack Developer'.)"
```

---

## Task 11: Fix the End-to-End Integration Failure (1 test)

**Files:**
- Test: `backend/utils/resume_parsing/tests/test_resume_parsing_integration.py::test_parse_end_to_end[resume_path0]`

- [ ] **Step 1: Reproduce and read what it needs**

```powershell
$env:PYTHONIOENCODING='utf-8'
poetry run pytest "backend/utils/resume_parsing/tests/test_resume_parsing_integration.py" -q --tb=long 2>&1 | Select-Object -Last 40
```

- [ ] **Step 2: Decide by what the failure is**

- If it fails on the same parsing defects as Task 10, it may now pass — run it after Task 10 before doing anything.
- If it requires a live LLM provider (Nebius 401), it belongs with the Task 9-of-Phase-0 quarantine: add `pytestmark = pytest.mark.skip(reason="Requires a working LLM provider (Nebius key dead, HTTP 401 as of 2026-08-27). Re-enable with the Phase 2 provider chain.")` after its imports.
- If it fails on a missing fixture file, skip with the fixture-policy reason used in Phase 0 (real resumes are excluded by policy; rewrite against a synthetic fixture in Phase 2).

- [ ] **Step 3: Verify zero failures suite-wide**

```powershell
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
```

Expected: `0 failed`. Record the exact passed/skipped counts — the README update in Task 12 needs them.

- [ ] **Step 4: Commit**

```powershell
git add -- backend/utils/resume_parsing/tests/test_resume_parsing_integration.py
git commit -m "test: resolve the end-to-end parsing integration failure

(Describe: fixed by Task 10's root cause / skipped pending provider chain.)"
```

---

## Task 12: Update README and TESTING.md with the New Reality

**Files:**
- Modify: `README.md` (Honest status section)
- Modify: `documentation/TESTING.md`

- [ ] **Step 1: Update the test-suite bullet in README.md**

Replace the line:

```markdown
- **The test suite:** 50 passing, 9 failing, 92 skipped. The failures are
  real defects, left visible on purpose. See
  [documentation/TESTING.md](documentation/TESTING.md).
```

with (substitute the real counts from Task 11 Step 3):

```markdown
- **The test suite:** <PASSED> passing, 0 failing, <SKIPPED> skipped. The
  nine defects that were failing visibly after Phase 0 — including a
  character-corruption bug in experience parsing — are fixed. See
  [documentation/TESTING.md](documentation/TESTING.md).
```

- [ ] **Step 2: Update documentation/TESTING.md**

Replace the "Tests that still fail" section with a short "Recently fixed" section describing the actual root causes found in Tasks 9–11 (keep the `Full Stack "eveloper` example as the before/after illustration).

- [ ] **Step 3: Stage, guard, commit**

```powershell
git add README.md documentation/TESTING.md
git commit -m "docs: update test status - suite is green

Phase 1a fixed the nine visible failures. README honest-status and
TESTING.md now describe the root causes instead of promising fixes."
```

---

## Task 13: Consolidate Alembic to One Tree

**Files:**
- Keep + rebuild: `backend/alembic/` (becomes the only tree), `backend/alembic.ini`
- Delete: `backend/migrations/` (9 revisions), root `alembic/` + root `alembic.ini`, `backend/models/alembic/` (untracked)
- Create: one fresh baseline revision in `backend/alembic/versions/`

The live DB stamp `40d08a3d3c48` exists in no tree, so history is unrecoverable by merging. Strategy: generate a single full-schema baseline from the live models against a scratch database, stamp the live DB with it, delete everything else.

- [ ] **Step 1: Point backend/alembic.ini at the alembic/ tree**

In `backend/alembic.ini`, change `script_location = migrations` to `script_location = alembic`.

- [ ] **Step 2: Empty the old revisions from the kept tree**

```powershell
Remove-Item backend\alembic\versions\*.py
```

- [ ] **Step 3: Create a scratch DB and generate the baseline against it**

```powershell
$env:PGPASSWORD = (Select-String -Path .env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U admin -h localhost ats_baseline_scratch
cd backend
$env:POSTGRES_CONN = "postgresql://admin:$env:PGPASSWORD@localhost:5432/ats_baseline_scratch"
poetry run alembic revision --autogenerate -m "baseline: full schema consolidated from three legacy trees"
cd ..
```

Expected: one new file in `backend/alembic/versions/` containing `create_table` calls for every table in `backend/models/models.py` (candidates, resumes, jobs, skills, candidate_skills, agent_memories with its `Vector(384)` column, job_applications, saved_jobs, candidate_pitches). If the revision is near-empty, `env.py`'s `target_metadata` is not pointing at `models.models.Base` — fix that first.

- [ ] **Step 4: Prove the baseline builds a complete schema**

```powershell
cd backend
poetry run alembic upgrade head
cd ..
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U admin -h localhost -d ats_baseline_scratch -c "\dt"
```

Expected: all tables listed. Then compare against the live DB's table list:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U admin -h localhost -d ats_db -c "\dt"
```

Any table in `ats_db` but not in the baseline is a model/DB drift — add the missing model or note it as intentionally dropped before proceeding.

- [ ] **Step 5: Stamp the live DB and drop the scratch**

```powershell
cd backend
$env:POSTGRES_CONN = "postgresql://admin:$env:PGPASSWORD@localhost:5432/ats_db"
poetry run alembic stamp head
poetry run alembic current
cd ..
& "C:\Program Files\PostgreSQL\16\bin\dropdb.exe" -U admin -h localhost ats_baseline_scratch
```

Expected: `alembic current` prints the new baseline revision id.

- [ ] **Step 6: Delete the redundant trees**

```powershell
git rm -r --quiet backend/migrations alembic alembic.ini
Remove-Item -Recurse -Force backend\models\alembic
```

- [ ] **Step 7: Verify the app is indifferent**

```powershell
cd backend; $env:PYTHONIOENCODING='utf-8'; poetry run python -c "import main; print('routes:', len(main.app.routes))"; cd ..
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
```

Expected: routes unchanged, suite still green.

- [ ] **Step 8: Stage, guard, commit**

```powershell
git add -- backend/alembic.ini backend/alembic backend/migrations alembic alembic.ini
```

Run the Task 3 guard, then:

```powershell
git commit -m "refactor: consolidate four Alembic trees into one fresh baseline

The live DB was stamped 40d08a3d3c48 - a revision existing in none of the
four trees (backend/alembic, backend/migrations, root alembic, untracked
backend/models/alembic), so histories were unmergeable. A single
autogenerated baseline now describes the full schema; ats_db is stamped
to it; the other trees are deleted."
```

---

## Task 14: Final Verification, Merge, Push

**Files:** none

- [ ] **Step 1: Full gate**

```powershell
git status --short
cd backend; $env:PYTHONIOENCODING='utf-8'; poetry run python -c "import main; print('routes:', len(main.app.routes))"; cd ..
$env:PYTHONIOENCODING='utf-8'
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
$tracked = git ls-files
$bad = $tracked | Where-Object { $_ -match '(?i)\.env$|resume.*\.(pdf|docx?)$|\.safetensors$|\.bin$|^storage/|^data/resumes/' }
if ($bad) { "*** TRACKED SENSITIVE FILES ***"; $bad } else { "OK - nothing sensitive tracked" }
$pw = (Select-String -Path .env -Pattern '^POSTGRES_PASSWORD=(.+)$').Matches[0].Groups[1].Value
git grep -l $pw -- . | ForEach-Object { "*** PASSWORD IN TRACKED FILE: $_ ***" }
```

Expected: clean tree (or known ignored leftovers), expected route count, `0 failed`, nothing sensitive, no password hits.

- [ ] **Step 2: Boot the app end-to-end once**

```powershell
cd backend
$env:PYTHONIOENCODING='utf-8'
Start-Process -NoNewWindow poetry -ArgumentList 'run','python','-m','uvicorn','main:app','--host','127.0.0.1','--port','8010'
Start-Sleep -Seconds 12
Invoke-RestMethod http://127.0.0.1:8010/health
Invoke-RestMethod http://127.0.0.1:8010/api/jobs | Select-Object -First 1
cd ..
```

Expected: health 200 and real job data. Stop the server afterwards.

- [ ] **Step 3: Merge and push**

```powershell
git checkout main
git merge --ff-only phase-1a-consolidation
git push origin main
git branch -d phase-1a-consolidation
```

---

## Deliberately Deferred to Plan B (phase-1b)

| Item | Why deferred |
|---|---|
| Neo4j → pgvector (768-dim, nomic-embed-text via ollama.sentienttrader.ai) | Real refactoring across graph_service (1,070 lines), rag_service, job_service; planned against the post-1a codebase |
| LangChain removal | Entangled with the Neo4j work — rag_service and neo4j_vector_custom are the LangChain surface |
| docker-compose | Phase-0 deferral note stands: composing around Neo4j is wasted work; also Docker is not installed on this machine |
| GitHub Actions CI | Lands with compose; suite is green after 1a so the badge ships green |
| Postgres `admin` password rotation | Owner action, recommended in Task 2 |

## Done When

- Working tree clean; the two WIP strands and the ORM package are committed.
- `backend/alembic.ini` carries no credential; `git grep` for the password finds nothing tracked.
- Travel/transformation stack gone (~3,800 lines); frontend has no stub screens; agents register 5.
- Test suite: **0 failed**, with README and TESTING.md quoting the real counts.
- Exactly one Alembic tree; `alembic current` matches its head on `ats_db`.
- `import main` still succeeds with the same route count recorded in Task 1.
- Merged to `main`, pushed.
