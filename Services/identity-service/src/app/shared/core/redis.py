"""Minimal Redis facade for identity-service local mode."""

from __future__ import annotations


class RedisManager:
    async def delete(self, _key: str) -> None:
        return None


redis_manager = RedisManager()
