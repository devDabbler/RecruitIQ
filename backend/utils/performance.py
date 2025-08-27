"""Lightweight performance profiling utilities.

Provides decorators to log execution duration of synchronous and asynchronous functions.

Usage:

    from backend.utils.performance import timed, async_timed

    @timed
    def my_func(...):
        ...

    @async_timed
    async def my_async_func(...):
        ...
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


def _log_duration(logger: logging.Logger, name: str, duration_seconds: float) -> None:
    """Log a formatted duration entry using the provided logger."""
    logger.info("[perf] %s took %.2f ms", name, duration_seconds * 1000)


def timed(fn: Callable[..., T]) -> Callable[..., T]:
    """Decorator for profiling synchronous callables."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):  # type: ignore[override]
        logger = logging.getLogger(fn.__module__)
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            _log_duration(logger, fn.__qualname__, time.perf_counter() - start)

    return wrapper  # type: ignore[return-value]


def async_timed(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Decorator for profiling async callables."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any):  # type: ignore[override]
        logger = logging.getLogger(fn.__module__)
        start = time.perf_counter()
        try:
            return await fn(*args, **kwargs)
        finally:
            _log_duration(logger, fn.__qualname__, time.perf_counter() - start)

    return wrapper
