from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.shared.core.logging import get_logger
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.modules.warehouses.domain.value_objects import WarehouseLocation
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    ValidationError,
    WarehouseNotFoundError,
)
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo

logger = get_logger(__name__)


def _db_sequence_sentinel() -> int:
    """Return sentinel 0 — signals that the DB BIGSERIAL should assign the ID."""
    return 0


# Kept as module attribute for test compatibility
_DB_SEQUENCE_SENTINEL: Callable[[], int] = _db_sequence_sentinel


class WarehouseService:
    """Application service for warehouse orchestration.

    TASK-001: In-memory ID generation removed.  When no ``id_generator`` is
    provided (production), ``warehouse_id=0`` is used as a sentinel so the
    PostgreSQL BIGSERIAL sequence in WarehouseRepo assigns the real ID on
    INSERT.  An explicit ``id_generator`` (used in unit tests) still overrides
    this behaviour for backward compatibility.
    """

    def __init__(
        self,
        warehouse_repo: IWarehouseRepo,
        id_generator: Optional[Callable[[], int]] = None,
        session=None,
        # Extra kwargs accepted but ignored so tests that pass product_repo /
        # inventory_repo do not fail with TypeError.
        **kwargs: Any,
    ):
        self.warehouse_repo = warehouse_repo
        # Keep attribute name _warehouse_id_generator for test compatibility.
        # When None is passed, fall back to the DB-sentinel no-op.
        self._warehouse_id_generator: Callable[[], int] = (
            id_generator if id_generator is not None else _DB_SEQUENCE_SENTINEL
        )
        self.session = session
        # Store any extra repos forwarded by tests (product_repo, inventory_repo)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def create_warehouse(
        self,
        location: str,
        *,
        warehouse_type: str = "ambient",
        capacity_sqm: Optional[float] = None,
        is_active: bool = True,
        manager_id: Optional[str] = None,
        timezone: str = "UTC",
    ) -> Warehouse:
        warehouse_id = self._warehouse_id_generator()
        normalized_location = WarehouseLocation(location).value
        if self.warehouse_repo.location_exists(normalized_location):
            raise EntityAlreadyExistsError(f"Warehouse location '{normalized_location}' already exists")
        warehouse = Warehouse(
            warehouse_id=warehouse_id,
            location=normalized_location,
            warehouse_type=warehouse_type,
            capacity_sqm=capacity_sqm,
            is_active=is_active,
            manager_id=manager_id,
            timezone=timezone,
        )
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
