"""Thread-safe ID generators used by services and repositories."""

from __future__ import annotations

import threading
from typing import Callable


class IDGenerator:
    """Thread-safe ID generator registry."""

    _generators: dict[str, "_ThreadSafeCounter"] = {}
    _lock = threading.Lock()

    @staticmethod
    def get_generator(name: str, start_id: int = 1) -> Callable[[], int]:
        with IDGenerator._lock:
            if name not in IDGenerator._generators:
                IDGenerator._generators[name] = _ThreadSafeCounter(start_id)
            return IDGenerator._generators[name].next_id

    @staticmethod
    def reset_generator(name: str, start_id: int = 1) -> None:
        with IDGenerator._lock:
            IDGenerator._generators[name] = _ThreadSafeCounter(start_id)


class _ThreadSafeCounter:
    def __init__(self, start: int = 1):
        self._counter = start - 1
        self._lock = threading.Lock()

    def next_id(self) -> int:
        with self._lock:
            self._counter += 1
            return self._counter


def document_id_generator() -> Callable[[], int]:
    return IDGenerator.get_generator("document", 1)


def warehouse_id_generator() -> Callable[[], int]:
    return IDGenerator.get_generator("warehouse", 1)


def product_id_generator() -> Callable[[], int]:
    return IDGenerator.get_generator("product", 1)

