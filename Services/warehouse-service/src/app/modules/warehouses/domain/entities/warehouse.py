from typing import Dict, List

from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    InvalidIDError,
    ValidationError,
    WarehouseNotFoundError,
)
from app.shared.domain.entity import DomainEntity
from app.modules.warehouses.domain.value_objects import WarehouseLocation, WarehouseType


class Warehouse(DomainEntity):
    """Domain entity for warehouses."""

    warehouse_id: int
    location: str
    warehouse_type: str
    capacity_sqm: float | None
    is_active: bool
    manager_id: str | None
    timezone: str

    def __init__(
        self,
        warehouse_id: int,
        location: str,
        warehouse_type: str = "ambient",
        capacity_sqm: float | None = None,
        is_active: bool = True,
        manager_id: str | None = None,
        timezone: str = "UTC",
    ) -> None:
        self._validate_warehouse_id(warehouse_id)
        self._validate_location(location)
        warehouse_type_obj = WarehouseType(warehouse_type)
        if capacity_sqm is not None and capacity_sqm < 0:
            raise ValidationError("capacity_sqm must be non-negative")

        self.warehouse_id = warehouse_id
        self.location = location
        self.warehouse_type = warehouse_type_obj.value
        self.capacity_sqm = capacity_sqm
        self.is_active = is_active
        self.manager_id = manager_id
        self.timezone = timezone or "UTC"


    @staticmethod
    def _validate_warehouse_id(warehouse_id: int) -> None:
        # 0 is a valid sentinel meaning "pending DB assignment" (TASK-001).
        # Negative values are still invalid.
        if not isinstance(warehouse_id, int) or warehouse_id < 0:
            raise InvalidIDError("warehouse_id must be a non-negative integer (0 = pending DB assignment)")

    @staticmethod
    def _validate_location(location: str) -> None:
        WarehouseLocation(location)

    def get_inventory_summary(self) -> dict:
        return {
            "warehouse_id": self.warehouse_id,
            "location": self.location,
            "total_products": 0,
            "total_items": 0,
        }

    def update_location(self, new_location: str) -> None:
        self.location = WarehouseLocation(new_location).value

    def location_metadata(self) -> dict:
        return {
            "warehouse_id": self.warehouse_id,
            "location": self.location,
            "owns_inventory_quantity": False,
        }

    @property
    def identity(self) -> int:
        return self.warehouse_id

    def __str__(self) -> str:
        return (
            f"Warehouse(id={self.warehouse_id}, location='{self.location}')"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Warehouse):
            return False
        return self.warehouse_id == other.warehouse_id

    def __hash__(self) -> int:
        return hash(self.warehouse_id)


class WarehouseManager:
    """Manager class for warehouse collections."""

    def __init__(self) -> None:
        self._warehouses: Dict[int, Warehouse] = {}

    def add_warehouse(self, warehouse: Warehouse) -> None:
        if warehouse.warehouse_id in self._warehouses:
            raise EntityAlreadyExistsError(
                f"Warehouse {warehouse.warehouse_id} already exists"
            )
        self._warehouses[warehouse.warehouse_id] = warehouse

    def get_warehouse(self, warehouse_id: int) -> Warehouse:
        warehouse = self._warehouses.get(warehouse_id)
        if warehouse is None:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found"
            )
        return warehouse

    def remove_warehouse(self, warehouse_id: int) -> None:
        if warehouse_id not in self._warehouses:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found"
            )
        del self._warehouses[warehouse_id]

    def get_all_warehouses(self) -> List[Warehouse]:
        return list(self._warehouses.values())

    def find_warehouses_with_product(self, product_id: int) -> List[Warehouse]:
        return []

    def get_total_product_quantity(self, product_id: int) -> int:
        return 0

    def __len__(self) -> int:
        return len(self._warehouses)

    def __str__(self) -> str:
        return f"WarehouseManager(warehouses={len(self)})"

    def __repr__(self) -> str:
        return self.__str__()
