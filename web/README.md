# RecruitIQ web

The Next.js front end. Replaces the Streamlit app; see
`docs/superpowers/specs/2026-08-27-recruitiq-phase-3-frontend-design.md` for the
design it implements.

## Topology

```
browser  →  Next (:3000)  →  uvicorn (:8010, loopback only)
```

The browser never talks to FastAPI. Next holds the API base URL and the session
cookie and calls the backend server-side, which is why there is no CORS config
anywhere and no `NEXT_PUBLIC_API_URL`: publishing the backend origin to the
client bundle would invite direct calls that bypass the session.

Visitors are signed in automatically. `src/proxy.ts` (Next 16 renamed
`middleware` to `proxy`) mints a demo token from `POST /auth/demo` on any
request without a cookie, so a link from a résumé lands in a working product
rather than a login form. The demo user is read-only; the backend enforces
that, and `canWrite()` in `src/lib/session.ts` mirrors it so write controls are
disabled rather than failing on click.

## Running it

The backend must be up first — the screens render real rows, not fixtures:

```bash
poetry run uvicorn backend.main:app --port 8010     # repo root
npm install
npm run dev                                          # http://localhost:3000
```

Environment (all optional, all server-side):

| Variable        | Default                 | Purpose                        |
| --------------- | ----------------------- | ------------------------------ |
| `API_BASE_URL`  | `http://127.0.0.1:8010` | Where FastAPI is listening     |
| `PORT`          | `3000`                  | Read by the standalone server  |

## Types come from the backend

`src/lib/schema.d.ts` is generated, never hand-edited:

```bash
npm run types:api      # reads ../openapi.json
```

`openapi.json` is committed and CI fails when it drifts from the routes, so a
screen that reads a field the API no longer returns fails at `npm run build`
instead of rendering blank.

## Tests

```bash
npm run typecheck
npm run lint
npm test               # Vitest: apiFetch, the SSE reader, session helpers
npm run e2e            # Playwright: one journey through all eight screens
```

The Playwright run is not in CI — it needs a seeded database and real model
credentials, so it would fail there for reasons unrelated to the diff. It
builds and boots the standalone artifact on port 3100 rather than reusing
whatever is on 3000.

## Build and deploy

`output: "standalone"`, so the droplet needs no `node_modules`:

```bash
npm run build
npm start              # copies static assets into the bundle, runs server.js
```

`npm start` goes through `scripts/start-standalone.mjs` because `next start`
refuses to serve a standalone build, and because Next omits `.next/static` and
`public/` from the bundle on the assumption a CDN serves them.
