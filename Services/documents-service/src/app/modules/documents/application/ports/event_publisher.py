from __future__ import annotations

from typing import Any, Protocol


class DocumentEventPublisher(Protocol):
    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        pass


class NoopDocumentEventPublisher:
    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        return None
