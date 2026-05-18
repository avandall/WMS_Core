from __future__ import annotations

from typing import Dict, List, Optional

from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    InsufficientStockError,
    InvalidIDError,
    InvalidQuantityError,
    ValidationError,
    WarehouseNotFoundError,
)
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.modules.products.domain.entities.product import Product
from app.shared.domain.entity import DomainEntity


class Warehouse(DomainEntity):
    """Domain entity for warehouses."""

    def __init__(
        self,
        warehouse_id: int,
        location: str,
        inventory: Optional[List[InventoryItem]] = None,
    ) -> None:
        self._validate_warehouse_id(warehouse_id)
        self._validate_location(location)

        self.warehouse_id = warehouse_id
        self.location = location
        self.inventory = inventory or []

    @staticmethod
    def _validate_warehouse_id(warehouse_id: int) -> None:
        if not isinstance(warehouse_id, int) or warehouse_id <= 0:
            raise InvalidIDError("warehouse_id must be a positive integer")

    @staticmethod
    def _validate_location(location: str) -> None:
        if not isinstance(location, str) or not location.strip():
            raise ValidationError("location must be a non-empty string")
        if len(location) > 200:
            raise ValidationError("location must be at most 200 characters")

    def add_product(self, product_id: int, quantity: int) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("quantity must be a positive integer")

        for item in self.inventory:
            if item.product_id == product_id:
                item.add_quantity(quantity)
                return

        self.inventory.append(InventoryItem(product_id, quantity))

    def remove_product(self, product_id: int, quantity: int) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("quantity must be a positive integer")

        for index, item in enumerate(self.inventory):
            if item.product_id == product_id:
                if item.quantity < quantity:
                    raise InsufficientStockError(
                        f"Insufficient stock: available={item.quantity}, requested={quantity}"
                    )
                item.remove_quantity(quantity)
                if item.is_empty():
                    self.inventory.pop(index)
                return

        raise EntityNotFoundError(
            f"Product {product_id} not found in warehouse {self.warehouse_id}"
        )

    def get_product_quantity(self, product_id: int) -> int:
        for item in self.inventory:
            if item.product_id == product_id:
                return item.quantity
        return 0

    def has_product(self, product_id: int) -> bool:
        return any(item.product_id == product_id for item in self.inventory)

    def get_inventory_value(self, products: Dict[int, Product]) -> float:
        total_value = 0.0
        for item in self.inventory:
            product = products.get(item.product_id)
            if product is not None:
                total_value += product.calculate_total_value(item.quantity)
        return total_value

    def get_inventory_summary(self) -> dict:
        return {
            "warehouse_id": self.warehouse_id,
            "location": self.location,
            "total_products": len(self.inventory),
            "total_items": sum(item.quantity for item in self.inventory),
        }

    def transfer_product_to(
        self, other_warehouse: "Warehouse", product_id: int, quantity: int
    ) -> None:
        if other_warehouse.warehouse_id == self.warehouse_id:
            raise BusinessRuleViolationError("Cannot transfer to the same warehouse")

        self.remove_product(product_id, quantity)
        other_warehouse.add_product(product_id, quantity)

    def update_location(self, new_location: str) -> None:
        self._validate_location(new_location)
        self.location = new_location

    @property
    def identity(self) -> int:
        return self.warehouse_id

    def __str__(self) -> str:
        return (
            f"Warehouse(id={self.warehouse_id}, location='{self.location}', products={len(self.inventory)})"
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
        return [
            warehouse
            for warehouse in self._warehouses.values()
            if warehouse.has_product(product_id)
        ]

    def get_total_product_quantity(self, product_id: int) -> int:
        return sum(
            warehouse.get_product_quantity(product_id)
            for warehouse in self._warehouses.values()
        )

    def __len__(self) -> int:
        return len(self._warehouses)

    def __str__(self) -> str:
        return f"WarehouseManager(warehouses={len(self)})"

    def __repr__(self) -> str:
        return self.__str__()
