"""Dependency injection for Warehouse Service endpoints."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.positions.application.services.position_service import PositionService
from app.modules.positions.infrastructure.repositories.position_repo import PositionRepo
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.shared.core.database import get_session


def get_warehouse_repo(db: Session = Depends(get_session)) -> WarehouseRepo:
    return WarehouseRepo(db)


def get_position_repo(db: Session = Depends(get_session)) -> PositionRepo:
    return PositionRepo(db)


def get_warehouse_service(db: Session = Depends(get_session)) -> WarehouseService:
    return WarehouseService(warehouse_repo=WarehouseRepo(db))


def get_position_service(db: Session = Depends(get_session)) -> PositionService:
    return PositionService(position_repo=PositionRepo(db))
