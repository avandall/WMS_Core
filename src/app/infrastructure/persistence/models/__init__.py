"""SQLAlchemy model package for persistence layer.

Keep imports lazy so `import app.infrastructure.persistence.models` doesn't
require SQLAlchemy (useful for import-only smoke tests and tooling).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


from app.shared.core.database import Base

_LAZY_EXPORTS: dict[str, str] = {
    "UserModel": "app.modules.users.infrastructure.models.user_table",
    "ProductModel": "app.modules.products.infrastructure.models.product_table",
    "InventoryModel": "app.modules.inventory.infrastructure.models.inventory_table",
    "WarehouseModel": "app.modules.warehouses.infrastructure.models.warehouse_table",
    "WarehouseInventoryModel": "app.modules.warehouses.infrastructure.models.warehouse_table",
    "DocumentModel": "app.modules.documents.infrastructure.models.document_table",
    "DocumentItemModel": "app.modules.documents.infrastructure.models.document_item_table",
    "CustomerModel": "app.modules.customers.infrastructure.models.customer_table",
    "CustomerPurchaseModel": "app.modules.customers.infrastructure.models.customer_purchase_table",
    "AuditLogModel": "app.infrastructure.persistence.models.audit_log_table",
    "AuditEventModel": "app.infrastructure.persistence.models.audit_event_table",
    "PositionModel": "app.modules.positions.infrastructure.models.position_table",
    "PositionInventoryModel": "app.modules.inventory.infrastructure.models.position_inventory_table",
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
