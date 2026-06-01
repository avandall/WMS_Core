from __future__ import annotations

from typing import List, Optional

from app.shared.core.logging import get_logger
from app.modules.positions.domain.entities.position import Position
from app.modules.positions.domain.interfaces.position_repo import IPositionRepo

logger = get_logger(__name__)


class PositionService:
    """Service for creating and querying warehouse positions (bin locations)."""

    def __init__(
        self,
        position_repo: IPositionRepo,
        session=None,
    ):
        self.position_repo = position_repo
        self.session = session

    def ensure_defaults(self, warehouse_id: int) -> None:
        self.position_repo.ensure_default_positions(warehouse_id)
        self._commit_if_needed()

    def create_position(
        self,
        *,
        warehouse_id: int,
        code: str,
        type: str = "STORAGE",
        description: Optional[str] = None,
        capacity: Optional[int] = None,
        zone: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Position:
        self.position_repo.ensure_default_positions(warehouse_id)
        position = self.position_repo.create_position(
            warehouse_id=warehouse_id,
            code=code,
            type=type,
            description=description,
        )
        self._commit_if_needed()
        logger.info(
            f"Position created: warehouse_id={warehouse_id} code={position.code} type={position.type}"
        )
        return position

    def list_positions(
        self, warehouse_id: int, *, include_inactive: bool = False
    ) -> List[Position]:
        self.position_repo.ensure_default_positions(warehouse_id)
        return self.position_repo.list_positions(
            warehouse_id, include_inactive=include_inactive
        )

    def get_position(self, warehouse_id: int, code: str) -> Position:
        self.position_repo.ensure_default_positions(warehouse_id)
        return self.position_repo.get_position(warehouse_id, code)

    def _commit_if_needed(self) -> None:
        if self.session is not None:
            self.session.commit()
