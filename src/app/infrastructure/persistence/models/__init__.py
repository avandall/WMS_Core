"""SQLAlchemy model package for persistence layer.

Keep imports lazy so `import app.infrastructure.persistence.models` doesn't
require SQLAlchemy (useful for import-only smoke tests and tooling).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


from app.core.database import Base

_LAZY_EXPORTS: dict[str, str] = {
    "UserModel": "app.infrastructure.persistence.models.user_table",
    "ProductModel": "app.infrastructure.persistence.models.product_table",
    "InventoryModel": "app.infrastructure.persistence.models.inventory_table",
    "WarehouseModel": "app.infrastructure.persistence.models.warehouse_table",
    "WarehouseInventoryModel": "app.infrastructure.persistence.models.warehouse_table",
    "DocumentModel": "app.infrastructure.persistence.models.document_table",
    "DocumentItemModel": "app.infrastructure.persistence.models.document_item_table",
    "CustomerModel": "app.infrastructure.persistence.models.customer_table",
    "CustomerPurchaseModel": "app.infrastructure.persistence.models.customer_purchase_table",
    "AuditLogModel": "app.infrastructure.persistence.models.audit_log_table",
    "AuditEventModel": "app.infrastructure.persistence.models.audit_event_table",
    "PositionModel": "app.infrastructure.persistence.models.position_table",
    "PositionInventoryModel": "app.infrastructure.persistence.models.position_inventory_table",
}

_MODEL_MODULES: list[str] = sorted(set(_LAZY_EXPORTS.values()))


def import_all_models() -> None:
    """Eagerly import all model modules to register SQLAlchemy tables."""
    for module_path in _MODEL_MODULES:
        import_module(module_path)


def __getattr__(name: str) -> Any:
    module_path = _LAZY_EXPORTS.get(name)
    if not module_path:
        raise AttributeError(name)
    module = import_module(module_path)
    try:
        return getattr(module, name)
    except AttributeError as exc:
        raise AttributeError(name) from exc


__all__ = ["import_all_models", "Base", *_LAZY_EXPORTS.keys()]
