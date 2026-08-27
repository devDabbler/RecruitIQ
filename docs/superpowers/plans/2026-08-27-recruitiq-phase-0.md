# RecruitIQ Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `github.com/devDabbler/RecruitIQ` presentable to a Talent Acquisition leader who will skim it for ninety seconds and to an engineer who will spend ten minutes checking whether it is real — without changing any application behaviour.

**Architecture:** Pure repository hygiene and narrative. Five moves: strip the 86.7 MB blob by deleting the one branch that references it; rewrite `.gitignore` so documentation and tests become visible while PII stays excluded; delete test code that was never valid; replace a sales-pitch README with the ten-repo lineage story; archive two stale public repos. No functional source changes except test deletions.

**Tech Stack:** git, GitHub CLI (`gh` 2.89.0, authenticated as `devDabbler` with `repo` scope), Poetry (Python ^3.11), pytest.

---

## Context You Need Before Starting

Read `docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md` — especially §1 (audience), §8 (publishing), §2.1–§2.3 (verified runtime baseline). Key facts established on 2026-08-27 that this plan depends on:

- **`origin/main` is already clean.** Its history is 7 commits from `2214261 "Initial commit (clean history)"` (2025-08-27). The 86.7 MB `model.safetensors` blob is reachable **only** from `origin/update-recruiq-project`, introduced in commit `2749497`. Verified with `git rev-list --objects origin/main`.
- **0 forks, 0 stars, 1 watcher.** Nobody has cloned the blob. This is why we keep the repo instead of starting fresh — the 2025-04-26 creation date is corroborating evidence for a README that claims two years of work.
- **Real resumes with PII are on disk** (~16.1 MB under `storage/`, `backend/storage/`, `data/resumes/`) including `Sean Collins Resume 2025.pdf`. They are correctly gitignored. **Do not let them become tracked.** Spec §6 commits to "synthetic only — no real resumes."
- **`data/Recruiting Solution POC.pdf` (4.87 MB) is untracked but NOT ignored.** A careless `git add -A` would commit it.
- **Test suite baseline:** 194 collected → 59 passed, 41 failed, 11 errored, 82 skipped, in 115s.

### Safety rules for every task

1. **Never run `git add -A` or `git add .`** in this plan. Always stage explicit paths.
2. After any staging, run the PII guard from Task 4 before committing.
3. Work on `main`. Do not create a new repo.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `.gitignore` | Rewrite | Show markdown + tests; keep PII, binaries, secrets out |
| `.env.example` | Create | Document all 96 env vars with safe placeholder values |
| `LICENSE` | Create | MIT text — README already claims MIT but no file exists |
| `README.md` | Rewrite | Lineage narrative replacing the sales-deck content |
| `pytest.ini` | Modify | `--ignore=docs` → `--ignore=documentation` after the rename |
| `docs/` → `documentation/` | Resolve rename | Finish the in-flight uncommitted move |
| `backend/z_ollama_backup/`, `backend/patches/`, `backend/examples/` | Delete | 26 dead files |
| ~19 test files | Delete / mark skip | Remove invalid tests, quarantine dead-provider tests |

---

## Task 1: Create a Safety Net

**Files:** none (git refs only)

- [ ] **Step 1: Record the current state**

```powershell
cd C:\Users\seaso\RecruitIQ
git tag phase0-start
git rev-parse origin/update-recruiq-project | Out-File -FilePath C:\Users\seaso\recruitiq-deleted-branch-sha.txt -Encoding ascii
Get-Content C:\Users\seaso\recruitiq-deleted-branch-sha.txt
```

Expected: a 40-character SHA printed. This is the only record of the branch we are about to delete; keep the file until Phase 1 completes.

- [ ] **Step 2: Confirm the working tree state is understood**

```powershell
git status --short | Measure-Object -Line
```

Expected: a non-zero count. There is an in-flight uncommitted rename of `docs/scripts` → `documentation/scripts` (deletions staged as `D`, new files as `??`). Task 5 resolves it. Do not commit anything yet.

- [ ] **Step 3: Verify the blob's reachability one more time before deleting anything**

```powershell
$blob = 'b117b07b913054e2d7fcaa8b0c1faf74b4b66a32'
if (git rev-list --objects origin/main | Select-String $blob) { "STOP - blob IS on main, do not proceed" } else { "OK - blob is not on main" }
```

Expected: `OK - blob is not on main`

If it prints `STOP`, halt this plan and re-open the fresh-repo decision from spec §8.

---

## Task 2: Delete the Stale Branch and Reclaim 86.7 MB

**Files:** none (git refs only)

- [ ] **Step 1: Delete the remote branch**

```powershell
cd C:\Users\seaso\RecruitIQ
gh api -X DELETE repos/devDabbler/RecruitIQ/git/refs/heads/update-recruiq-project
```

Expected: no output, exit code 0.

- [ ] **Step 2: Confirm GitHub now has only main**

```powershell
gh api repos/devDabbler/RecruitIQ/branches --jq '.[].name'
```

Expected: `main` only.

- [ ] **Step 3: Delete the local tracking ref and expire the reflog**

```powershell
git remote prune origin
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

Expected: `git gc` runs for 10–60 seconds. No errors.

- [ ] **Step 4: Verify the blob is gone and measure the result**

```powershell
$blob = 'b117b07b913054e2d7fcaa8b0c1faf74b4b66a32'
$found = git cat-file -e $blob 2>&1
if ($LASTEXITCODE -eq 0) { "blob still present locally" } else { "blob GONE locally" }
"{0:N1} MB .git" -f ((Get-ChildItem .git -Recurse -Force | Measure-Object Length -Sum).Sum/1MB)
```

Expected: `blob GONE locally`, and `.git` between 1 and 4 MB (was 88.5 MB).

> **Note:** GitHub retains unreachable objects until its own GC runs, so the blob may briefly remain fetchable by direct SHA. It is no longer fetched by `git clone`, which is what matters. If you want it purged server-side immediately, ask GitHub Support to run GC on the repo.

---

## Task 3: Rewrite .gitignore

**Files:**
- Modify: `.gitignore` (full rewrite)

The current file hides every `.md` (line 89) and every test (lines 67–71). It must stop doing both while still excluding PII, binaries and secrets.

- [ ] **Step 1: Write the new .gitignore**

Replace the entire contents of `.gitignore` with:

```gitignore
# ==== OS & IDE ====
.DS_Store
.DS_Store?
Thumbs.db
._*
*.swp
*.swo
.idea/
.vscode/
.cursor/

# ==== Secrets ====
# .env holds live API keys. .env.example is committed and MUST stay visible.
.env
.env.*
!.env.example
.python-version

# ==== Python ====
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.mypy_cache/
.pyre/
.ipynb_checkpoints/
.cache/
.coverage
htmlcov/
.venv/
venv/
env/
ENV/
build/
dist/
*.egg-info/

# ==== Logs & Temp ====
logs/
*.log
*.tmp
*.bak
*.orig
*.rej
*.backup

# ==== Databases & dumps ====
*.db
*.sqlite
*.sqlite3
*.db-journal
**/*.sql
**/*.dump
**/*.sql.gz
**/*.sql.zip

# ==== Large model weights ====
# An 86.7 MB model.safetensors was committed once. Never again.
*.pt
*.pth
*.onnx
*.tflite
*.bin
*.safetensors
backend/models/sentence_transformers/

# ==== Node ====
node_modules/
.npm/
.yarn/

# ==== PII: real resumes and uploads ====
# Spec §6: this project ships synthetic data only. Real candidate documents
# must never be tracked. These rules are load-bearing - do not relax them.
storage/
backend/storage/
data/resumes/
data/results/
exports/
backups/
training_data/
**/[Rr]esume*.pdf
**/[Rr]esume*.doc
**/[Rr]esume*.docx
**/[Rr]esume*.rtf
**/[Rr]esume*.txt
**/*[Rr]esume*.pdf
**/*[Rr]esume*.doc
**/*[Rr]esume*.docx
**/*[Rr]esume*.rtf
**/*[Rr]esume*.txt
**/[Cc][Vv]*.pdf
**/[Cc][Vv]*.doc
**/[Cc][Vv]*.docx
**/[Cc][Vv]*.rtf
**/[Cc][Vv]*.txt
# Untracked 4.87 MB pitch deck - not a resume, so named explicitly.
data/Recruiting Solution POC.pdf

# ==== Legacy / dead ====
backend/z_ollama_backup/
working_mcp_launcher.py

# ==== Deliberately NOT ignored ====
# Markdown: the old rule `**/*.md` hid all 19 documentation/ files from GitHub.
# Tests: the old rules `tests/`, `**/tests/`, `**/test_*.py`, `**/*_test.py`
# hid 138 test files. Both are now visible. See docs/decisions/.
```

- [ ] **Step 2: Verify markdown is now visible**

```powershell
cd C:\Users\seaso\RecruitIQ
git check-ignore -v -- documentation\API.md
if ($LASTEXITCODE -ne 0) { "OK - markdown no longer ignored" } else { "STILL IGNORED" }
```

Expected: `OK - markdown no longer ignored`

- [ ] **Step 3: Verify tests are now visible**

```powershell
git check-ignore -v -- backend\tests\test_cache_utils.py
if ($LASTEXITCODE -ne 0) { "OK - tests no longer ignored" } else { "STILL IGNORED" }
```

Expected: `OK - tests no longer ignored`

- [ ] **Step 4: Verify PII is STILL ignored — this is the critical check**

```powershell
$mustBeIgnored = @(
  'data\resumes\Sean Collins Resume 2025.pdf',
  'storage\70b27498-6357-4fe7-adc0-aa3548f473ba\Clint_Forest_Resume.pdf',
  'backend\storage\0679756e-cc62-498a-b10e-a3db107a0aba\Roger Waters Resume.pdf',
  'data\Recruiting Solution POC.pdf',
  '.env'
)
$bad = 0
foreach ($p in $mustBeIgnored) {
  git check-ignore -q -- $p
  if ($LASTEXITCODE -ne 0) { "*** LEAK: $p is NOT ignored ***"; $bad++ }
}
if ($bad -eq 0) { "OK - all PII and secrets still ignored" }
```

Expected: `OK - all PII and secrets still ignored`

**If any line prints `LEAK`, stop and fix `.gitignore` before continuing.**

- [ ] **Step 5: Commit**

```powershell
git add .gitignore
git commit -m "chore: stop ignoring markdown and tests, harden PII rules

The rule **/*.md hid all 19 documentation/ files from GitHub, and four
rules hid 138 test files. Both are now visible. PII rules for storage/,
data/resumes/ and resume documents are kept and extended."
```

---

## Task 4: PII Guard (run before every later commit)

**Files:** none — this is a reusable verification step.

- [ ] **Step 1: Learn the guard command**

Before **every** commit in Tasks 5–13, run this against the staged set:

```powershell
$staged = git diff --cached --name-only
$suspicious = $staged | Where-Object { $_ -match '(?i)resume|\.pdf$|\.docx?$|^storage/|^data/resumes/|^\.env$|\.safetensors$|\.bin$' }
if ($suspicious) { "*** ABORT - suspicious files staged ***"; $suspicious } else { "OK - nothing sensitive staged" }
$big = $staged | Where-Object { Test-Path $_ } | Where-Object { (Get-Item $_).Length -gt 2MB }
if ($big) { "*** ABORT - files over 2 MB staged ***"; $big } else { "OK - no large files staged" }
```

Expected on a clean stage: `OK - nothing sensitive staged` and `OK - no large files staged`.

If either aborts, run `git restore --staged <path>` for the offending file and re-check.

---

## Task 5: Resolve the docs → documentation Rename

**Files:**
- Modify: `pytest.ini:12`
- Stage: deletion of `docs/scripts/**`, addition of `documentation/**`
- Keep: `docs/superpowers/` (specs and plans live here)

The working tree has `docs/scripts/*` deleted and `documentation/scripts/*` untracked. `pytest.ini` still says `--ignore=docs`, so dev scripts under `documentation/scripts` are now collected as tests — that is where several of the 11 fixture errors come from.

- [ ] **Step 1: Fix the pytest ignore path**

In `pytest.ini`, replace line 12:

```ini
addopts = --ignore=docs
```

with:

```ini
addopts = --ignore=documentation --ignore=docs
```

- [ ] **Step 2: Remove compiled artifacts from the moved scripts**

```powershell
cd C:\Users\seaso\RecruitIQ
Remove-Item -Recurse -Force documentation\scripts\__pycache__ -ErrorAction SilentlyContinue
"pycache removed"
```

- [ ] **Step 3: Verify collection no longer picks up documentation scripts**

```powershell
poetry run pytest --collect-only -q 2>&1 | Select-Object -Last 3
```

Expected: a collected count, and it should be **lower than 194** because `documentation/scripts` is now ignored. Record the new number.

- [ ] **Step 4: Stage the rename and the documentation tree**

```powershell
git add pytest.ini
git add -- docs/scripts
git add -- documentation
git add -- "docs/RecruitIQ_Recruiting_Database_Tranformation_Service"
```

- [ ] **Step 5: Run the PII guard from Task 4**

Expected: both `OK` lines. The four PNGs under `documentation/image/` are ~148 KB each and are fine.

- [ ] **Step 6: Commit**

```powershell
git commit -m "chore: complete docs -> documentation rename, fix pytest ignore path

pytest.ini still ignored 'docs', so dev scripts under documentation/scripts
were being collected as tests. 19 documentation files are now tracked and
visible for the first time."
```

---

## Task 6: Delete Dead Directories

> **OUTCOME 2026-08-27 — the gate fired. `backend/patches/` MUST NOT be deleted.**
> It is star-imported at the top of the application entrypoint:
> ```
> backend/main.py:2              from backend.patches import *
> backend/services/intent_processor.py:2   import backend.patches  # Windows compatibility patches
> ```
> Spec §4.5 was right that `patches/` is live. `z_ollama_backup/` and
> `examples/` were deleted and verified safe — the only reference to
> `z_ollama_backup` is a comment in `regex_extractor.py:7`. Backend still
> imports with 95 routes. **Status: complete, with `patches/` deliberately
> retained.**

**Files:**
- Delete: `backend/z_ollama_backup/` (10 files) — DONE
- ~~Delete: `backend/patches/` (15 files)~~ **KEEP — live import, see above**
- Delete: `backend/examples/` (1 file) — DONE

- [ ] **Step 1: Confirm nothing imports from them**

```powershell
cd C:\Users\seaso\RecruitIQ
Select-String -Path (Get-ChildItem backend,frontend -Recurse -Filter *.py | Where-Object { $_.FullName -notmatch 'z_ollama_backup|\\patches\\|\\examples\\' }).FullName -Pattern 'z_ollama_backup|from patches|import patches|backend\.patches|backend\.examples' | Select-Object -First 10
```

Expected: no output. If there are hits, note them — spec §4.5 says `patches/robust_json_extractor.py` participates in JSON repair, so a live import is possible. If anything imports it, **do not delete that directory**; report and stop.

- [ ] **Step 2: Delete the directories**

```powershell
Remove-Item -Recurse -Force backend\z_ollama_backup, backend\patches, backend\examples
"deleted"
```

- [ ] **Step 3: Verify the backend still imports**

```powershell
cd C:\Users\seaso\RecruitIQ\backend
$env:PYTHONIOENCODING='utf-8'
poetry run python -c "import main; print('IMPORT OK'); print('routes:', len(main.app.routes))"
cd C:\Users\seaso\RecruitIQ
```

Expected: `IMPORT OK` and `routes: 95`.

**If this fails, restore with `git checkout -- backend/patches` and investigate.**

- [ ] **Step 4: Stage, guard, commit**

```powershell
git add -- backend/z_ollama_backup backend/patches backend/examples
```

Run the Task 4 PII guard, then:

```powershell
git commit -m "chore: delete dead directories (z_ollama_backup, patches, examples)

26 files, no live imports. Verified backend still imports with 95 routes."
```

---

## Task 7: Delete Script-Style Files Masquerading as Tests

**Files (delete whole file):**
- `backend/tests/test_parsing_fix.py`
- `backend/tests/test_production_bullet_formatting.py`
- `backend/utils/resume_parsing/tests/test_education_e2e.py`
- `backend/utils/resume_parsing/tests/test_education_extraction.py`
- `backend/utils/resume_parsing/tests/test_linkedin_extraction_specific.py`
- `backend/utils/resume_parsing/tests/test_remote.py`

These produce all 11 collection errors. Every one fails with `fixture '<name>' not found` — they are functions named `test_*` that take plain arguments (`pdf_path`, `text`, `resume_path`, `description`, `config`, `file_path`) and were written to be called by hand. They have never been valid pytest tests.

- [ ] **Step 1: Confirm each file's test functions take non-fixture arguments**

```powershell
cd C:\Users\seaso\RecruitIQ
$files = @(
 'backend\tests\test_parsing_fix.py',
 'backend\tests\test_production_bullet_formatting.py',
 'backend\utils\resume_parsing\tests\test_education_e2e.py',
 'backend\utils\resume_parsing\tests\test_education_extraction.py',
 'backend\utils\resume_parsing\tests\test_linkedin_extraction_specific.py',
 'backend\utils\resume_parsing\tests\test_remote.py'
)
foreach ($f in $files) { "--- $f ---"; Select-String -Path $f -Pattern '^def test_' | ForEach-Object { $_.Line } }
```

Expected: each `def test_*` takes at least one argument that is not a defined fixture.

- [ ] **Step 2: Delete them**

The array is redefined here because `$files` from Step 1 does not survive into
a separate command.

```powershell
cd C:\Users\seaso\RecruitIQ
$files = @(
 'backend\tests\test_parsing_fix.py',
 'backend\tests\test_production_bullet_formatting.py',
 'backend\utils\resume_parsing\tests\test_education_e2e.py',
 'backend\utils\resume_parsing\tests\test_education_extraction.py',
 'backend\utils\resume_parsing\tests\test_linkedin_extraction_specific.py',
 'backend\utils\resume_parsing\tests\test_remote.py'
)
Remove-Item $files
"deleted $($files.Count) files"
```

- [ ] **Step 2b: Remove the seventh fixture-error test, which lives in a file we keep**

The 11 errors span **seven** files, not six. The eleventh is
`test_resume_parser_with_real_file` inside
`backend/utils/resume_parsing/tests/test_extractthinker_pipeline.py` — a file
Task 8 modifies rather than deletes. Remove just that one method now, or Step 3
below will still report an error.

Open `backend/utils/resume_parsing/tests/test_extractthinker_pipeline.py` and
delete the entire `test_resume_parser_with_real_file` method from
`TestExtractThinkerPipeline`. Leave the rest of the class alone; Task 8 removes
four more methods from it.

```powershell
Select-String -Path backend\utils\resume_parsing\tests\test_extractthinker_pipeline.py -Pattern 'test_resume_parser_with_real_file'
```

Expected: no output.

- [ ] **Step 3: Verify zero collection errors remain**

```powershell
$env:PYTHONIOENCODING='utf-8'
poetry run pytest --collect-only -q 2>&1 | Select-Object -Last 5
```

Expected: a collected count with **no `errors`** in the summary line.

- [ ] **Step 4: Stage, guard, commit**

Shell variables do not survive between separate commands, so the paths are
repeated explicitly here rather than reusing `$files`.

```powershell
git add -- backend/tests/test_parsing_fix.py backend/tests/test_production_bullet_formatting.py backend/utils/resume_parsing/tests/test_education_e2e.py backend/utils/resume_parsing/tests/test_education_extraction.py backend/utils/resume_parsing/tests/test_linkedin_extraction_specific.py backend/utils/resume_parsing/tests/test_remote.py backend/utils/resume_parsing/tests/test_extractthinker_pipeline.py
```

Run the Task 4 PII guard, then:

```powershell
git commit -m "test: remove script-style files that were never valid tests

These six files, plus one method in test_extractthinker_pipeline.py, produced
all 11 collection errors. Each defines test_* functions taking plain arguments
(pdf_path, text, resume_path, description, config, file_path) that pytest tries
to resolve as fixtures. They were written to be run by hand, not by pytest."
```

---

## Task 8: Delete Tests That Assert on Removed Private APIs

**Files (delete whole file):**
- `backend/tests/test_all_experiences.py`
- `backend/tests/test_bullet_formatting.py`
- `backend/tests/test_bullet_point_fix.py`
- `backend/tests/test_comprehensive_resume_fixes.py`
- `backend/tests/test_experience_header_formats.py`
- `backend/tests/test_final_bullet_fix.py`
- `backend/tests/test_final_fixes.py`
- `backend/tests/test_resume_parser_fix.py`
- `backend/tests/test_skills_formatting_fix.py`

**Files (delete specific tests, keep the file):**
- `backend/utils/resume_parsing/tests/test_extractors.py` — remove `TestAIExtractor::test_ensure_array_fields` and `TestNLPExtractor::test_extract_education_with_ner`
- `backend/utils/resume_parsing/tests/test_extractthinker_pipeline.py` — remove `test_intelligent_text_processor`, `test_structured_extractor`, `test_contract_validation`, `test_configuration_loading`

Every one of these reaches into a private method or constructor kwarg that no longer exists. Testing private APIs was the original mistake; these assert on implementation details that were legitimately refactored away.

| Missing attribute / signature | Tests affected |
|---|---|
| `RegexExtractor._process_experience_description` | 4 |
| `RegexExtractor._clean_skill_name` | 4 |
| `NebiusAIResumeParser._extract_job_info_from_block` | 4 |
| `RegexExtractor._format_experience...` | 1 |
| `RegexExtractor._extract_experience` | 1 |
| `AIExtractor._ensure_array_fields` | 1 |
| `_complete_truncated_sentence()` arity | 1 |
| `NLPExtractor(llm_service=...)` | 1 |
| `TextProcessingConfig(consolidate_bullets=...)` | 1 |
| `StructuredExtractor(nebius_ai_service=...)` | 1 |
| `ResumeParser(storage_service=...)` | 1 |

- [ ] **Step 1: Delete the whole-file cases**

```powershell
cd C:\Users\seaso\RecruitIQ
$stale = @(
 'backend\tests\test_all_experiences.py',
 'backend\tests\test_bullet_formatting.py',
 'backend\tests\test_bullet_point_fix.py',
 'backend\tests\test_comprehensive_resume_fixes.py',
 'backend\tests\test_experience_header_formats.py',
 'backend\tests\test_final_bullet_fix.py',
 'backend\tests\test_final_fixes.py',
 'backend\tests\test_resume_parser_fix.py',
 'backend\tests\test_skills_formatting_fix.py'
)
Remove-Item $stale
"deleted $($stale.Count) files"
```

- [ ] **Step 2: Remove the two stale tests from test_extractors.py**

Open `backend/utils/resume_parsing/tests/test_extractors.py`. Delete the entire `test_ensure_array_fields` method from `TestAIExtractor` and the entire `test_extract_education_with_ner` method from `TestNLPExtractor`. Leave every other test in the file untouched.

- [ ] **Step 3: Remove the four stale tests from test_extractthinker_pipeline.py**

Open `backend/utils/resume_parsing/tests/test_extractthinker_pipeline.py`. Delete these four methods from `TestExtractThinkerPipeline`, leaving the rest of the class intact:
- `test_intelligent_text_processor`
- `test_structured_extractor`
- `test_contract_validation`
- `test_configuration_loading`

`test_resume_parser_with_real_file` was already removed in Task 7 Step 2b. If it is somehow still present, delete it now.

- [ ] **Step 4: Confirm the removed names are gone**

```powershell
Select-String -Path backend\utils\resume_parsing\tests\test_extractors.py, backend\utils\resume_parsing\tests\test_extractthinker_pipeline.py -Pattern 'test_ensure_array_fields|test_extract_education_with_ner|test_intelligent_text_processor|test_structured_extractor|test_contract_validation|test_configuration_loading'
```

Expected: no output.

- [ ] **Step 5: Run the suite and record the new numbers**

```powershell
$env:PYTHONIOENCODING='utf-8'
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 3
```

Expected: failures down from 41 to roughly 21, errors at 0.

- [ ] **Step 6: Stage, guard, commit**

Paths repeated explicitly — `$stale` from Step 1 does not survive into a
separate command.

```powershell
git add -- backend/tests/test_all_experiences.py backend/tests/test_bullet_formatting.py backend/tests/test_bullet_point_fix.py backend/tests/test_comprehensive_resume_fixes.py backend/tests/test_experience_header_formats.py backend/tests/test_final_bullet_fix.py backend/tests/test_final_fixes.py backend/tests/test_resume_parser_fix.py backend/tests/test_skills_formatting_fix.py backend/utils/resume_parsing/tests/test_extractors.py backend/utils/resume_parsing/tests/test_extractthinker_pipeline.py
```

Run the Task 4 PII guard, then:

```powershell
git commit -m "test: remove tests asserting on removed private APIs

These tests called private methods and constructor kwargs that were
refactored away (RegexExtractor._clean_skill_name,
NebiusAIResumeParser._extract_job_info_from_block, NLPExtractor(llm_service),
and others). Testing private implementation details was the original
mistake; the code is correct and the tests are stale."
```

---

## Task 9: Quarantine Tests That Require Dead or Live Services

**Files:**
- Modify: `backend/tests/test_ai_assistant_comprehensive.py`
- Modify: `backend/tests/test_resume_save.py`
- Modify: `backend/tests/test_resume_save_confirm.py`
- Modify: `backend/utils/resume_parsing/tests/test_improved_extraction.py`
- Modify: `backend/utils/resume_parsing/tests/test_nebius_integration.py`

Spec §2.1 established the Nebius key returns **HTTP 401** and is the current primary provider. These tests cannot pass until the provider chain is rebuilt in Phase 2. They are skipped rather than deleted because they assert on real desired behaviour.

- [ ] **Step 1: Skip the six AI assistant tests**

At the top of `backend/tests/test_ai_assistant_comprehensive.py`, immediately after the existing imports, add:

```python
import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Requires a working LLM provider. The Nebius key returns HTTP 401 as of "
        "2026-08-27 and Nebius is the current primary provider. Re-enable once the "
        "provider chain (Ollama -> OpenRouter -> Claude) lands in Phase 2. "
        "See spec section 4.3."
    )
)
```

- [ ] **Step 2: Skip the two Nebius parsing tests**

At the top of `backend/utils/resume_parsing/tests/test_nebius_integration.py`, after the imports, add:

```python
import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Nebius API key returns HTTP 401 as of 2026-08-27. Nebius is deprioritised "
        "in spec section 4.3 in favour of OpenRouter. Delete this file in Phase 2 "
        "when the provider chain is rebuilt."
    )
)
```

- [ ] **Step 3: Skip the two tests needing a running server and seeded DB**

At the top of both `backend/tests/test_resume_save.py` and `backend/tests/test_resume_save_confirm.py`, after the imports, add:

```python
import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Integration test: requires a running backend and specific seeded database "
        "state (it expects resume id 2 to exist). Needs converting to a fixture-based "
        "test with its own data setup. Tracked for Phase 1."
    )
)
```

- [ ] **Step 4: Skip the two tests needing an absent fixture file**

At the top of `backend/utils/resume_parsing/tests/test_improved_extraction.py`, after the imports, add:

```python
import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Requires Jane_Smith_Resume.pdf at the repo root, which is not committed "
        "(real resumes are excluded by policy - see spec section 6). Rewrite against "
        "a synthetic fixture in Phase 1."
    )
)
```

- [ ] **Step 5: Run the suite**

```powershell
$env:PYTHONIOENCODING='utf-8'
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 3
```

Expected: failures down to roughly **8**, errors 0, skips increased by about 11.

- [ ] **Step 6: Stage, guard, commit**

```powershell
git add -- backend/tests/test_ai_assistant_comprehensive.py backend/tests/test_resume_save.py backend/tests/test_resume_save_confirm.py backend/utils/resume_parsing/tests/test_improved_extraction.py backend/utils/resume_parsing/tests/test_nebius_integration.py
```

Run the Task 4 PII guard, then:

```powershell
git commit -m "test: skip tests blocked on dead provider or absent fixtures

Each skip carries an explicit reason and the phase that will unblock it.
The Nebius key returns 401 and is the current primary provider."
```

---

## Task 10: Commit the Remaining Test Suite

**Files:** every remaining test file, now un-ignored by Task 3.

The roughly 8 still-failing tests stay visible and failing. They assert real defects — including `Expected 'Full Stack Developer', got 'Full Stack "eveloper'`, a genuine character-corruption bug in parsing. Hiding them would defeat the purpose of un-ignoring the suite.

- [ ] **Step 1: See what will be added**

```powershell
cd C:\Users\seaso\RecruitIQ
git add --dry-run -- backend/tests backend/utils/resume_parsing/tests frontend/tests tests conftest.py | Measure-Object -Line
```

Expected: a count in the low hundreds.

- [ ] **Step 2: Stage the tests**

```powershell
git add -- backend/tests backend/utils/resume_parsing/tests frontend/tests tests conftest.py
```

- [ ] **Step 3: Run the PII guard from Task 4 — mandatory here**

This is the largest staging operation in the plan. Expected: both `OK` lines.

Note `backend/utils/resume_parsing/tests/fixtures/sample_resume.pdf` is **0 bytes** and matches the resume ignore patterns, so it should not appear. If it does, unstage it.

- [ ] **Step 4: Commit**

```powershell
git commit -m "test: track the test suite for the first time

138 test files existed on disk but were gitignored, so only 1 was tracked.
After removing invalid and stale tests, the remaining suite is committed.
Roughly 8 tests still fail against real defects and are deliberately left
visible - see documentation/TESTING.md."
```

- [ ] **Step 5: Record the final baseline**

```powershell
$env:PYTHONIOENCODING='utf-8'
poetry run pytest -q --no-header -p no:cacheprovider --tb=no 2>&1 | Select-Object -Last 2
```

Write the resulting counts down; Task 12 quotes them in the README.

---

## Task 11: Add .env.example and LICENSE

**Files:**
- Create: `.env.example`
- Create: `LICENSE`

`README.md:247` links to `[MIT License](LICENSE)` but no `LICENSE` file exists — a broken claim on a public repo.

- [ ] **Step 1: Create .env.example**

Create `.env.example` with this content. Values are placeholders; no real secret may appear.

```bash
# RecruitIQ environment configuration.
# Copy to .env and fill in. Never commit .env.
#
# Only POSTGRES_* is strictly required to boot the backend. Neo4j, MinIO and
# Redis are optional - the app degrades gracefully without them.

# ==== Core ====
ENVIRONMENT=development
API_URL=http://localhost:8000
BASE_URL=http://localhost:8000
API_VERSION=v1
ENABLE_SWAGGER=true
LOG_LEVEL=INFO
LOG_FILE=logs/recruitiq.log

# ==== PostgreSQL (required) ====
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ats_db
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_CONN=postgresql://your_db_user:your_db_password@localhost:5432/ats_db

# ==== Neo4j (optional; being removed in Phase 1) ====
DISABLE_NEO4J=false
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
NEO4J_DATABASE=neo4j
NEO4J_PORT=7687
NEO4J_MAX_CONNECTION_LIFETIME=300
NEO4J_MAX_CONNECTION_POOL_SIZE=10
NEO4J_CONNECTION_TIMEOUT=5
NEO4J_ASYNC_MODE=true
NEO4J_EVENT_LOOP_MODE=auto

# ==== Redis (optional) ====
REDIS_URL=redis://localhost:6379
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_MAX_CONNECTIONS=10
REDIS_SOCKET_TIMEOUT=5
REDIS_RETRY_ON_TIMEOUT=true
REDIS_DECODE_RESPONSES=true

# ==== MinIO (optional; falls back to local disk) ====
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=resumes
MINIO_USE_SSL=false

# ==== LLM providers ====
# OpenRouter is the primary cloud fallback.
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=meta-llama/llama-3.3-8b-instruct:free
OPENROUTER_DEFAULT_MODEL=meta-llama/llama-3.3-8b-instruct:free
OPENROUTER_ENABLED=true
OPENROUTER_TIMEOUT=60

# Groq - used for reranking.
GROQ_API_KEY=gsk_your-key-here
GROQ_API_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_ENABLED=true
GROQ_TIMEOUT=30

# Nebius - DEPRECATED. Key returned HTTP 401 as of 2026-08-27.
NEBIUS_API_KEY=

# Optional / currently disabled providers.
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
COHERE_API_KEY=
GOOGLE_API_KEY=
GOOGLE_GEMINI_API_KEY=
GOOGLE_CSE_ID=
GEMINI_ENABLED=false
META_LLAMA_API_KEY=
META_LLAMA_MODEL=
META_LLAMA_ENABLED=false
META_LLAMA_TIMEOUT=30
OPENROUTESERVICE_API_KEY=

# ==== Portkey gateway (optional) ====
PORTKEY_ENABLED=false
PORTKEY_GATEWAY_URL=
PORTKEY_CACHE_STRATEGY=simple
PORTKEY_CACHE_TTL=3600
PORTKEY_RETRY_ATTEMPTS=3
PORTKEY_TIMEOUT=30

# ==== Models and embeddings ====
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
VECTOR_MODEL=sentence-transformers/all-MiniLM-L6-v2
VECTOR_DIMENSION=384
SPACY_MODEL=en_core_web_lg
LLM_MODEL_PATH=
FALLBACK_MODEL=
DOCUMENT_GENERATION_MODEL=
PARAMETER_EXTRACTION_MODEL=
SECTION_DETECTION_MODEL=
SEARCH_INDEX_PATH=
MAX_TOKENS=4096

# ==== Resume parsing ====
PARSER_TIMEOUT=120
PARSER_MAX_RETRIES=3
PARSER_BATCH_SIZE=10
PARSER_CACHE_ENABLED=true
PARSER_MIN_CONFIDENCE=0.5
PARSER_FALLBACK_CHAIN=llm,regex
CONFIDENCE_THRESHOLD=0.7
NER_CONFIDENCE_THRESHOLD=0.7
OCR_LANGUAGE=en
ENABLE_GPU=false
ENABLE_ADVANCED_NER=true
ENABLE_CONTACT_EXTRACTION=true
ENABLE_FUZZY_MATCHING=true
ENABLE_LAYOUT_ANALYSIS=true
ENABLE_SECTION_DETECTION=true

# ==== Graph RAG ====
GRAPH_RAG_ENABLED=true
GRAPH_CONTEXT_DEPTH=2
```

- [ ] **Step 2: Verify .env.example is not ignored and contains no real secrets**

```powershell
cd C:\Users\seaso\RecruitIQ
git check-ignore -q -- .env.example
if ($LASTEXITCODE -ne 0) { "OK - .env.example is trackable" } else { "STILL IGNORED - fix the !.env.example rule" }
Select-String -Path .env.example -Pattern 'eyJ|sk-or-v1-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|cadjhosea'
"(no output above = no real secrets)"
```

Expected: `OK - .env.example is trackable`, and no secret matches.

- [ ] **Step 3: Create LICENSE**

Create `LICENSE` with the MIT text:

```
MIT License

Copyright (c) 2024-2026 Sean Collins

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Stage, guard, commit**

```powershell
git add .env.example LICENSE
```

Run the Task 4 PII guard, then:

```powershell
git commit -m "docs: add .env.example and the MIT LICENSE file

README claimed MIT and linked to a LICENSE file that did not exist.
.env.example documents all 96 environment variables with placeholders."
```

---

## Task 12: Rewrite the README Around the Lineage

**Files:**
- Rewrite: `README.md`
- Create: `documentation/TESTING.md`

The current README is a sales deck — subscription tiers, service phases, pricing model. That is the artifact of the internal pitch that did not land (spec §1). The audience is a TA leader skimming for ninety seconds, and an engineer checking whether it is real.

Two factual errors must not survive: it claims **Python 3.9+** (`pyproject.toml` requires `^3.11`) and links to a LICENSE that did not exist until Task 11.

- [ ] **Step 1: Write documentation/TESTING.md**

```markdown
# Testing

```bash
poetry run pytest
```

## Current state

This suite was gitignored until 2026-08-27 — 138 test files existed on disk
and one was tracked. Un-ignoring them exposed real rot, which was triaged
rather than hidden:

- **Deleted:** six files defining `test_*` functions that took plain arguments
  (`pdf_path`, `text`, `resume_path`). pytest treated them as fixture requests
  and they errored at collection. They were written to be run by hand.
- **Deleted:** nine files plus six individual tests asserting on private
  methods and constructor kwargs that no longer exist
  (`RegexExtractor._clean_skill_name`, `NLPExtractor(llm_service=...)`).
  Testing private implementation details was the original mistake.
- **Skipped, with reasons:** tests needing the Nebius API (key returns HTTP 401
  and the provider is being replaced), a running server with seeded data, or a
  real resume fixture that policy forbids committing.

## Tests that still fail

A handful fail against genuine defects and are deliberately left visible.
The clearest is a character-corruption bug in experience parsing:

```
AssertionError: Expected 'Full Stack Developer', got 'Full Stack "eveloper'
```

These are the eval harness's first targets.
```

- [ ] **Step 2: Write the new README.md**

Replace the entire contents of `README.md` with the following. Substitute the real pass/fail counts recorded in Task 10 Step 5 wherever the text says `<PASSED>` / `<FAILED>` / `<SKIPPED>`.

```markdown
# RecruitIQ

**Your ATS is a graveyard of qualified candidates you already paid to source.**

Every agency and in-house team I have worked on sits on thousands of resumes
that were good enough to interview and never got called again. The candidate
was real, the skills were real, the money to source them was already spent.
Then the req closed and they vanished into a search index that only matches on
keywords.

RecruitIQ is my attempt to fix that: parse what is already in the pile,
represent it properly, and match against live roles semantically instead of by
string.

I am a recruiter, not a software engineer by training. I have been building
toward this problem for two years.

---

## The lineage

This repository is the eleventh iteration. The arc matters more than any single
repo:

| # | Repo | What it added |
|---|---|---|
| 1 | `py_to_mysql_resparser` (Mar 2024) | Regex parsing into MySQL |
| 2 | `RezParser` | Structured extraction |
| 3 | `Resume-Cupidv1` | First matching attempt |
| 4 | `Resume-Cupid-RAG-Test` | Retrieval-augmented matching |
| 5 | `Resume_Cupid_CrewAI_HF_Llama3` | Multi-agent orchestration |
| 6 | `Resume-Cupid_Multi-Option-LLM` | Provider abstraction |
| 7 | `Resume-Cupid-Full-Stack` | End-to-end application |
| 8 | `Resumatch-AI` | Matching as the product |
| 9 | `Recruiter-Dashboard` | Recruiter-facing workflow |
| 10 | `Recruiting-Dashboard` | Pipeline management |
| 11 | **RecruitIQ** | Graph + vector matching, agent framework |

MySQL regex parser to CrewAI to RAG to a graph-backed platform. Each one taught
me what the previous one got wrong.

---

## What is actually here

A FastAPI backend (95 routes) and a Streamlit frontend, backed by PostgreSQL.

**The resume parsing pipeline** is the part I am most confident in. LLM
structured extraction against a Pydantic contract, falling back to a regex
extractor, with a dedicated extractor for military service — because veteran
resumes describe experience in a format civilian parsers reliably mangle.

**Candidate-job matching** scores role fit, skill overlap and experience
independently, then applies cross-domain penalties. A pre-K teacher does not
rank for a Data Engineer role just because both mention "leadership".

---

## Honest status

This is a portfolio piece under active renovation, not a product. Being
specific about what is broken is more useful to you than a feature list:

- **Neo4j is being removed.** It holds 48 nodes and its vector indexes are
  misconfigured — 384-dimension indexes against 1536-dimension stored vectors.
  It is the single biggest barrier to anyone running this project, and it is
  being folded into Postgres with `pgvector`.
- **The Nebius API key is dead (HTTP 401)** and it is still the primary
  provider, so AI-dependent paths fail until the provider chain is rebuilt.
- **`intent_processor.py` is 4,338 lines of hand-written regex** across 30+
  intents. It is being replaced with ~8 tool definitions.
- **The test suite:** `<PASSED>` passing, `<FAILED>` failing, `<SKIPPED>`
  skipped. The failures are real defects, left visible on purpose. See
  [documentation/TESTING.md](documentation/TESTING.md).

Full assessment and plan:
[docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md](docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md).

---

## Running it

Requires **Python 3.11+**, Poetry and PostgreSQL. Neo4j, Redis and MinIO are
optional — the app degrades gracefully without them.

```bash
poetry install
cp .env.example .env        # fill in POSTGRES_* at minimum
```

```bash
# Terminal 1 - backend on :8000
poetry run python -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend

# Terminal 2 - frontend on :8501
poetry run streamlit run frontend/app.py
```

API docs at `http://localhost:8000/docs`.

The first request takes around 30 seconds while spaCy and the OCR models load.
Subsequent requests are around 300 ms.

---

## Data

All candidate data in this repository is **synthetic**. Real resumes are
excluded by `.gitignore` and are never committed.

## License

[MIT](LICENSE)
```

- [ ] **Step 3: Verify the claims in the README are true**

```powershell
cd C:\Users\seaso\RecruitIQ
Select-String -Path pyproject.toml -Pattern '^python\s*='
(Get-Content backend\services\intent_processor.py | Measure-Object -Line).Lines
if (Test-Path LICENSE) { "LICENSE exists" } else { "LICENSE MISSING" }
```

Expected: `python = "^3.11"` (matching the README's 3.11+ claim), a line count near 4,338, and `LICENSE exists`.

- [ ] **Step 4: Stage, guard, commit**

```powershell
git add README.md documentation/TESTING.md
```

Run the Task 4 PII guard, then:

```powershell
git commit -m "docs: rewrite README around the lineage narrative

Replaces subscription tiers, service phases and pricing with the actual
story and an honest status section. Corrects two false claims: Python 3.9+
(pyproject requires ^3.11) and a LICENSE link that pointed at nothing."
```

---

## Task 13: Archive the Stale Public Repos

**Files:** none — GitHub API only.

Spec §8. `Resume-Cupid_Multi-Option-LLM`'s README still contains an unedited
`git clone https://github.com/your-username/resume-cupid.git` placeholder and
the line "not yet ready for public use".

> **Confirm with the repo owner before running this step.** Archiving is
> outward-facing and makes the repos read-only. It is reversible via the GitHub
> UI, but it changes how they appear publicly.

- [ ] **Step 1: Confirm current state**

```powershell
foreach ($r in @('devDabbler/Resumatch-AI','devDabbler/Resume-Cupid_Multi-Option-LLM')) {
  gh repo view $r --json name,isArchived,visibility,updatedAt
}
```

Expected: both `"isArchived": false`, `"visibility": "PUBLIC"`.

- [ ] **Step 2: Archive them**

```powershell
gh repo archive devDabbler/Resumatch-AI --yes
gh repo archive devDabbler/Resume-Cupid_Multi-Option-LLM --yes
```

- [ ] **Step 3: Verify**

```powershell
foreach ($r in @('devDabbler/Resumatch-AI','devDabbler/Resume-Cupid_Multi-Option-LLM')) {
  gh repo view $r --json name,isArchived
}
```

Expected: both `"isArchived": true`.

---

## Task 14: Final Verification and Push

**Files:** none

- [ ] **Step 1: Confirm the working tree is clean**

```powershell
cd C:\Users\seaso\RecruitIQ
git status --short
```

Expected: empty, or only files that are intentionally untracked-and-ignored.

- [ ] **Step 2: Confirm no secret or PII file is tracked anywhere**

```powershell
$tracked = git ls-files
$bad = $tracked | Where-Object { $_ -match '(?i)\.env$|resume.*\.(pdf|docx?)$|\.safetensors$|\.bin$|^storage/|^data/resumes/' }
if ($bad) { "*** TRACKED SENSITIVE FILES ***"; $bad } else { "OK - nothing sensitive tracked" }
```

Expected: `OK - nothing sensitive tracked`

- [ ] **Step 3: Confirm the repo is small**

```powershell
"{0:N1} MB .git" -f ((Get-ChildItem .git -Recurse -Force | Measure-Object Length -Sum).Sum/1MB)
"tracked files: $((git ls-files | Measure-Object).Count)"
```

Expected: `.git` between 1 and 5 MB. Tracked files up well above 303, because ~130 tests and 19 documentation files are now included.

- [ ] **Step 4: Confirm the app still runs — Phase 0 changed no behaviour**

```powershell
cd C:\Users\seaso\RecruitIQ\backend
$env:PYTHONIOENCODING='utf-8'
poetry run python -c "import main; print('IMPORT OK'); print('routes:', len(main.app.routes))"
cd C:\Users\seaso\RecruitIQ
```

Expected: `IMPORT OK` and `routes: 95` — identical to the Task 6 baseline.

- [ ] **Step 5: Push**

```powershell
git push origin main
```

- [ ] **Step 6: Verify what a visitor sees**

```powershell
gh repo view devDabbler/RecruitIQ --json name,description,diskUsage,defaultBranchRef
gh api repos/devDabbler/RecruitIQ/contents/documentation --jq '.[].name' | Select-Object -First 5
```

Expected: `diskUsage` dramatically lower than before, and documentation files listed — proving markdown is visible on GitHub for the first time.

- [ ] **Step 7: Clean up the safety net**

```powershell
git tag -d phase0-start
Remove-Item C:\Users\seaso\reset_pg_admin.ps1 -ErrorAction SilentlyContinue
Remove-Item C:\Users\seaso\RecruitIQ\test_triage.log -ErrorAction SilentlyContinue
Remove-Item C:\Users\seaso\RecruitIQ\backend_baseline.log -ErrorAction SilentlyContinue
"cleaned"
```

Keep `C:\Users\seaso\recruitiq-deleted-branch-sha.txt` until Phase 1 completes.

---

## Deliberately Not in Phase 0

Spec §8 lists these under Publishing, but §10 assigns them to Phase 1. Recording
them here so they read as deferred rather than forgotten:

| Item | Why deferred |
|---|---|
| `docker-compose.yml` | §10 puts it in Phase 1. Also blocked: **Docker is not installed on this machine** (spec §2.1), so it is a prerequisite to install, not merely to author. And composing around Neo4j now would be wasted work, since Phase 1 removes it. |
| GitHub Actions (pytest + ruff) | §10 puts CI in Phase 1. Adding CI before the ~8 genuine test failures are addressed would ship a permanently red badge — worse than no badge. |
| `docs/decisions/` ADRs | §4 narrative work. Phase 4 in §10. |
| Fixing the ~8 genuine test failures | Real debugging, including the `Full Stack "eveloper` character-corruption bug. Phase 1, informed by the eval harness in §7. |

## Deviation From the Spec, Approved 2026-08-27

Spec §8 says **"Fresh git history — the 86.7 MB blob cannot be surgically
removed from a repo others may have cloned."** That premise was tested and does
not hold:

- The blob is reachable **only** from `origin/update-recruiq-project`, not from
  `origin/main`. `main` was already reset to clean history on 2025-08-27.
- The repo has **0 forks and 0 stars**. Nobody has cloned it.

Deleting one branch therefore removes the entire problem. The repo is kept,
which preserves the URL, main's history, and the **2025-04-26 creation date** —
meaningful because the README argues two years of sustained work, and a repo
created today would quietly undercut that claim.

## Done When

- `git clone` of the repo pulls under 5 MB instead of 90 MB.
- The 19 files in `documentation/` are visible on GitHub.
- The test suite is tracked, collects with zero errors, and every skip states why.
- `README.md` leads with the ATS-graveyard thesis and the eleven-repo lineage.
- `.env.example` and `LICENSE` exist; `LICENSE` is no longer a broken link.
- `Resumatch-AI` and `Resume-Cupid_Multi-Option-LLM` are archived.
- `import main` still yields 95 routes — no behaviour changed.
