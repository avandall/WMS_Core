from __future__ import annotations

from typing import Any, Protocol


class DomainEntity(Protocol):
    @property
    def identity(self) -> Any:
        ...


__all__ = ["DomainEntity"]

