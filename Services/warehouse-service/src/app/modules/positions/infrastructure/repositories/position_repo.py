from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.core.logging import get_logger
from app.shared.core.transaction import TransactionalRepository
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    WarehouseNotFoundError,
)
from app.modules.positions.domain.entities.position import Position
from app.modules.positions.infrastructure.models.position import PositionModel
from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel

logger = get_logger(__name__)


DEFAULT_POSITIONS: list[tuple[str, str, str | None]] = [
    ("RECEIVING", "RECEIVING", "Inbound / receiving area"),
    ("STORAGE", "STORAGE", "Main storage"),
    ("SHIPPING", "SHIPPING", "Outbound / shipping area"),
    ("UNASSIGNED", "SYSTEM", "System bucket for un-positioned stock"),
]


def _normalize_code(code: str) -> str:
    return code.strip().upper()


class PositionRepo(TransactionalRepository):
    """Repository for warehouse positions and bin metadata."""

    def __init__(self, session: Session):
        super().__init__(session)

    def ensure_default_positions(self, warehouse_id: int) -> None:
        warehouse = self.session.get(WarehouseModel, warehouse_id)
        if not warehouse:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found")

        existing_codes = {
            row.code
            for row in self.session.execute(
                select(PositionModel).where(PositionModel.warehouse_id == warehouse_id)
            ).scalars().all()
        }
        for obj in list(self.session.new) + list(self.session.dirty):
            if isinstance(obj, PositionModel) and obj.warehouse_id == warehouse_id:
                existing_codes.add(obj.code)

        created = 0
        for code, pos_type, desc in DEFAULT_POSITIONS:
            if code in existing_codes:
                continue
            self.session.add(
                PositionModel(
                    warehouse_id=warehouse_id,
                    code=code,
                    type=pos_type,
                    description=desc,
                    is_active=1,
                )
            )
            created += 1

        if created:
            logger.info("Created %s default positions for warehouse %s", created, warehouse_id)
            self.session.flush()
            self._commit_if_auto()

    def create_position(
        self,
        *,
        warehouse_id: int,
        code: str,
        type: str = "STORAGE",
        description: Optional[str] = None,
        aisle: Optional[str] = None,
        bay: Optional[str] = None,
        level: Optional[str] = None,
        bin: Optional[str] = None,
        max_weight_kg: Optional[float] = None,
        temperature_zone: str = "ambient",
        pick_sequence: int = 0,
        hazmat_class: Optional[str] = None,
    ) -> Position:
        warehouse = self.session.get(WarehouseModel, warehouse_id)
        if not warehouse:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found")

        norm_code = _normalize_code(code)
        existing = self.session.execute(
            select(PositionModel).where(
                PositionModel.warehouse_id == warehouse_id,
                PositionModel.code == norm_code,
            )
        ).scalar_one_or_none()
        if existing:
            raise EntityAlreadyExistsError(
                f"Position {norm_code} already exists in warehouse {warehouse_id}"
            )

        model = PositionModel(
            warehouse_id=warehouse_id,
            code=norm_code,
            type=type.strip().upper(),
            description=description,
            is_active=1,
            aisle=aisle,
            bay=bay,
            level=level,
            bin=bin,
            max_weight_kg=max_weight_kg,
            temperature_zone=temperature_zone,
            pick_sequence=pick_sequence,
            hazmat_class=hazmat_class,
        )
        self.session.add(model)
        self.session.flush()
        self._commit_if_auto()
        return self._to_domain(model)

    def list_positions(
        self, warehouse_id: int, *, include_inactive: bool = False
    ) -> List[Position]:
        stmt = select(PositionModel).where(PositionModel.warehouse_id == warehouse_id)
        if not include_inactive:
            stmt = stmt.where(PositionModel.is_active == 1)
        rows = self.session.execute(
            stmt.order_by(PositionModel.pick_sequence.asc(), PositionModel.code.asc())
        ).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_position(self, warehouse_id: int, code: str) -> Position:
        norm_code = _normalize_code(code)
        model = self.session.execute(
            select(PositionModel).where(
                PositionModel.warehouse_id == warehouse_id,
                PositionModel.code == norm_code,
                PositionModel.is_active == 1,
            )
        ).scalar_one_or_none()
        if not model:
            raise EntityNotFoundError(
                f"Position {norm_code} not found in warehouse {warehouse_id}"
            )
        return self._to_domain(model)

    def get_position_model(self, warehouse_id: int, code: str) -> PositionModel:
        norm_code = _normalize_code(code)
        for obj in list(self.session.new) + list(self.session.dirty):
            if not isinstance(obj, PositionModel):
                continue
            if (
                obj.warehouse_id == warehouse_id
                and obj.code == norm_code
                and obj.is_active == 1
            ):
                return obj
        model = self.session.execute(
            select(PositionModel).where(
                PositionModel.warehouse_id == warehouse_id,
                PositionModel.code == norm_code,
                PositionModel.is_active == 1,
            )
        ).scalar_one_or_none()
        if not model:
            raise EntityNotFoundError(
                f"Position {norm_code} not found in warehouse {warehouse_id}"
            )
        return model

    @staticmethod
    def _to_domain(model: PositionModel) -> Position:
        return Position(
            id=int(model.id) if model.id is not None else None,
            warehouse_id=int(model.warehouse_id),
            code=str(model.code),
            type=str(model.type),
            description=str(model.description) if model.description is not None else None,
            is_active=bool(model.is_active),
            aisle=str(model.aisle) if model.aisle is not None else None,
            bay=str(model.bay) if model.bay is not None else None,
            level=str(model.level) if model.level is not None else None,
            bin=str(model.bin) if model.bin is not None else None,
            max_weight_kg=float(model.max_weight_kg) if model.max_weight_kg is not None else None,
            temperature_zone=str(model.temperature_zone or "ambient"),
            pick_sequence=int(model.pick_sequence) if model.pick_sequence is not None else 0,
            hazmat_class=str(model.hazmat_class) if model.hazmat_class is not None else None,
        )

