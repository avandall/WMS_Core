from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.modules.positions.domain.entities.position import Position


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
    def get_position_model(self, warehouse_id: int, code: str):
        """Internal helper for services needing DB identity (position id)."""
        pass


# Alias for backward compatibility
PositionRepo = IPositionRepo
