from __future__ import annotations

from typing import Any, Protocol


class InventoryEventPublisher(Protocol):
    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        pass


class NoopInventoryEventPublisher:
    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        return None
