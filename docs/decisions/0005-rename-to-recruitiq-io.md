# ADR 0005: Rename the live site to recruitiq.io, redirect resumecupid.ai

**Date:** 2026-08-30 · **Status:** Accepted (Phase 5) · **Amends:** ADR 0003, ADR 0004

## Context

The product is called RecruitIQ everywhere it is written down - the repo, the
README, the design spec, the systemd units, the nginx zone names. The URL said
`resumecupid.ai`, a domain carried over from an earlier iteration of the same
two-year line of work.

The gap was costing something specific. The audience is TA leaders at AI
companies; `resumecupid` reads consumer dating app, `RecruitIQ` reads B2B
intelligence platform. The README carried an apologetic parenthetical
explaining the mismatch, and a footer line acknowledging it was in the spec as
a planned mitigation - both of which are tells that the name was doing damage
that had to be worked around rather than fixed.

`recruitiq.io` was available at standard registration price and is an exact
brand match. `.io` reads technical to this particular audience.

The counter-argument, which is real: `.ai` carries genuine signal with an
AI-company audience, and the move trades that away. It was judged the lesser
loss - brand coherence beats TLD signal when the brand is the artifact being
demonstrated.

Audit of what actually depended on the old name, before deciding: nothing in
the application. `API_BASE_URL` is `http://127.0.0.1:8020` in the systemd unit
and the browser never talks to FastAPI directly, so no origin is baked into any
build. The `BASE_URL` and `API_URL` entries in `/etc/recruitiq/env` were found
to be vestigial - no code reads either. There is no `metadataBase`, no sitemap,
no canonical tag, and the footer names the product rather than the domain. The
change is therefore DNS, certificate, `server_name`, and prose only. No
rebuild, no migration, no code.

## Decision

**`recruitiq.io` is canonical. `resumecupid.ai` redirects to it, preserving the
path.** The old domain stays registered indefinitely; it is a redirect, not a
retirement, so every link already handed out keeps working.

**The redirect lives at Cloudflare's edge, with an nginx block as fallback.**
ADR 0004 already put the site behind Cloudflare for HTTP/2 and edge caching, so
answering the redirect at a PoP near the visitor rather than in NYC is
consistent with that decision and saves old-link visitors the origin round
trip. But an edge Redirect Rule is dashboard state, invisible to this repo and
to `deploy.sh`. `deploy/nginx-recruitiq.conf` therefore also carries a
`resumecupid.ai` server block that redirects. If the Cloudflare rule is ever
deleted or the zone un-proxied, the old domain still redirects instead of
quietly serving a second copy of the app under the wrong name - which is the
failure that would undo the point of the rename.

**302 first, 301 after about a week.** A 301 is cached by browsers essentially
forever; anyone who follows one while the new domain is misconfigured is pinned
to a broken destination with no server-side remedy. The correct search signal
is worth less than reversibility for a portfolio demo during its first week.
Promotion to 301 must change *both* layers together - a mismatch means the
answer depends on which layer served it.

**`recruitiq.io` goes behind Cloudflare's proxy too.** Not optional. The
HTTP/2, HTTP/3 and edge-cached-chunks win from ADR 0004 is a property of the
proxied zone, not of the account. A canonical domain left grey-clouded would be
measurably slower than the domain it replaced.

## Consequences

- **The ACME challenge path must be excluded from the redirect rule.** Renewal
  for `resumecupid.ai` uses HTTP-01 through Cloudflare (ADR 0004). An
  unconditional redirect catches `/.well-known/acme-challenge/...` too and
  sends Let's Encrypt to the wrong host, so the cert silently fails to renew
  ~60 days later, long after anyone is watching. The rule is scoped with
  `not starts_with(http.request.uri.path, "/.well-known/")`. The
  `resumecupid.ai` certificate is kept renewing rather than allowed to lapse,
  because the nginx fallback block above can only serve an HTTPS redirect if
  the origin still has a valid certificate for that name.
- **Initial issuance for `recruitiq.io` happens grey-clouded**, before the
  proxy is enabled. Renewals demonstrably work through the proxy, but first
  issuance has no fallback if it does not, and the grey-cloud window is free.
- **Cloudflare SSL mode must be Full (strict) before the orange cloud goes on.**
  A new zone can default to Flexible, which terminates TLS at the edge and
  talks plain HTTP to an origin whose nginx redirects HTTP to HTTPS - an
  infinite loop that presents as a dead site, not as a warning.
- Two Cloudflare zones now exist for one property. `cloudflare-realip.conf` and
  `scripts/update_cloudflare_ips.sh` follow the canonical zone; the legacy zone
  never reaches the origin in normal operation and needs neither.
- The free plan's 100s proxied-request ceiling (error 524) now applies to
  `recruitiq.io`, exactly as it did before under ADR 0004. Unchanged, restated
  so it is not rediscovered.
- ADRs 0003 and 0004 keep their original text, since they record decisions made
  when the domain was `resumecupid.ai` and rewriting them would falsify the
  record. Both carry a pointer here.
