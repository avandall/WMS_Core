from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.domain.entities.position import Position, PositionInventoryItem


class IPositionRepo(ABC):
    @abstractmethod
    def ensure_default_positions(self, warehouse_id: int) -> None:
        pass

    @abstractmethod
    def create_position(
        self,
        *,
        warehouse_id: int,
        code: str,
        type: str = "STORAGE",
        description: Optional[str] = None,
    ) -> "Position":
        pass

    @abstractmethod
    def list_positions(
        self, warehouse_id: int, *, include_inactive: bool = False
    ) -> List["Position"]:
        pass

    @abstractmethod
    def get_position(self, warehouse_id: int, code: str) -> "Position":
        pass

    @abstractmethod
    def list_position_inventory(
        self, warehouse_id: int, code: str
    ) -> List["PositionInventoryItem"]:
        pass

    @abstractmethod
    def get_position_model(self, warehouse_id: int, code: str):
        """Internal helper for services needing DB identity (position id)."""
        pass

    @abstractmethod
    def get_total_quantity_for_product(self, warehouse_id: int, product_id: int) -> int:
        pass

    @abstractmethod
    def adjust_position_stock(
        self, *, position_id: int, product_id: int, delta: int
    ) -> None:
        pass

    @abstractmethod
    def allocate_and_remove(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        preferred_position_codes: Optional[List[str]] = None,
    ):
        pass
