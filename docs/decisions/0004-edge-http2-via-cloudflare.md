# ADR 0004: Get HTTP/2 from Cloudflare's edge, not from the droplet's nginx

**Date:** 2026-08-29 · **Status:** Accepted (Phase 5)

> The domain was renamed to `recruitiq.io` on 2026-08-30 (ADR 0005). Everything
> below still holds; read `resumecupid.ai` as "the canonical domain". The
> renamed zone is proxied the same way, and for the reasons given here.

## Context

`resumecupid.ai` serves HTTP/1.1 only. The homepage pulls 10 subresources
against a browser's 6-connection-per-origin cap, so a cold load costs an extra
round-trip wave — roughly 100-200ms at a typical ~150ms RTT. Enabling HTTP/2
was the obvious fix.

It is not available cleanly on this box. Two findings, both measured rather
than assumed:

**HTTP/2 cannot be scoped to RecruitIQ on nginx 1.24.** Before 1.25.1 the
`http2` flag is a property of the *listen socket*, not the server block.
`resumecupid.ai` and `sentienttrader.ai` share `0.0.0.0:443`. Tested on an
unused port with two server blocks and `http2` on only the first: **both**
negotiated HTTP/2. Enabling it for RecruitIQ necessarily enables it for the
trading system's origin, which ADR 0003 and CLAUDE.md put off limits.

**Upgrading nginx is disproportionate.** Ubuntu 24.04 ships no nginx ≥1.25 in
`noble`, `noble-updates` or `noble-security` — 1.24.0 is the ceiling. Getting
the per-server `http2 on;` directive means replacing the distro package with
nginx.org's, which conflicts with `nginx-common`. That package owns
`/etc/nginx/nginx.conf` (carrying the `include sites-enabled/*` line) and
`/etc/nginx/proxy_params`, which both site configs include. The swap leaves
nginx unable to start until those are rebuilt by hand, taking the trading
system's origin down with it, and moves nginx off Ubuntu's security-update
track permanently.

Separately: `sentienttrader.ai` already resolves to Cloudflare IPs on
Cloudflare nameservers. `resumecupid.ai` resolves straight to the droplet on
registrar DNS.

## Decision

**Put `resumecupid.ai` behind Cloudflare's proxy; leave the droplet's nginx at
HTTP/1.1.**

Cloudflare terminates HTTP/2 *and* HTTP/3 at the edge regardless of what the
origin speaks, so the browser-side win lands without touching nginx. It also
caches the eight static Next.js chunks at a PoP near the visitor, which is
worth more than origin HTTP/2 would have been — the chunks stop crossing the
country at all. The change is scoped to one domain by construction, so the
shared-socket problem disappears rather than being managed.

Cost is $0 on the free plan, matching the spec's hosting budget (§3).

**Trust Cloudflare's forwarded address, scoped to RecruitIQ's server block.**
Proxying breaks two IP-keyed mechanisms at once, both silently:

- the `limit_req` zones key on `$binary_remote_addr` (ADR 0003), so the 10r/s
  and 12r/m budgets would be shared by the whole internet
- `backend/utils/parse_quota.py` reads `X-Real-IP`, which `proxy_params` fills
  from `$remote_addr`, so the daily parse limit would be consumed globally by
  whoever arrived first

`deploy/cloudflare-realip.conf` restores `$remote_addr` from
`CF-Connecting-IP`. The realip module runs at post-read, before `limit_req` is
evaluated at preaccess, so one fix covers both. It is `include`d from
RecruitIQ's server block rather than dropped in `conf.d/`, because
http-context directives would change SentientTrader's request handling too.

`set_real_ip_from` trusts only Cloudflare's published ranges, which makes the
snippet inert until traffic actually arrives via Cloudflare — so it was
installed *before* the DNS cutover, leaving no window where the site is
proxied but the quota is broken. Verified: a forged `CF-Connecting-IP` from a
non-Cloudflare source is ignored, so the header cannot be used to dodge either
limit.

## Consequences

- Cold loads get HTTP/2, HTTP/3 and edge-cached static assets. Origin protocol
  is unchanged, so nothing about the trading system moves.
- Cloudflare's free plan cuts proxied requests at 100s (error 524). The
  `/api/resume/` (180s) and `/api/assistant/` (300s) read timeouts become
  unreachable; a pathologically slow LLM call that succeeds today would fail.
  Typical parses run a few seconds, so this is accepted rather than mitigated.
- certbot's HTTP-01 challenge now routes through Cloudflare. Works, but
  `certbot renew --dry-run` is the check that matters; DNS-01 is the cleaner
  long-term answer if it proves fragile.
- Cloudflare's IP ranges change occasionally. A stale list means those visitors
  collapse onto one edge address and share a rate-limit bucket — the exact
  failure this guards against. `scripts/update_cloudflare_ips.sh --check`
  detects it.
- HTTP/2 on the droplet's nginx stays off, and stays off deliberately. Anyone
  revisiting it should read the shared-socket finding above first.
