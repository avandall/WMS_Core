"""Domain package.

Keep this module lightweight to avoid circular imports. Use direct imports from
`app.domain.entities` and `app.domain.interfaces` in new code.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from app.shared.domain.business_exceptions import (  # noqa: F401
    BusinessRuleViolationError,
    DomainError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    InsufficientStockError,
    InvalidDocumentStatusError,
    InvalidIDError,
    InvalidQuantityError,
    ProductNotFoundError,
    ValidationError,
    WarehouseNotFoundError,
)


_LAZY_EXPORTS: dict[str, str] = {
    "DomainEntity": "app.domain.interfaces.entity",
    "Document": "app.domain.entities.document",
    "DocumentProduct": "app.domain.entities.document",
    "DocumentStatus": "app.domain.entities.document",
    "DocumentType": "app.domain.entities.document",
    "InventoryItem": "app.domain.entities.inventory",
    "Position": "app.domain.entities.position",
    "PositionInventoryItem": "app.domain.entities.position",
    "Product": "app.domain.entities.product",
    "User": "app.domain.entities.user",
    "Warehouse": "app.domain.entities.warehouse",
    "WarehouseManager": "app.domain.entities.warehouse",
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


__all__ = [
    "BusinessRuleViolationError",
    "DomainError",
    "EntityAlreadyExistsError",
    "EntityNotFoundError",
    "InsufficientStockError",
    "InvalidDocumentStatusError",
    "InvalidIDError",
    "InvalidQuantityError",
    "ProductNotFoundError",
    "ValidationError",
    "WarehouseNotFoundError",
    *_LAZY_EXPORTS.keys(),
]
