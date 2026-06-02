"""Minimal session facade for identity-service local mode."""

from __future__ import annotations


class SessionManager:
    async def create_token_session(self, _token: str, _data: dict, *, ex: int | None = None) -> None:
        return None


session_manager = SessionManager()
