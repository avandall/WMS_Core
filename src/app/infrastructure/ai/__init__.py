"""AI infrastructure (LangChain powered).

This package contains the concrete implementation for the "chat with DB" feature:
customer question -> safe SQL -> read-only execution -> natural language answer.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_EXPORTS: dict[str, str] = {
    "handle_customer_chat_with_db": "app.infrastructure.ai.chains",
    "ai_engine_settings": "app.infrastructure.ai.settings",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_EXPORTS.get(name)
    if not module_path:
        raise AttributeError(name)
    module = import_module(module_path)
    try:
        return getattr(module, name)
    except AttributeError as exc:
        raise AttributeError(name) from exc


__all__ = list(_LAZY_EXPORTS.keys())
