# Fractal pilot hardening + Slate gap plan

Date: 2026-10-05
Status: in progress. Track 1 #1 (internal-mode) shipped 2026-10-05.
Sources: `.claude/audits/2026-10-05-slate-source-review.md` (gap list),
hosting request doc (Claude Docs, "RecruitIQ internal pilot hosting request"),
`2026-10-03-recruitiq-ats-workflow-design.md` (ATS blueprint).

Context: Sean is submitting a formal request to host RecruitIQ inside
Fractal (pilot: one team, 90 days, Workday stays system of record). The
hosting request promises six "Before pilot" controls. Separately, the Slate
source review found 17 unplanned product gaps worth adopting. This plan
orders both.

## Track 1 - Pilot blockers (gate for real candidate data)

These are the six controls the hosting request marks "Before pilot", plus
one bug. Nothing else unblocks approval, so they come first. Each is one PR
on the normal /st loop; all deployable to the public demo without changing
its behavior (every control is flag-gated or additive).

| # | PR | What | Size |
|---|---|---|---|
| 1 | internal-mode | `DEPLOYMENT_MODE=internal` env flag: disables `/auth/demo`, the demo role, and public pages (transparency stays, it is the selling point; decide per page). Default `public` keeps recruitiq.io exactly as-is. Include the /docs title mojibake fix ("Â·"). | S |
| 2 | erasure | Complete candidate deletion: rewrite `delete_candidate` to remove every related row (applications, stages, interviews, feedback, notes, tags, emails, embeddings, resume files in MinIO) in one transaction, verified by a test that counts leftovers across all FK tables. This is GDPR right-to-erasure and also just correctness. | S-M |
| 3 | audit-log | `audit_events` table + service: who viewed/created/changed/exported/deleted candidate data, when, from which endpoint. Append-only, admin-readable UI page later (table + API first). Learn from Slate's mistake: store field names changed, never full row copies; admin-only read. | M |
| 4 | sso-oidc | OIDC sign-in (works with Entra ID/Google/Okta): new auth path beside the existing password login, mapped to the four staff roles via a configurable claim. Password login stays for dev/demo. | M |
| 5 | data-export | `GET /api/candidates/{id}/export`: everything held about one person as JSON + readable text, admin-only, audit-logged. Small once 3 exists. | S |
| 6 | retention | `RETENTION_DAYS` setting + a daily job (systemd timer calling a script) that anonymizes or deletes candidates with no activity past the window; dry-run flag; logged. | S |

Order within track: 1 → 2 → 3 → 5 → 6 → 4 (SSO last: it is the only one
needing Fractal-side configuration to test fully; everything else is
self-contained).

## Track 2 - Product gaps from the Slate review

Ordered by demo value and by what makes the Fractal pitch stronger.
Phased execution plan: `2026-10-05-track-2-product-gaps.md` (one /st session per phase).
Numbers reference the gap table in the audit.

**Wave 1 (the headline features):**
1. **Structured requirements + score caps** (gap 1): must-have/nice-to-have
   skills, experience range, min education on jobs; score_pair caps when
   must-haves are missing, surfaced in the transparency trace. This is
   Slate's best idea and credits Prasnajeet's design. M
2. **Rank a job's applicants** (gap 2): score column on the pipeline
   board/candidate table scoped to the job, bulk upload ends sorted by fit.
   Depends on 1 to be trustworthy. M

**Wave 2 (team workflow):**
3. **AI feedback summary** (gap 3): committee brief once 2+ feedback
   submissions exist, through build_chain, de-identified, never fed scores. M
4. **@mentions + pending-feedback badge** (gaps 4, 8): mention typeahead in
   notes, email via existing SMTP, sidebar badge. M
5. **No-movement email digest** (gap 5): daily email using the existing
   stale rule; shares the timer infrastructure with retention (Track 1 #6). S

**Wave 3 (quick wins, 1-2 PRs batched):**
6. Tag filter + bulk tag (9), requisition number (11), department picklist
   (12), withdraw action (13), source picker (15), median time to
   hire/reject (16), feedback templates + drafts (6, 7). All S.

**Deferred (decide later):** JD upload (10), in-app workflow guide (17),
audit-trail UI page, notice-period/comp capture at HR screen, start-date
after offer accepted.

## Track 3 - Not code

- Send the security note to Prasnajeet (`.claude/audits/2026-10-05-note-to-slate-author.md`) - Sean's call, urgent because the app is public.
- Fill the bracketed placeholders in the hosting request doc and submit.
- Co-sponsor conversation with Prasnajeet (Bench module as his area in a unified app).

## Sequencing recommendation

Track 1 first and fully (it gates the pilot and is ~2 weeks as promised in
the request), with Track 2 Wave 1 interleaved only if Track 1 stalls on
external dependencies (SSO config). Then Wave 1 → Wave 2 → Wave 3. Every PR
through the normal /st loop: scratch-DB verified, CI green, deployed to the
droplet (internal-mode features behind flags so the public demo is
unchanged).
