"""Pydantic DTOs for the application layer.

These were previously located under `app.api.schemas` in `src-old`.

Import DTOs directly from their module for best import performance, e.g.
`from app.application.dtos.product import ProductCreate`.

This package also exposes commonly used DTOs as lazy attributes.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_EXPORTS: dict[str, str] = {
    # ai
    "ChatDBRequest": "app.application.dtos.ai",
    "ChatDBResponse": "app.application.dtos.ai",
    # audit_event
    "AuditEventResponse": "app.application.dtos.audit_event",
    # auth
    "UserCreate": "app.application.dtos.auth",
    "UserResponse": "app.application.dtos.auth",
    "LoginRequest": "app.application.dtos.auth",
    "TokenResponse": "app.application.dtos.auth",
    "RefreshRequest": "app.application.dtos.auth",
    # customer
    "CustomerCreate": "app.application.dtos.customer",
    "CustomerResponse": "app.application.dtos.customer",
    "DebtUpdate": "app.application.dtos.customer",
    "CustomerUpdate": "app.application.dtos.customer",
    "PurchaseResponse": "app.application.dtos.customer",
    "CustomerDetailResponse": "app.application.dtos.customer",
    # position
    "PositionCreate": "app.application.dtos.position",
    "PositionResponse": "app.application.dtos.position",
    "PositionMoveRequest": "app.application.dtos.position",
    "WarehouseTransferPositionRequest": "app.application.dtos.position",
    "PositionInventoryItemResponse": "app.application.dtos.position",
    # document
    "DocumentItemCreate": "app.application.dtos.document",
    "DocumentItemResponse": "app.application.dtos.document",
    "DocumentCreate": "app.application.dtos.document",
    "DocumentResponse": "app.application.dtos.document",
    "DocumentUpdate": "app.application.dtos.document",
    "DocumentStatusUpdate": "app.application.dtos.document",
    "DocumentListResponse": "app.application.dtos.document",
    "DocumentSearchRequest": "app.application.dtos.document",
    # inventory
    "InventoryItemCreate": "app.application.dtos.inventory",
    "InventoryItemUpdate": "app.application.dtos.inventory",
    "InventoryItemResponse": "app.application.dtos.inventory",
    "InventoryAdjustment": "app.application.dtos.inventory",
    "StockMovementRequest": "app.application.dtos.inventory",
    "InventorySearchRequest": "app.application.dtos.inventory",
    "InventoryListResponse": "app.application.dtos.inventory",
    "LowStockItem": "app.application.dtos.inventory",
    # warehouse
    "WarehouseCreate": "app.application.dtos.warehouse",
    "WarehouseUpdate": "app.application.dtos.warehouse",
    "WarehouseResponse": "app.application.dtos.warehouse",
    "WarehouseDetailResponse": "app.application.dtos.warehouse",
    "WarehouseSearchRequest": "app.application.dtos.warehouse",
    "WarehouseListResponse": "app.application.dtos.warehouse",
    "WarehouseStats": "app.application.dtos.warehouse",
    # user
    "UserCreate": "app.application.dtos.user",
    "UserUpdate": "app.application.dtos.user",
    "UserResponse": "app.application.dtos.user",
    "UserLogin": "app.application.dtos.user",
    "UserLoginResponse": "app.application.dtos.user",
    "UserChangePassword": "app.application.dtos.user",
    "UserListResponse": "app.application.dtos.user",
    "UserSearchRequest": "app.application.dtos.user",
    # product (contains several workflow DTOs)
    "ProductCreate": "app.application.dtos.product",
    "ProductUpdate": "app.application.dtos.product",
    "ProductResponse": "app.application.dtos.product",
    "InventoryItemResponse": "app.application.dtos.product",
    "WarehouseCreate": "app.application.dtos.product",
    "WarehouseResponse": "app.application.dtos.product",
    "WarehouseInventoryRowResponse": "app.application.dtos.product",
    "ProductMovement": "app.application.dtos.product",
    "TransferInventoryRequest": "app.application.dtos.product",
    "WarehouseTransferResponse": "app.application.dtos.product",
    "DocumentProductItem": "app.application.dtos.product",
    "DocumentCreate": "app.application.dtos.product",
    "DocumentPost": "app.application.dtos.product",
    "DocumentResponse": "app.application.dtos.product",
    "InventoryReportItem": "app.application.dtos.product",
    "WarehouseInventoryReport": "app.application.dtos.product",
    "TotalInventoryReport": "app.application.dtos.product",
    "InventoryReportResponse": "app.application.dtos.product",
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

