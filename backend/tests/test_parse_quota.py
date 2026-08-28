"""The daily parse cap: counts per IP, 429s over the limit, degrades open."""
import types

import pytest
from fastapi import HTTPException

import backend.utils.win_compat  # noqa: F401

from backend.utils.auth import ROLE_ADMIN
from backend.utils.parse_quota import enforce_parse_quota


class FakeRedis:
    def __init__(self):
        self.counts = {}
        self.ttls = {}

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, seconds):
        self.ttls[key] = seconds


class DeadRedis:
    async def incr(self, key):
        raise ConnectionError("redis is down")

    async def expire(self, key, seconds):
        raise ConnectionError("redis is down")


def _request(ip="203.0.113.7", real_ip=None):
    headers = {}
    if real_ip:
        headers["x-real-ip"] = real_ip
    return types.SimpleNamespace(
        headers=headers,
        client=types.SimpleNamespace(host=ip),
    )


def _patch_redis(monkeypatch, fake):
    async def fake_get_client():
        return fake

    monkeypatch.setattr(
        "backend.utils.redis_client.get_redis_client", fake_get_client
    )


def _patch_limit(monkeypatch, limit):
    # Settings is a module-level singleton with import-time defaults, so the
    # instance attribute is the only patch point that actually takes effect.
    from backend.utils.config import get_settings

    monkeypatch.setattr(get_settings(), "parse_daily_limit", limit)


@pytest.mark.asyncio
async def test_under_the_limit_passes(monkeypatch):
    fake = FakeRedis()
    _patch_redis(monkeypatch, fake)
    _patch_limit(monkeypatch, 3)
    for _ in range(3):
        await enforce_parse_quota(_request(), current_user=None)
    assert list(fake.counts.values()) == [3]
    # First increment set an expiry so the key cannot live forever
    assert list(fake.ttls.values()) == [25 * 3600]


@pytest.mark.asyncio
async def test_over_the_limit_is_429(monkeypatch):
    _patch_redis(monkeypatch, FakeRedis())
    _patch_limit(monkeypatch, 2)
    await enforce_parse_quota(_request(), current_user=None)
    await enforce_parse_quota(_request(), current_user=None)
    with pytest.raises(HTTPException) as exc:
        await enforce_parse_quota(_request(), current_user=None)
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_ips_are_counted_separately(monkeypatch):
    _patch_redis(monkeypatch, FakeRedis())
    _patch_limit(monkeypatch, 1)
    await enforce_parse_quota(_request(ip="203.0.113.7"), current_user=None)
    # A different visitor still has their own budget
    await enforce_parse_quota(_request(ip="198.51.100.9"), current_user=None)


@pytest.mark.asyncio
async def test_nginx_real_ip_header_wins_over_socket(monkeypatch):
    fake = FakeRedis()
    _patch_redis(monkeypatch, fake)
    _patch_limit(monkeypatch, 5)
    # Behind nginx the socket peer is always 127.0.0.1; the header is the visitor
    await enforce_parse_quota(
        _request(ip="127.0.0.1", real_ip="203.0.113.7"), current_user=None
    )
    assert any("203.0.113.7" in key for key in fake.counts)


@pytest.mark.asyncio
async def test_admin_is_exempt(monkeypatch):
    fake = FakeRedis()
    _patch_redis(monkeypatch, fake)
    _patch_limit(monkeypatch, 1)
    admin = types.SimpleNamespace(role=ROLE_ADMIN)
    for _ in range(5):
        await enforce_parse_quota(_request(), current_user=admin)
    assert fake.counts == {}


@pytest.mark.asyncio
async def test_redis_down_degrades_open(monkeypatch):
    _patch_redis(monkeypatch, DeadRedis())
    _patch_limit(monkeypatch, 1)
    for _ in range(5):
        await enforce_parse_quota(_request(), current_user=None)
