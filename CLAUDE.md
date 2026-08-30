# RecruitIQ

Recruiting intelligence platform: FastAPI + Postgres/pgvector backend
(`backend/`), Next.js frontend (`web/`), LLM provider chain (Ollama tunnel →
OpenRouter). Live at https://recruitiq.io (the former resumecupid.ai
redirects; see ADR 0005). Design spec:
`docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md`.
Decisions live in `docs/decisions/` (ADRs 0001-0003); read them before
changing provider routing or deployment shape.

## Environments

- **Dev (this machine):** Postgres in docker on **5433** (5432 belongs to
  another project), Redis on 6380. `.env` at repo root holds dev config.
  Backend: `cd backend && poetry run python -m uvicorn main:app --port 8010`.
  Web: `cd web && npm run dev`.
- **Prod:** DigitalOcean droplet `157.245.233.229` (SSH as root), shared with
  the live SentientTrader trading system. RecruitIQ runs as the `recruitiq`
  user from `/opt/recruitiq/app` under two systemd units (`recruitiq-api` on
  127.0.0.1:8020, `recruitiq-web` on 127.0.0.1:3001) behind nginx. Secrets:
  `/etc/recruitiq/env` (never in git). Postgres is native on the droplet;
  Docker is dev-only (ADR 0003).

## Workflow

1. **Branch off `main`** (`phase-N-topic` or a short feature name). Never
   commit directly to `main` except trivial docs.
2. **Test before pushing.** Backend, the way CI does it (fresh-DB semantics):
   ```powershell
   $env:POSTGRES_CONN = "<dev conn from .env>"
   $env:OLLAMA_BASE_URL = "http://localhost:1"   # unreachable on purpose
   poetry run pytest -q
   ```
   Web: `cd web; npm run typecheck; npm test` (typecheck runs `next typegen`
   first — a bare tsc fails on every route).
3. **Commit style:** imperative subject (`fix:`/`feat:`/`docs:`), body explains
   *why* and what was verified, not a file list.
4. **Push the branch, open a PR** against `main` with `gh pr create`. Wait for
   CI (backend test job, web job, GitGuardian). Never merge red.
5. **Merge with a merge commit** (`gh pr merge N --merge`), then update local
   `main`.

## Database rule (learned the hard way)

Any table or column the code touches must exist in the Alembic tree
(`backend/alembic/`). The dev database contains legacy tables that migrations
never created; code that "works locally" can 500 on any fresh install. When
touching schema, verify against a scratch database: create one, run
`alembic upgrade head` against it, run the suite pointed at it.

Seed data (`scripts/seed_demo.py`) must stay **self-sufficient and fully
synthetic** — a fresh DB plus this script is the whole demo dataset. No real
resumes, ever (spec §6).

## Deploying to the droplet

The droplet checkout tracks `main`. After a PR merges:

```powershell
ssh root@157.245.233.229 "/opt/recruitiq/app/scripts/deploy.sh"
```

That script is the entire story: git pull, poetry/npm deps, memory-fenced
`next build`, `alembic upgrade head`, unit restarts, health checks. If it
fails it prints the failing unit's journal.

Rules of engagement on the droplet (it hosts a latency-sensitive trading
system):

- Never touch SentientTrader's services, its nginx sites, or Redis db 0
  (RecruitIQ uses db 3). Ports 8000/8001 are theirs.
- Check `free -h` before anything heavy; RecruitIQ's units are memory-capped
  on purpose — do not raise `MemoryMax` without reading ADR 0003.
- certbot owns the nginx site file after first issue; `deploy.sh` deliberately
  does not overwrite it.
- One-off admin: `scripts/create_admin.py` (reads `ADMIN_PASSWORD` env);
  reseed: run `scripts/seed_demo.py` as `recruitiq` with `/etc/recruitiq/env`
  sourced.

## Known sharp edges

- ~35 backend endpoints are `async def` doing sync ORM on the event loop.
  Mitigated (pool sizing, 2 workers, timeouts — ADR 0003 amendment) but the
  refactor is open Phase 5 work. Don't add new `async def` endpoints that use
  `Depends(get_db)`; make them plain `def`.
- `/matching` computes scores live (~8s); the page streams a skeleton first.
- Alembic reads `POSTGRES_CONN` from the environment, not `.env`.
- No em dashes in user-visible copy.
