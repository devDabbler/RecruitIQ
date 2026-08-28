# ADR 0003: Deploy onto the existing trading host, natively

**Date:** 2026-08-28 · **Status:** Accepted (Phase 4)

## Context

The spec (§3, §9) fixes the hosting budget at ~$0/month by piggybacking the
`sentient-trader` droplet: 4 vCPU, 7.8 GB RAM, Ubuntu 24.04, already running
nginx, Redis, and a live trading system whose money-touching paths are
latency-sensitive. At deploy time the box had ~2.4 GB RAM available and 4 GB
of swap, 1.1 GB of it in use — tighter than the spec's snapshot two days
earlier, because an IB Gateway process had joined in between. The droplet had
neither Docker nor Postgres installed.

The audience-visible reproducibility story is `git clone && docker compose
up`, which shipped in Phase 1 and runs on any evaluator's machine. Nothing an
evaluator can see depends on how the droplet itself runs the app.

## Decision

**Native processes under systemd; Docker stays a dev-only concern.**
Installing the Docker daemon on a production trading host buys zero visible
polish and adds a few hundred MB of overhead plus one more failure domain.
Postgres 16 + pgvector come from apt, listening on loopback only.

**One domain, one proxy hop.** nginx serves `resumecupid.ai` and proxies
everything to the Next.js standalone server (127.0.0.1:3001). The browser
never talks to FastAPI (Phase 3 design); Next reaches it server-side at
127.0.0.1:8020. Ports 8000/8001 belong to the neighbor.

**RecruitIQ is the sacrificial tenant.** Both units carry
`MemoryHigh`/`MemoryMax` (API 768M/1G, web 384M/512M), so under memory
pressure the kernel throttles and then kills RecruitIQ, never the trading
system. `next build` — the one RAM-spiky operation — runs inside a
`systemd-run` scope with its own `MemoryMax=1200M` and reduced CPU weight: a
build can OOM itself but cannot push the neighbor into swap.

**Rate limiting lives in nginx, not Redis.** The spec called for Redis-backed
per-IP limits; the backend never grew an application-level limiter, and
adding one during deploy would be new machinery for a demo. nginx `limit_req`
zones cap the two LLM-backed paths (resume parse, assistant chat) at
12 req/min per IP and everything else at 10 req/s, which is what the guard
was for: a stranger cannot run up the OpenRouter bill or queue work on the
GPU tunnel. Redis (logical db 3, isolated from the neighbor's db 0) serves
only the parser cache. Revisit if the app ever grows a metered write tier.

**Secrets in `/etc/recruitiq/env`** (root:recruitiq, 640), never in git.
Deploys are one script: `scripts/deploy.sh` pulls, installs, builds inside
the memory fence, migrates, restarts, health-checks.

## Consequences

- Steady state measured after first deploy: API 332 MB, web 48 MB, plus
  Postgres's workers — under 500 MB total, inside the 2.4 GB that was
  available.
- The demo's live-upload path depends on the Cloudflare tunnel to the home
  GPU for embeddings; if the tunnel is down, browsing (pre-embedded seed
  data) still works and only fresh uploads degrade — the trade §4.2 accepted.
- Prod diverges from dev (native vs Docker). Accepted: the divergence is one
  `docker compose up` vs three systemd units, documented in this file and in
  `scripts/deploy.sh`.
- If the neighbor's footprint grows further, the escape hatch is building in
  GitHub Actions and shipping the artifact, removing the last RAM spike.
