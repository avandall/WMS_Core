from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from app.domain.entities.inventory import InventoryItem
    from app.domain.entities.warehouse import Warehouse


class IWarehouseRepo(ABC):
    @abstractmethod
    def create_warehouse(self, warehouse: "Warehouse") -> None:
        pass

    @abstractmethod
    def save(self, warehouse: "Warehouse") -> None:
        pass

    @abstractmethod
    def get(self, warehouse_id: int) -> Optional["Warehouse"]:
        pass

    @abstractmethod
    def get_all(self) -> Dict[int, "Warehouse"]:
        pass

    @abstractmethod
    def delete(self, warehouse_id: int) -> None:
        pass

    @abstractmethod
    def get_warehouse_inventory(self, warehouse_id: int) -> List["InventoryItem"]:
        pass

    @abstractmethod
    def add_product_to_warehouse(
        self, warehouse_id: int, product_id: int, quantity: int
    ) -> None:
        pass

    @abstractmethod
    def remove_product_from_warehouse(
        self, warehouse_id: int, product_id: int, quantity: int
    ) -> None:
        pass
