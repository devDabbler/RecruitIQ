#!/usr/bin/env bash
# Regenerate the Cloudflare real-IP snippet from Cloudflare's published ranges.
#
#   scripts/update_cloudflare_ips.sh              # rewrite deploy/cloudflare-realip.conf
#   scripts/update_cloudflare_ips.sh --check      # exit 1 if the file is stale
#
# Cloudflare changes these ranges rarely. When they do, a range we no longer
# trust stops being rewritten, so those visitors all collapse onto one edge
# address and start sharing a rate-limit bucket - the exact failure this file
# exists to prevent. Run --check from time to time rather than assuming.
#
# After updating, copy to the droplet and reload:
#   scp deploy/cloudflare-realip.conf root@HOST:/etc/nginx/snippets/
#   ssh root@HOST 'nginx -t && systemctl reload nginx'
set -euo pipefail

cd "$(dirname "$0")/.."
TARGET="deploy/cloudflare-realip.conf"
CHECK_ONLY=false
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=true

v4=$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v4)
v6=$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v6)

if [[ -z "$v4" || -z "$v6" ]]; then
    echo "refusing to write: Cloudflare returned an empty list" >&2
    exit 1
fi

# Keep the commentary at the top of the existing file; only the directives are
# generated. The "why" is worth more than the list and should not be rewritten
# by a script.
header=$(sed -n '1,/^$/p' "$TARGET" 2>/dev/null || true)
if [[ -z "$header" ]]; then
    echo "missing $TARGET - restore it from git before regenerating" >&2
    exit 1
fi

generated=$(
    printf '%s\n' "$header"
    while read -r cidr; do [[ -n "$cidr" ]] && echo "set_real_ip_from $cidr;"; done <<<"$v4"
    echo
    while read -r cidr; do [[ -n "$cidr" ]] && echo "set_real_ip_from $cidr;"; done <<<"$v6"
    echo
    echo "# CF-Connecting-IP carries a single address, so real_ip_recursive is not needed."
    echo "# Preferred over X-Forwarded-For, which a client can forge; this header is set"
    echo "# by Cloudflare itself and the set_real_ip_from list above is what makes"
    echo "# trusting it safe."
    echo "real_ip_header CF-Connecting-IP;"
)

if $CHECK_ONLY; then
    if diff -q <(printf '%s\n' "$generated") "$TARGET" >/dev/null 2>&1; then
        echo "up to date"
    else
        echo "STALE - Cloudflare's ranges no longer match $TARGET" >&2
        diff <(printf '%s\n' "$generated") "$TARGET" >&2 || true
        exit 1
    fi
else
    printf '%s\n' "$generated" >"$TARGET"
    echo "wrote $TARGET"
fi
