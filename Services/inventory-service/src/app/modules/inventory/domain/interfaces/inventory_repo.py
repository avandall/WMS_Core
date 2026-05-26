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

    @abstractmethod
    def adjust_quantity(self, product_id: int, quantity_delta: int) -> None:
        pass

    @abstractmethod
    def adjust_warehouse_quantity(
        self, product_id: int, warehouse_id: int, quantity_delta: int
    ) -> None:
        pass

    @abstractmethod
    def has_movement_event(self, event_id: str) -> bool:
        pass

    @abstractmethod
    def record_movement_event(
        self,
        *,
        event_id: str,
        movement_type: str,
        document_id: int | None,
        payload: dict[str, Any],
    ) -> None:
        pass


# Alias for backward compatibility
InventoryRepo = IInventoryRepo
