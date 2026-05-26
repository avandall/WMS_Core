from __future__ import annotations

from typing import Any, Dict, List

from app.shared.core.logging import get_logger
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.modules.warehouses.domain.value_objects import WarehouseLocation
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
        session=None,
    ):
        self.warehouse_repo = warehouse_repo
        self._warehouse_id_generator = id_generator or warehouse_id_generator()
        self.session = session

    def create_warehouse(self, location: str) -> Warehouse:
        warehouse_id = self._warehouse_id_generator()
        normalized_location = WarehouseLocation(location).value
        if self.warehouse_repo.location_exists(normalized_location):
            raise EntityAlreadyExistsError(f"Warehouse location '{normalized_location}' already exists")
        warehouse = Warehouse(warehouse_id=warehouse_id, location=normalized_location)
        self.warehouse_repo.create_warehouse(warehouse)
        self._commit_if_needed()
        return warehouse

    def create_warehouse_with_id(self, warehouse: Warehouse) -> None:
        existing = self.warehouse_repo.get(warehouse.warehouse_id)
        if existing:
            raise EntityAlreadyExistsError(
                f"Warehouse with ID {warehouse.warehouse_id} already exists"
            )
        self.warehouse_repo.create_warehouse(warehouse)
        self._commit_if_needed()

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

    def update_warehouse_location(self, warehouse_id: int, new_location: str) -> Warehouse:
        warehouse = self.get_warehouse(warehouse_id)
        normalized_location = WarehouseLocation(new_location).value
        if self.warehouse_repo.location_exists(
            normalized_location,
            excluding_warehouse_id=warehouse_id,
        ):
            raise EntityAlreadyExistsError(f"Warehouse location '{normalized_location}' already exists")
        warehouse.update_location(normalized_location)
        self.warehouse_repo.save(warehouse)
        self._commit_if_needed()
        return warehouse

    def get_warehouse_location_metadata(self, warehouse_id: int) -> dict:
        warehouse = self.get_warehouse(warehouse_id)
        return warehouse.location_metadata()

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
        self._commit_if_needed()

    def _commit_if_needed(self) -> None:
        if self.session is not None:
            self.session.commit()
