"""Dependency injection for Warehouse Service endpoints."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo
from app.modules.inventory.application.services.stock_movement_service import StockMovementService
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.positions.application.services.position_service import PositionService
from app.modules.positions.infrastructure.repositories.position_repo import PositionRepo
from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
from app.modules.warehouses.application.services.warehouse_operations_service import (
    WarehouseOperationsService,
)
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.shared.core.database import get_session


class _NullDocumentRepo(IDocumentRepo):
    def save(self, document):  # type: ignore[no-untyped-def]
        return None

    def get(self, document_id: int):  # type: ignore[no-untyped-def]
        return None

    def get_all(self):  # type: ignore[no-untyped-def]
        return []

    def update_status(self, document_id: int, new_status):  # type: ignore[no-untyped-def]
        return None

    def delete(self, document_id: int) -> None:
        return None


def get_warehouse_repo(db: Session = Depends(get_session)) -> WarehouseRepo:
    return WarehouseRepo(db)


def get_product_repo(db: Session = Depends(get_session)) -> ProductRepo:
    return ProductRepo(db)


def get_inventory_repo(db: Session = Depends(get_session)) -> InventoryRepo:
    return InventoryRepo(db)


def get_position_repo(db: Session = Depends(get_session)) -> PositionRepo:
    return PositionRepo(db)


def get_warehouse_service(db: Session = Depends(get_session)) -> WarehouseService:
    return WarehouseService(
        warehouse_repo=WarehouseRepo(db),
        product_repo=ProductRepo(db),
        inventory_repo=InventoryRepo(db),
    )


def get_warehouse_operations_service(db: Session = Depends(get_session)) -> WarehouseOperationsService:
    return WarehouseOperationsService(
        warehouse_repo=WarehouseRepo(db),
        product_repo=ProductRepo(db),
        inventory_repo=InventoryRepo(db),
        document_repo=_NullDocumentRepo(),
    )


def get_position_service(db: Session = Depends(get_session)) -> PositionService:
    return PositionService(position_repo=PositionRepo(db), audit_event_repo=None)


def get_stock_movement_service(db: Session = Depends(get_session)) -> StockMovementService:
    return StockMovementService(
        position_repo=PositionRepo(db),
        warehouse_repo=WarehouseRepo(db),
        session=db,
        audit_event_repo=None,
    )

