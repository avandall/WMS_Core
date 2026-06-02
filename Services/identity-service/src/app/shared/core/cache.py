"""Lightweight cache decorators for the local identity service runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar


P = ParamSpec("P")
T = TypeVar("T")


def cached(prefix: str, ttl: int = 300) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """No-op async cache decorator matching the shared service API."""

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def invalidate_cache_pattern(pattern: str) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """No-op async invalidation decorator matching the shared service API."""

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await fn(*args, **kwargs)

        return wrapper

    return decorator
