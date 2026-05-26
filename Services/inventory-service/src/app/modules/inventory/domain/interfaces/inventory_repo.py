from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from app.modules.inventory.domain.entities.inventory import InventoryItem


class IInventoryRepo(ABC):
    @abstractmethod
    def save(self, inventory_item: "InventoryItem") -> None:
        pass

    @abstractmethod
    def add_quantity(self, product_id: int, quantity: int) -> None:
        pass

    @abstractmethod
    def get_quantity(self, product_id: int) -> int:
        pass

    @abstractmethod
    def get_all(self) -> List["InventoryItem"]:
        pass

    @abstractmethod
    def delete(self, product_id: int) -> None:
        pass

    @abstractmethod
    def remove_quantity(self, product_id: int, quantity: int) -> None:
        pass

    @abstractmethod
    def get_inventory_by_warehouse_rows(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_warehouse_distribution(self, product_id: int) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_warehouse_summary(self) -> dict[int, dict[str, Any]]:
        pass


# Alias for backward compatibility
InventoryRepo = IInventoryRepo
