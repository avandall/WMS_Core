from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.modules.documents.infrastructure.repositories.cycle_count_repo import (
        CycleCountRepository,
    )

from app.modules.documents.domain.entities.cycle_count import (
    BlindCountItem,
    CycleCountItem,
    CycleCountSheet,
    CycleCountStatus,
)
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ValidationError,
)


@dataclass(slots=True)
class CycleCountAdjustmentPayload:
    """Payload representing approved inventory adjustment to be processed by inventory service."""

    cycle_count_id: str
    warehouse_id: int
    product_id: int
    location_id: str
    lot_number: str
    system_qty: int
    counted_qty: int
    discrepancy_qty: int
    reason: str


class CycleCountService:
    """Application service for managing Blind Cycle Counting workflows and Discrepancy Approval backed by DB persistence."""

    def __init__(
        self,
        repo: Optional[CycleCountRepository] = None,
        session: Optional[Session] = None,
    ) -> None:
        from app.modules.documents.infrastructure.repositories.cycle_count_repo import (
            CycleCountRepository,
        )

        if repo is not None:
            self._repo = repo
        elif session is not None:
            self._repo = CycleCountRepository(session, auto_commit=True)
        else:
            try:
                from app.shared.core.database import SessionLocal
                session_obj = SessionLocal()
                from sqlalchemy import text
                session_obj.execute(text("SELECT 1"))
                self._repo = CycleCountRepository(session_obj, auto_commit=True)
            except Exception:
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker
                from app.shared.core.database import Base, import_all_models
                import_all_models()
                engine = create_engine("sqlite:///:memory:", future=True)
                Base.metadata.create_all(bind=engine)
                fallback = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
                self._repo = CycleCountRepository(fallback, auto_commit=True)

        self._identity_map: Dict[str, CycleCountSheet] = {}

    def create_cycle_count_sheet(
        self,
        cycle_count_id: str,
        warehouse_id: int,
        title: str,
        items: List[CycleCountItem],
        assigned_to: Optional[str] = None,
        discrepancy_qty_threshold: int = 0,
        discrepancy_value_threshold: float = 0.0,
        created_by: str = "system",
        note: Optional[str] = None,
    ) -> CycleCountSheet:
        """Initializes a new cycle count sheet and persists to DB."""
        if not items:
            raise ValidationError("Cannot create cycle count sheet with empty items list")
        if cycle_count_id in self._identity_map or self._repo.exists(cycle_count_id):
            raise EntityAlreadyExistsError(f"Cycle count sheet '{cycle_count_id}' already exists")

        sheet = CycleCountSheet(
            cycle_count_id=cycle_count_id,
            warehouse_id=warehouse_id,
            title=title,
            assigned_to=assigned_to,
            discrepancy_qty_threshold=discrepancy_qty_threshold,
            discrepancy_value_threshold=discrepancy_value_threshold,
            items=items,
            created_by=created_by,
            note=note,
        )
        self._identity_map[cycle_count_id] = sheet
        self._repo.save(sheet)
        return sheet

    def get_cycle_count_sheet(self, cycle_count_id: str) -> CycleCountSheet:
        """Retrieves cycle count sheet by ID from identity map or DB."""
        if cycle_count_id in self._identity_map:
            return self._identity_map[cycle_count_id]

        sheet = self._repo.get(cycle_count_id)
        if sheet is None:
            raise EntityNotFoundError(f"Cycle count sheet '{cycle_count_id}' not found")

        self._identity_map[cycle_count_id] = sheet
        return sheet

    def get_blind_count_sheet(self, cycle_count_id: str) -> List[BlindCountItem]:
        """Retrieves blind count view for staff (system_qty strictly hidden)."""
        sheet = self.get_cycle_count_sheet(cycle_count_id)
        return sheet.get_blind_sheet()

    def start_cycle_count(
        self, cycle_count_id: str, assigned_to: Optional[str] = None
    ) -> CycleCountSheet:
        """Assigns counter and transitions sheet to IN_PROGRESS."""
        sheet = self.get_cycle_count_sheet(cycle_count_id)
        if assigned_to:
            sheet.assign_counter(assigned_to)
        sheet.start_counting()
        self._repo.save(sheet)
        return sheet

    def record_counts(self, cycle_count_id: str, counts: Dict[str, int]) -> CycleCountSheet:
        """Records physical counts for items in sheet."""
        sheet = self.get_cycle_count_sheet(cycle_count_id)
        sheet.record_counts(counts)
        self._repo.save(sheet)
        return sheet

    def submit_counts(self, cycle_count_id: str) -> CycleCountSheet:
        """Submits physical counts, calculates discrepancies, and evaluates threshold rules."""
        sheet = self.get_cycle_count_sheet(cycle_count_id)
        sheet.submit_counts()
        self._repo.save(sheet)
        return sheet

    def approve_cycle_count(
        self, cycle_count_id: str, supervisor_id: str, note: Optional[str] = None
    ) -> CycleCountSheet:
        """Supervisor approves discrepancies exceeding threshold."""
        sheet = self.get_cycle_count_sheet(cycle_count_id)
        sheet.approve_by_supervisor(supervisor_id=supervisor_id, note=note)
        self._repo.save(sheet)
        return sheet

    def reject_cycle_count(
        self, cycle_count_id: str, supervisor_id: str, reason: str
    ) -> CycleCountSheet:
        """Supervisor rejects discrepancies exceeding threshold."""
        sheet = self.get_cycle_count_sheet(cycle_count_id)
        sheet.reject_by_supervisor(supervisor_id=supervisor_id, reason=reason)
        self._repo.save(sheet)
        return sheet

    def generate_inventory_adjustments(
        self, cycle_count_id: str
    ) -> List[CycleCountAdjustmentPayload]:
        """Generates inventory adjustment payloads ONLY when sheet status is APPROVED.

        Discrepant items (counted != system) will generate adjustment payloads.
        Raises BusinessRuleViolationError if sheet is not APPROVED.
        """
        sheet = self.get_cycle_count_sheet(cycle_count_id)
        if sheet.status != CycleCountStatus.APPROVED:
            raise BusinessRuleViolationError(
                f"Cannot generate inventory adjustments for cycle count sheet in status '{sheet.status.value}'. Must be APPROVED."
            )

        adjustments: List[CycleCountAdjustmentPayload] = []
        for item in sheet.items:
            if item.discrepancy_qty != 0 and item.counted_qty is not None:
                adj = CycleCountAdjustmentPayload(
                    cycle_count_id=sheet.cycle_count_id,
                    warehouse_id=sheet.warehouse_id,
                    product_id=item.product_id,
                    location_id=item.location_id,
                    lot_number=item.lot_number,
                    system_qty=item.system_qty,
                    counted_qty=item.counted_qty,
                    discrepancy_qty=item.discrepancy_qty,
                    reason=(
                        f"Blind Cycle Count '{sheet.cycle_count_id}' discrepancy adjustment: "
                        f"System={item.system_qty}, Counted={item.counted_qty}, Discrepancy={item.discrepancy_qty}"
                    ),
                )
                adjustments.append(adj)

        return adjustments
