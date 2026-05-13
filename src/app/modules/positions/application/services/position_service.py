from __future__ import annotations

from typing import List, Optional

from app.shared.core.logging import get_logger
from app.modules.positions.domain.entities.position import Position, PositionInventoryItem
from app.modules.audit.domain.interfaces.audit_event_repo import IAuditEventRepo
from app.modules.positions.domain.interfaces.position_repo import IPositionRepo

logger = get_logger(__name__)


class PositionService:
    """Service for creating and querying warehouse positions (bin locations)."""

    def __init__(
        self,
        position_repo: IPositionRepo,
        audit_event_repo: Optional[IAuditEventRepo] = None,
    ):
        self.position_repo = position_repo
        self.audit_event_repo = audit_event_repo

    def ensure_defaults(self, warehouse_id: int) -> None:
        self.position_repo.ensure_default_positions(warehouse_id)

    async def create_position(
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
            capacity=capacity,
            zone=zone,
        )
        if self.audit_event_repo:
            self.audit_event_repo.create_event(
                action="POSITION_CREATED",
                entity_type="position",
                entity_id=f"{warehouse_id}:{position.code}",
                warehouse_id=warehouse_id,
                payload={"code": position.code, "type": position.type},
                user_id=user_id,
            )
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

    def list_position_inventory(
        self, warehouse_id: int, code: str
    ) -> List[PositionInventoryItem]:
        self.position_repo.ensure_default_positions(warehouse_id)
        return self.position_repo.list_position_inventory(warehouse_id, code)

