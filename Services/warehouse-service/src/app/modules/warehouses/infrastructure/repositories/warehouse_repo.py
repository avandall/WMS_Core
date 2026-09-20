from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.domain.business_exceptions import (
    ValidationError,
)
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.shared.core.transaction import TransactionalRepository
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo
from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel


class WarehouseRepo(TransactionalRepository, IWarehouseRepo):
    """PostgreSQL-backed repository for warehouses and their inventory.

    TASK-001: ID assignment is fully delegated to the PostgreSQL BIGSERIAL
    sequence (autoincrement=True on WarehouseModel.warehouse_id).
    The former _sync_id_generator / IDGenerator approach has been removed.

    Insert path:
      When warehouse.warehouse_id == 0 (sentinel), the primary-key column is
      omitted from the INSERT so the DB sequence assigns the next value.
      After session.flush() the ORM model carries the generated ID, which is
      written back to warehouse.warehouse_id before returning.
    """

    def __init__(self, session: Session):
        super().__init__(session)

    def create_warehouse(self, warehouse: Warehouse) -> None:
        if warehouse.warehouse_id == 0:
            # Sentinel: let the DB sequence assign the ID.
            model = WarehouseModel(location=warehouse.location)
        else:
            model = WarehouseModel(
                warehouse_id=warehouse.warehouse_id, location=warehouse.location
            )
        self.session.add(model)
        # Flush so the DB sequence assigns the primary key, then write it back.
        self.session.flush()
        warehouse.warehouse_id = model.warehouse_id
        self._commit_if_auto()

    def save(self, warehouse: Warehouse) -> None:
        existing = self.session.get(WarehouseModel, warehouse.warehouse_id)
        if existing:
            existing.location = warehouse.location
        else:
            self.create_warehouse(warehouse)
            existing = self.session.get(WarehouseModel, warehouse.warehouse_id)

        self._commit_if_auto()

    def get(self, warehouse_id: int) -> Optional[Warehouse]:
        model = self.session.get(WarehouseModel, warehouse_id)
        if not model:
            return None
        return self._to_domain(model)

    def get_all(self) -> Dict[int, Warehouse]:
        rows = self.session.execute(select(WarehouseModel)).scalars().all()
        return {row.warehouse_id: self._to_domain(row) for row in rows}

    def location_exists(self, location: str, *, excluding_warehouse_id: int | None = None) -> bool:
        stmt = select(WarehouseModel).where(WarehouseModel.location == location)
        if excluding_warehouse_id is not None:
            stmt = stmt.where(WarehouseModel.warehouse_id != excluding_warehouse_id)
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def delete(self, warehouse_id: int) -> None:
        model = self.session.get(WarehouseModel, warehouse_id)
        if model:
            try:
                self.session.delete(model)
                self._commit_if_auto()
            except Exception as exc:
                # Most commonly: FK references from historical documents.
                raise ValidationError(
                    f"Cannot delete warehouse {warehouse_id}: it is referenced by existing documents"
                ) from exc

    def _to_domain(self, model: WarehouseModel) -> Warehouse:
        return Warehouse(
            warehouse_id=model.warehouse_id,
            location=model.location,
        )
