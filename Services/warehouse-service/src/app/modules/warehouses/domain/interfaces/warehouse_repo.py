from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from app.modules.warehouses.domain.entities.warehouse import Warehouse


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
    def location_exists(self, location: str, *, excluding_warehouse_id: int | None = None) -> bool:
        pass


# Alias for backward compatibility
WarehouseRepo = IWarehouseRepo
