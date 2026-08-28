# Phase 3 — Next.js Frontend

Status: approved 2026-08-27
Supersedes: the three-line Phase 3 stub in
`docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md` (§ Phase 3)

Replaces the 14,761-line Streamlit app (47 files, 97 `unsafe_allow_html=True`
calls, hardcoded `testuser`/`password` login, no central API client) with a
Next.js App Router application in TypeScript, styled with Tailwind and
shadcn/ui.

The revival spec fixed the stack and the screen list but left three decisions
open: how the app is served in production, how the frontend talks to the API,
and what the assistant chat does about tool-calling latency. This document
settles all three and the design that follows from them.

## Goals

A TA leader following a link from Sean's resume lands in a working product with
real seeded data, no signup wall, and no dead tabs. Every screen shows live
data from the existing FastAPI backend.

Non-goals: multi-tenancy, user registration, refresh-token rotation, mobile
layouts beyond what Tailwind gives for free, and any screen outside the eight.

## 1. Serving and topology

Next.js builds with `output: 'standalone'` and runs as a systemd unit. nginx
terminates TLS and routes:

```
nginx :443
  ├── /docs, /openapi.json  →  uvicorn 127.0.0.1:8010
  └── /*                    →  node   127.0.0.1:3000
                                  └── route handlers proxy → uvicorn 127.0.0.1:8010

systemd: recruitiq-web.service   MemoryMax=512M
```

FastAPI binds loopback only. The browser talks exclusively to Next — a
backend-for-frontend (BFF) arrangement that buys three things:

- No CORS configuration anywhere.
- The JWT lives in an httpOnly cookie that page JavaScript cannot read.
- Mutating API routes are not publicly addressable.

`/docs` is deliberately left public. A documented API surface is an asset in a
portfolio piece, and Swagger UI against read-only-enforced routes is safe.

Chosen over static export (`output: 'export'`), which would have cost Server
Components, route handlers, and middleware, and forced the JWT into
JS-readable storage. The Node process costs roughly 150 MB against the
droplet's ~3.6 GB free, and the systemd-unit-with-`MemoryMax` pattern is
already what Phase 4 commits to for every other service.

**Phase 4 prerequisite:** the droplet has no Node runtime installed. Node 20+
becomes a new deploy-phase dependency.

## 2. Authentication

Fills `backend/routers/auth.py`, currently a 0-byte file. No user model, JWT
handling, or route protection exists anywhere in the backend today.

**Model.** `User`: `id` (UUID pk), `email` (unique), `hashed_password`
(passlib/bcrypt), `role` (`admin` | `demo`), `created_at`.

**Routes.** `POST /auth/login` (credentials → token), `POST /auth/demo`
(no credentials → demo token), `GET /auth/me`.

**Token.** HS256, 24-hour expiry, secret from `Settings`. No refresh-token
rotation — a deliberate scope cut for a demo application.

**Auto-sign-in.** Next middleware: a request with no session cookie triggers a
server-side call to `/auth/demo`, sets the resulting token as an httpOnly,
Secure, SameSite=Lax cookie, and continues. The visitor never sees a login
screen.

**Read-only enforcement lives in the backend.** A FastAPI dependency returns
403 for any mutating method when `role == demo`. The UI also hides mutating
controls, but that is cosmetic — a hidden button is not an access control, and
anyone can POST directly to the API. The dependency is the gate; the UI is
courtesy.

## 3. API client

The backend exposes ~82 decorated routes across 15 router modules. Only about
25 are reachable from the eight screens.

1. **Backfill `response_model`** on those ~25 routes. Roughly half the backend
   currently declares one (40 of 82), so generating types today would emit
   `unknown` for much of the surface we actually use.
2. **Generate types.** Emit `openapi.json` from the app; run
   `openapi-typescript` → `web/src/lib/api.d.ts`. Types only, no runtime.
3. **Hand-write `apiFetch<T>()`** for base URL, cookie forwarding, and error
   normalization.

`openapi.json` is committed, and CI asserts that regenerating it produces no
diff. Backend/frontend drift then fails the build rather than a screen.

**Risk — response filtering.** Adding `response_model` to a live route is not
inert: FastAPI *filters* the response down to the declared model, so any field
a handler returns that the model omits disappears silently, and the symptom
looks like a frontend bug. Mitigation is a golden-response test per route,
captured before the backfill and asserted unchanged after. This is the first
task of the implementation plan, not a later hardening step.

## 4. Data fetching

Server Components load initial page data, calling FastAPI server-side with the
cookie's token — no loading spinner on navigation. TanStack Query handles
client-side interactivity: candidate search-as-you-type, re-running a match,
and mutations.

## 5. Assistant chat

The current contract is synchronous: `{message, conversation_history,
conversation_context}` → `{response, conversation_context}`, with
`run_tool_loop` executing to completion server-side.

A single chat turn is typically three model calls plus tool execution against
the database. Only the final call produces prose, so token-level streaming
would cover roughly the last fifth of the wait and leave the rest as dead air.
Streaming the *tool activity* covers all of it, and for this audience it is
the better artifact: watching `searching candidates → found 12 → scoring`
demonstrates that the assistant queries real ATS data rather than inventing it.

**Design.** A new `POST /api/assistant/chat/stream` returns SSE. `run_tool_loop`
gains an optional event sink — it already knows the tool boundaries and simply
discards them today. Existing `/chat` is untouched, so Phase 2's contract and
its tests survive intact. Event types: `tool_start`, `tool_end`, `message`,
`error`. The final answer arrives whole in a `message` event.

The Next route handler pipes the stream through unbuffered. nginx needs
`proxy_buffering off` on that location, or SSE arrives in a single lump and the
feature is invisible.

## 6. Screens

Exactly eight, per the revival spec's rule that nothing ships stubbed:

Dashboard · Candidates · Candidate Detail · Jobs · Job Detail · Resume Upload ·
Matching · AI Assistant

Interviews (8 routes) and Tasks (8 routes) keep their API endpoints and remain
visible in `/docs`, but get no UI. A tight, finished eight reads better than
ten where two feel thin.

## 7. Seed data

`scripts/seed_demo.py`, idempotent: ~40 candidates with resumes and 768-dim
embeddings, ~8 jobs, match scores, and pipeline states.

Authored during Phase 3 rather than Phase 4, because a Dashboard or Matching
screen cannot be built or verified against an empty database. Phase 4 loads the
same dataset on the droplet, so the public demo shows exactly what was
developed against.

## 8. Testing

| Layer | Covers |
|---|---|
| pytest | login, demo issuance, expiry, invalid token; 403 on every mutating route as `demo`; golden response tests for the `response_model` backfill |
| Vitest | `apiFetch`, auth helpers |
| Playwright | one journey through all eight screens as the demo user, asserting no dead tabs |

## 9. Streamlit removal

The Streamlit app is frozen, not modified. It stays through the phase as a
working reference and fallback, then is removed in a single final commit once
the Next.js app reaches parity.

## 10. Risks

| Risk | Mitigation |
|---|---|
| `response_model` backfill silently truncates responses | Golden tests before/after, as task 1 |
| SSE buffered by nginx or the Next proxy | `proxy_buffering off`; assert streaming in an integration test |
| Node process memory on a shared droplet | `output: 'standalone'`, systemd `MemoryMax=512M` |
| Droplet has no Node runtime | Flagged as a Phase 4 prerequisite |
| Demo data mutated by visitors | Backend read-only dependency, enforced and tested per route |

## Repository layout

The Next.js application lives in `web/` at the repository root, alongside
`backend/` and (until removal) `frontend/`.
