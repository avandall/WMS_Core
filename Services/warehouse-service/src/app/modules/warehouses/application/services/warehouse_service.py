from __future__ import annotations

from typing import Any, Dict, List

from app.shared.core.logging import get_logger
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    ValidationError,
    WarehouseNotFoundError,
)
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo
from app.shared.utils.infrastructure import warehouse_id_generator

logger = get_logger(__name__)


class WarehouseService:
    """Application service for warehouse orchestration."""

    def __init__(
        self,
        warehouse_repo: IWarehouseRepo,
        id_generator=None,
    ):
        self.warehouse_repo = warehouse_repo
        self._warehouse_id_generator = id_generator or warehouse_id_generator()

    def create_warehouse(self, location: str) -> Warehouse:
        warehouse_id = self._warehouse_id_generator()
        warehouse = Warehouse(warehouse_id=warehouse_id, location=location)
        self.warehouse_repo.create_warehouse(warehouse)
        return warehouse

    def create_warehouse_with_id(self, warehouse: Warehouse) -> None:
        existing = self.warehouse_repo.get(warehouse.warehouse_id)
        if existing:
            raise EntityAlreadyExistsError(
                f"Warehouse with ID {warehouse.warehouse_id} already exists"
            )
        self.warehouse_repo.create_warehouse(warehouse)

    def get_warehouse(self, warehouse_id: int) -> Warehouse:
        warehouse = self.warehouse_repo.get(warehouse_id)
        if not warehouse:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found")
        return warehouse

    def get_all_warehouses_with_inventory_summary(self) -> List[Dict[str, Any]]:
        result = []
        for warehouse in self.warehouse_repo.get_all().values():
            result.append(
                {
                    "warehouse": warehouse,
                    "inventory_summary": {
                        "total_items": 0,
                        "unique_products": 0,
                        "inventory_details": [],
                    },
                }
            )
        return result

    def get_all_warehouses(self) -> List[Warehouse]:
        return list(self.warehouse_repo.get_all().values())

    def transfer_all_inventory(
        self, from_warehouse_id: int, to_warehouse_id: int
    ) -> List[dict]:
        if from_warehouse_id == to_warehouse_id:
            raise ValidationError("Cannot transfer to the same warehouse")
        self.get_warehouse(from_warehouse_id)
        self.get_warehouse(to_warehouse_id)
        return []

    def delete_warehouse(self, warehouse_id: int) -> None:
        self.get_warehouse(warehouse_id)
        self.warehouse_repo.delete(warehouse_id)
