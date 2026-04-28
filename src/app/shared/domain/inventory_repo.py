from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.modules.inventorys.domain.entities.inventory import InventoryItem


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
