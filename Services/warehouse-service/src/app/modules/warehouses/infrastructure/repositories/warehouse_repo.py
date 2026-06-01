from typing import Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.domain.business_exceptions import (
    ValidationError,
)
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.shared.utils.infrastructure.id_generator import IDGenerator
from app.shared.core.transaction import TransactionalRepository
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo
from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel


class WarehouseRepo(TransactionalRepository, IWarehouseRepo):
    """PostgreSQL-backed repository for warehouses and their inventory."""

    def __init__(self, session: Session):
        super().__init__(session)
        self._sync_id_generator()

    def _sync_id_generator(self) -> None:
        max_id = self.session.execute(
            select(func.max(WarehouseModel.warehouse_id))
        ).scalar()
        # Handle Mock objects in testing
        if hasattr(max_id, '__class__') and max_id.__class__.__name__ == 'Mock':
            start_id = 1
        else:
            start_id = (max_id or 0) + 1
        IDGenerator.reset_generator("warehouse", start_id)

    def create_warehouse(self, warehouse: Warehouse) -> None:
        model = WarehouseModel(
            warehouse_id=warehouse.warehouse_id, location=warehouse.location
        )
        self.session.add(model)
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
