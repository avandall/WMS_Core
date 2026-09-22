from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.documents.domain.entities.cycle_count import (
    CycleCountItem,
    CycleCountSheet,
    CycleCountStatus,
)
from app.modules.documents.infrastructure.models.cycle_count_sheet import (
    CycleCountSheetModel,
)
from app.shared.core.transaction import TransactionalRepository


class CycleCountRepository(TransactionalRepository):
    """PostgreSQL-backed repository for Cycle Count Sheets and audit items."""

    def __init__(self, session: Session, auto_commit: bool = True):
        super().__init__(session, auto_commit=auto_commit)

    def save(self, sheet: CycleCountSheet) -> None:
        items_data = [
            {
                "item_id": item.item_id,
                "product_id": item.product_id,
                "location_id": item.location_id,
                "system_qty": item.system_qty,
                "counted_qty": item.counted_qty,
                "lot_number": item.lot_number,
                "unit_cost": item.unit_cost,
            }
            for item in sheet.items
        ]

        status_val = (
            sheet.status.value
            if isinstance(sheet.status, CycleCountStatus)
            else str(sheet.status)
        )

        model = self.session.get(CycleCountSheetModel, sheet.cycle_count_id)
        if model is None:
            model = CycleCountSheetModel(
                cycle_count_id=sheet.cycle_count_id,
                warehouse_id=sheet.warehouse_id,
                title=sheet.title,
                assigned_to=sheet.assigned_to,
                status=status_val,
                discrepancy_qty_threshold=sheet.discrepancy_qty_threshold,
                discrepancy_value_threshold=sheet.discrepancy_value_threshold,
                created_by=sheet.created_by,
                note=sheet.note,
                submitted_at=sheet.submitted_at,
                approved_by=sheet.approved_by,
                approved_at=sheet.approved_at,
                rejection_reason=sheet.rejection_reason,
                items=items_data,
                created_at=sheet.created_at,
            )
            self.session.add(model)
        else:
            model.warehouse_id = sheet.warehouse_id
            model.title = sheet.title
            model.assigned_to = sheet.assigned_to
            model.status = status_val
            model.discrepancy_qty_threshold = sheet.discrepancy_qty_threshold
            model.discrepancy_value_threshold = sheet.discrepancy_value_threshold
            model.created_by = sheet.created_by
            model.note = sheet.note
            model.submitted_at = sheet.submitted_at
            model.approved_by = sheet.approved_by
            model.approved_at = sheet.approved_at
            model.rejection_reason = sheet.rejection_reason
            model.items = items_data
            model.created_at = sheet.created_at

        self._commit_if_auto()

    def get(self, cycle_count_id: str) -> Optional[CycleCountSheet]:
        model = self.session.get(CycleCountSheetModel, cycle_count_id)
        if model is None:
            return None

        items: List[CycleCountItem] = []
        for it in model.items or []:
            items.append(
                CycleCountItem(
                    item_id=it["item_id"],
                    product_id=it["product_id"],
                    location_id=it["location_id"],
                    system_qty=it["system_qty"],
                    counted_qty=it.get("counted_qty"),
                    lot_number=it.get("lot_number", ""),
                    unit_cost=it.get("unit_cost", 0.0),
                )
            )

        sheet = CycleCountSheet(
            cycle_count_id=model.cycle_count_id,
            warehouse_id=model.warehouse_id,
            title=model.title,
            assigned_to=model.assigned_to,
            discrepancy_qty_threshold=model.discrepancy_qty_threshold,
            discrepancy_value_threshold=model.discrepancy_value_threshold,
            items=items,
            created_by=model.created_by,
            note=model.note,
        )
        sheet.status = CycleCountStatus(model.status)
        sheet.created_at = model.created_at
        sheet.submitted_at = model.submitted_at
        sheet.approved_by = model.approved_by
        sheet.approved_at = model.approved_at
        sheet.rejection_reason = model.rejection_reason
        return sheet

    def exists(self, cycle_count_id: str) -> bool:
        return self.session.get(CycleCountSheetModel, cycle_count_id) is not None

    def delete(self, cycle_count_id: str) -> None:
        model = self.session.get(CycleCountSheetModel, cycle_count_id)
        if model:
            self.session.delete(model)
            self._commit_if_auto()
