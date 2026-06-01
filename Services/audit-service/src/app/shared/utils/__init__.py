"""Utility helpers (compatibility).

Prefer putting domain-specific logic on domain entities and application-specific
logic inside services/use-cases. This package is kept for small, dependency-free
helpers and to preserve legacy import paths.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_EXPORTS: dict[str, str] = {
    # infrastructure
    "IDGenerator": "app.utils.infrastructure.id_generator",
    "document_id_generator": "app.utils.infrastructure.id_generator",
    "product_id_generator": "app.utils.infrastructure.id_generator",
    "warehouse_id_generator": "app.utils.infrastructure.id_generator",
    # domain utils
    "ValidationUtils": "app.utils.domain",
    "BusinessRulesUtils": "app.utils.domain",
    "DateUtils": "app.utils.domain",
    # application utils
    "PaginatedResult": "app.utils.application",
    "PaginationUtils": "app.utils.application",
    "SortingUtils": "app.utils.application",
    "FilterUtils": "app.utils.application",
    "SearchUtils": "app.utils.application",
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
