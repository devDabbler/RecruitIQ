"""Per-IP daily cap on the public resume-parse endpoints.

nginx already enforces a per-minute rate (12r/m, burst 6) on /api/resume/;
this bounds the *daily* total so a patient scraper cannot run up the
OpenRouter bill a minute at a time. Admins are exempt. If Redis is down the
cap degrades open: a missing counter must never take the demo's flagship
feature down with it.
"""
import logging
from datetime import date, timedelta

from fastapi import Depends, HTTPException, Request

from backend.utils.auth import ROLE_ADMIN, get_optional_user
from backend.utils.config import get_settings

logger = logging.getLogger(__name__)

# Keyed per IP per UTC day; expiry comfortably outlives the day it counts.
_KEY_TTL_SECONDS = int(timedelta(hours=25).total_seconds())


def _client_ip(request: Request) -> str:
    # Behind nginx everything arrives from 127.0.0.1; the real address is in
    # X-Real-IP (set by the standard proxy_params). Falling back to the socket
    # address keeps dev and tests working without a proxy.
    forwarded = request.headers.get("x-real-ip")
    if forwarded:
        return forwarded.strip()
    return request.client.host if request.client else "unknown"


async def enforce_parse_quota(
    request: Request,
    current_user=Depends(get_optional_user),
) -> None:
    if current_user is not None and current_user.role == ROLE_ADMIN:
        return

    settings = get_settings()
    limit = settings.parse_daily_limit
    if limit <= 0:  # explicit off switch
        return

    key = f"recruitiq:parse_quota:{_client_ip(request)}:{date.today().isoformat()}"
    try:
        from backend.utils.redis_client import get_redis_client

        redis = await get_redis_client()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, _KEY_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Parse quota check skipped (Redis unavailable): %s", exc)
        return

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail=(
                "Daily demo limit reached for resume parsing. "
                "Come back tomorrow, or reach out for a walkthrough."
            ),
        )
