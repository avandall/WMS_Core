from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.transaction import TransactionalRepository
from app.domain.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    InsufficientStockError,
    ValidationError,
    WarehouseNotFoundError,
)
from app.domain.entities.position import Position, PositionInventoryItem
from app.infrastructure.persistence.models import (
    PositionInventoryModel,
    PositionModel,
    WarehouseModel,
)

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
    """Repository for warehouse positions and position-level inventory."""

    def __init__(self, session: Session):
        super().__init__(session)

    def ensure_default_positions(self, warehouse_id: int) -> None:
        warehouse = self.session.get(WarehouseModel, warehouse_id)
        if not warehouse:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found")

        existing_codes = set()
        for row in self.session.execute(
            select(PositionModel).where(PositionModel.warehouse_id == warehouse_id)
        ).scalars().all():
            existing_codes.add(row.code)
        # Session uses `autoflush=False`; include pending objects as well.
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
            logger.info(
                f"Created {created} default positions for warehouse {warehouse_id}"
            )
            # Flush so subsequent queries can see the rows even with `autoflush=False`.
            self.session.flush()
            self._commit_if_auto()

    def create_position(
        self,
        *,
        warehouse_id: int,
        code: str,
        type: str = "STORAGE",
        description: Optional[str] = None,
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
        rows = self.session.execute(stmt.order_by(PositionModel.code.asc())).scalars().all()
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

    def list_position_inventory(
        self, warehouse_id: int, code: str
    ) -> List[PositionInventoryItem]:
        pos = self.get_position_model(warehouse_id, code)
        rows = self.session.execute(
            select(PositionInventoryModel).where(PositionInventoryModel.position_id == pos.id)
        ).scalars().all()
        return [
            PositionInventoryItem(
                warehouse_id=warehouse_id,
                position_code=pos.code,
                product_id=row.product_id,
                quantity=row.quantity,
            )
            for row in rows
            if row.quantity > 0
        ]

    def get_total_quantity_for_product(self, warehouse_id: int, product_id: int) -> int:
        total = (
            self.session.execute(
                select(func.coalesce(func.sum(PositionInventoryModel.quantity), 0))
                .select_from(PositionInventoryModel)
                .join(PositionModel, PositionModel.id == PositionInventoryModel.position_id)
                .where(
                    PositionModel.warehouse_id == warehouse_id,
                    PositionInventoryModel.product_id == product_id,
                )
            ).scalar_one()
            or 0
        )
        return int(total)

    def adjust_position_stock(
        self, *, position_id: int, product_id: int, delta: int
    ) -> None:
        if delta == 0:
            return
        if delta < 0:
            self._remove_from_position(position_id=position_id, product_id=product_id, quantity=-delta)
        else:
            self._add_to_position(position_id=position_id, product_id=product_id, quantity=delta)

    def allocate_and_remove(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        preferred_position_codes: Optional[List[str]] = None,
    ) -> List[Tuple[str, int]]:
        """
        Remove stock from a warehouse by allocating across multiple positions.

        Returns list of (position_code, removed_qty) allocations.
        """
        if quantity <= 0:
            raise ValidationError("quantity must be positive")

        preferred = [_normalize_code(c) for c in (preferred_position_codes or [])]
        pos_rows = self.session.execute(
            select(PositionModel)
            .where(PositionModel.warehouse_id == warehouse_id, PositionModel.is_active == 1)
            .order_by(PositionModel.code.asc())
        ).scalars().all()

        by_code = {p.code: p for p in pos_rows}
        ordered: list[PositionModel] = []
        for code in preferred:
            if code in by_code:
                ordered.append(by_code.pop(code))
        # then any remaining, stable order
        ordered.extend(sorted(by_code.values(), key=lambda p: p.code))

        remaining = quantity
        allocations: list[Tuple[str, int]] = []
        for pos in ordered:
            if remaining <= 0:
                break
            available = self._get_position_product_quantity(position_id=pos.id, product_id=product_id)
            if available <= 0:
                continue
            take = min(available, remaining)
            self._remove_from_position(position_id=pos.id, product_id=product_id, quantity=take)
            allocations.append((pos.code, take))
            remaining -= take

        if remaining > 0:
            raise InsufficientStockError(
                f"Insufficient position stock for product {product_id} in warehouse {warehouse_id}: missing {remaining}"
            )

        return allocations

    def _get_pending_row(
        self, position_id: int, product_id: int
    ) -> Optional[PositionInventoryModel]:
        for obj in list(self.session.new) + list(self.session.dirty):
            if not isinstance(obj, PositionInventoryModel):
                continue
            if obj.position_id == position_id and obj.product_id == product_id:
                return obj
        return None

    def _get_position_product_quantity(self, *, position_id: int, product_id: int) -> int:
        pending = self._get_pending_row(position_id, product_id)
        if pending is not None:
            return int(pending.quantity)

        row = self.session.execute(
            select(PositionInventoryModel).where(
                PositionInventoryModel.position_id == position_id,
                PositionInventoryModel.product_id == product_id,
            )
        ).scalar_one_or_none()
        return int(row.quantity) if row else 0

    def _add_to_position(self, *, position_id: int, product_id: int, quantity: int) -> None:
        if quantity <= 0:
            raise ValidationError("quantity must be positive")

        pending = self._get_pending_row(position_id, product_id)
        if pending is not None:
            pending.quantity += quantity
            pending.updated_at = func.now()
            self._commit_if_auto()
            return

        row = self.session.execute(
            select(PositionInventoryModel).where(
                PositionInventoryModel.position_id == position_id,
                PositionInventoryModel.product_id == product_id,
            )
        ).scalar_one_or_none()

        if row:
            row.quantity += quantity
            row.updated_at = func.now()
        else:
            self.session.add(
                PositionInventoryModel(
                    position_id=position_id, product_id=product_id, quantity=quantity
                )
            )
        self._commit_if_auto()

    def _remove_from_position(
        self, *, position_id: int, product_id: int, quantity: int
    ) -> None:
        if quantity <= 0:
            raise ValidationError("quantity must be positive")

        pending = self._get_pending_row(position_id, product_id)
        if pending is not None:
            if pending.quantity < quantity:
                raise InsufficientStockError(
                    f"Insufficient stock at position {position_id} for product {product_id}"
                )
            pending.quantity -= quantity
            pending.updated_at = func.now()
            if pending.quantity == 0:
                self.session.expunge(pending)
            self._commit_if_auto()
            return

        row = self.session.execute(
            select(PositionInventoryModel).where(
                PositionInventoryModel.position_id == position_id,
                PositionInventoryModel.product_id == product_id,
            )
        ).scalar_one_or_none()
        if not row or row.quantity < quantity:
            raise InsufficientStockError(
                f"Insufficient stock at position {position_id} for product {product_id}"
            )

        row.quantity -= quantity
        row.updated_at = func.now()
        if row.quantity == 0:
            self.session.delete(row)
        self._commit_if_auto()

    @staticmethod
    def _to_domain(model: PositionModel) -> Position:
        return Position(
            id=model.id,
            warehouse_id=model.warehouse_id,
            code=model.code,
            type=model.type,
            description=model.description,
            is_active=bool(model.is_active),
        )
