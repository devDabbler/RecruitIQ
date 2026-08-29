"""Guards on what may run directly on the event loop.

Most of this app's ORM work is synchronous. A handler declared `async def` runs
*on the event loop*, so a blocking `db.query(...)` inside one stops every other
request in the worker until it finishes. The dashboard fans out several API
calls with `Promise.all`, so its latency was the sum of its endpoints rather
than the slowest one.

A handler declared plain `def` is run by Starlette in a threadpool instead, and
the blocking call stops only its own thread. These tests pin the three routes
that fix down, plus the pool arithmetic that makes threadpool execution safe.
"""
from __future__ import annotations

import asyncio
import inspect

import pytest

from backend.main import THREADPOOL_LIMIT, app
from backend.utils.database import engine

# The dashboard's fan-out. Each does sync ORM work with no `await` in its body,
# so each must stay a plain `def`.
DASHBOARD_ROUTES = [
    ("/api/candidates/", "GET"),
    ("/api/candidates/skills_breakdown", "GET"),
    ("/api/jobs/", "GET"),
]


def endpoint_for(path: str, method: str):
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", ()):
            return route.endpoint
    raise AssertionError(f"no route registered for {method} {path}")


@pytest.mark.parametrize("path,method", DASHBOARD_ROUTES)
def test_dashboard_routes_do_not_run_on_the_event_loop(path, method):
    endpoint = endpoint_for(path, method)
    assert not inspect.iscoroutinefunction(endpoint), (
        f"{method} {path} is `async def` but does synchronous ORM work, which "
        f"blocks the event loop for every other request. Declare it plain `def` "
        f"so Starlette runs it in the threadpool."
    )


def test_threadpool_cannot_outnumber_the_connection_pool():
    """Bound concurrency on threads, which are cheap, not on connections.

    Starlette's default threadpool is 40 workers. Each in-flight sync request
    holds one session for its whole life, so more concurrent threads than the
    engine can serve turns surplus load into `pool_timeout` 500s. Keeping the
    cap under the ceiling makes surplus load wait instead.
    """
    capacity = engine.pool.size() + engine.pool._max_overflow
    assert THREADPOOL_LIMIT < capacity, (
        f"threadpool cap ({THREADPOOL_LIMIT}) must stay below engine capacity "
        f"({capacity}); raise pool_size/max_overflow in utils/database.py first."
    )


def test_startup_applies_the_threadpool_limit():
    """The cap is only real if the startup hook actually installs it.

    anyio's limiter is scoped to the running event loop, so this drives its own
    loop rather than mutating the one the rest of the suite shares.
    """
    import anyio.to_thread

    handlers = [h for h in app.router.on_startup if h.__name__ == "limit_threadpool"]
    assert handlers, "no limit_threadpool startup handler registered"

    async def run():
        await handlers[0]()
        return anyio.to_thread.current_default_thread_limiter().total_tokens

    assert asyncio.run(run()) == THREADPOOL_LIMIT
