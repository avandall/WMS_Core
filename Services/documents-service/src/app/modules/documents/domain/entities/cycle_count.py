from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidDocumentStatusError,
    InvalidIDError,
    InvalidQuantityError,
    ValidationError,
)
from app.shared.domain.entity import DomainEntity


class CycleCountStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COUNT_COMPLETED = "COUNT_COMPLETED"
    PENDING_SUPERVISOR_APPROVAL = "PENDING_SUPERVISOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class DiscrepancyType(str, Enum):
    MATCH = "MATCH"
    SURPLUS = "SURPLUS"  # Real count > system count
    SHORTAGE = "SHORTAGE"  # Real count < system count


@dataclass(slots=True)
class BlindCountItem:
    """View model for counting staff. Excludes system quantities to prevent fraud."""

    item_id: str
    product_id: int
    location_id: str
    lot_number: str = ""
    is_counted: bool = False
    counted_qty: Optional[int] = None


@dataclass(slots=True)
class CycleCountItem:
    """Internal domain item representation with full system audit data."""

    item_id: str
    product_id: int
    location_id: str
    system_qty: int
    counted_qty: Optional[int] = None
    lot_number: str = ""
    unit_cost: float = 0.0

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidIDError("product_id must be positive")
        if self.system_qty < 0:
            raise InvalidQuantityError("system_qty cannot be negative")
        if self.unit_cost < 0:
            raise ValidationError("unit_cost cannot be negative")
        if self.counted_qty is not None and self.counted_qty < 0:
            raise InvalidQuantityError("counted_qty cannot be negative")

    @property
    def is_counted(self) -> bool:
        return self.counted_qty is not None

    @property
    def discrepancy_qty(self) -> int:
        if self.counted_qty is None:
            return 0
        return self.counted_qty - self.system_qty

    @property
    def abs_discrepancy_qty(self) -> int:
        return abs(self.discrepancy_qty)

    @property
    def discrepancy_value(self) -> float:
        return self.discrepancy_qty * self.unit_cost

    @property
    def abs_discrepancy_value(self) -> float:
        return abs(self.discrepancy_value)

    @property
    def discrepancy_type(self) -> DiscrepancyType:
        if self.counted_qty is None or self.discrepancy_qty == 0:
            return DiscrepancyType.MATCH
        return DiscrepancyType.SURPLUS if self.discrepancy_qty > 0 else DiscrepancyType.SHORTAGE

    def record_count(self, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Counted quantity cannot be negative")
        self.counted_qty = quantity

    def to_blind_item(self) -> BlindCountItem:
        """Converts item to blind view model, hiding system_qty."""
        return BlindCountItem(
            item_id=self.item_id,
            product_id=self.product_id,
            location_id=self.location_id,
            lot_number=self.lot_number,
            is_counted=self.is_counted,
            counted_qty=self.counted_qty,
        )


class CycleCountSheet(DomainEntity):
    """Domain entity managing Blind Cycle Counting and Supervisor Approval workflow."""

    def __init__(
        self,
        cycle_count_id: str,
        warehouse_id: int,
        title: str,
        assigned_to: Optional[str] = None,
        discrepancy_qty_threshold: int = 0,
        discrepancy_value_threshold: float = 0.0,
        items: Optional[List[CycleCountItem]] = None,
        created_by: str = "system",
        note: Optional[str] = None,
    ) -> None:
        if not cycle_count_id or not cycle_count_id.strip():
            raise ValidationError("cycle_count_id cannot be empty")
        if warehouse_id <= 0:
            raise InvalidIDError("warehouse_id must be positive")
        if not title or not title.strip():
            raise ValidationError("title cannot be empty")
        if discrepancy_qty_threshold < 0:
            raise ValidationError("discrepancy_qty_threshold cannot be negative")
        if discrepancy_value_threshold < 0:
            raise ValidationError("discrepancy_value_threshold cannot be negative")

        self.cycle_count_id = cycle_count_id.strip()
        self.warehouse_id = warehouse_id
        self.title = title.strip()
        self.assigned_to = assigned_to.strip() if assigned_to else None
        self.status: CycleCountStatus = CycleCountStatus.DRAFT
        self.discrepancy_qty_threshold = discrepancy_qty_threshold
        self.discrepancy_value_threshold = discrepancy_value_threshold
        self.items: List[CycleCountItem] = items or []
        self.created_by = created_by
        self.note = note
        self.created_at = datetime.now(timezone.utc)
        self.submitted_at: Optional[datetime] = None
        self.approved_by: Optional[str] = None
        self.approved_at: Optional[datetime] = None
        self.rejection_reason: Optional[str] = None

    @property
    def identity(self) -> str:
        return self.cycle_count_id

    def add_item(self, item: CycleCountItem) -> None:
        if self.status != CycleCountStatus.DRAFT:
            raise InvalidDocumentStatusError("Cannot add items after sheet is initialized")
        for existing in self.items:
            if existing.item_id == item.item_id:
                raise BusinessRuleViolationError(f"Item '{item.item_id}' already exists in cycle count sheet")
        self.items.append(item)

    def assign_counter(self, assigned_to: str) -> None:
        if not assigned_to or not assigned_to.strip():
            raise ValidationError("assigned_to cannot be empty")
        if self.status in (CycleCountStatus.APPROVED, CycleCountStatus.REJECTED, CycleCountStatus.CANCELLED):
            raise InvalidDocumentStatusError(f"Cannot reassign counter when status is {self.status.value}")
        self.assigned_to = assigned_to.strip()

    def start_counting(self) -> None:
        if self.status not in (CycleCountStatus.DRAFT, CycleCountStatus.IN_PROGRESS):
            raise InvalidDocumentStatusError(f"Cannot start counting when status is {self.status.value}")
        if not self.items:
            raise BusinessRuleViolationError("Cannot start cycle count with empty items list")
        self.status = CycleCountStatus.IN_PROGRESS

    def get_blind_sheet(self) -> List[BlindCountItem]:
        """Returns sheet for counter staff. System quantities are completely hidden."""
        if self.status == CycleCountStatus.CANCELLED:
            raise InvalidDocumentStatusError("Cannot get blind count sheet for cancelled count")
        return [item.to_blind_item() for item in self.items]

    def record_counts(self, counts: Dict[str, int]) -> None:
        """Records physical count results for items."""
        if self.status != CycleCountStatus.IN_PROGRESS:
            raise InvalidDocumentStatusError(f"Cannot record counts when status is {self.status.value}")
        for item_id, qty in counts.items():
            item = self._get_item_by_id(item_id)
            item.record_count(qty)

    def submit_counts(self) -> CycleCountStatus:
        """Finalizes counter input and calculates discrepancies.

        If any item discrepancy > threshold (quantity or monetary value),
        requires supervisor approval (PENDING_SUPERVISOR_APPROVAL).
        Otherwise auto-approves.
        """
        if self.status != CycleCountStatus.IN_PROGRESS:
            raise InvalidDocumentStatusError(f"Cannot submit counts when status is {self.status.value}")
        if not self.items:
            raise BusinessRuleViolationError("No items to submit")

        uncounted = [item.item_id for item in self.items if not item.is_counted]
        if uncounted:
            raise BusinessRuleViolationError(f"Cannot submit count: items {uncounted} have not been counted yet")

        self.submitted_at = datetime.now(timezone.utc)

        # Check discrepancy thresholds
        requires_approval = False
        for item in self.items:
            if item.abs_discrepancy_qty > self.discrepancy_qty_threshold:
                requires_approval = True
                break
            if item.abs_discrepancy_value > self.discrepancy_value_threshold:
                requires_approval = True
                break

        if requires_approval:
            self.status = CycleCountStatus.PENDING_SUPERVISOR_APPROVAL
        else:
            self.status = CycleCountStatus.APPROVED
            self.approved_by = "system"
            self.approved_at = datetime.now(timezone.utc)

        return self.status

    def approve_by_supervisor(self, supervisor_id: str, note: Optional[str] = None) -> None:
        """Supervisor approves the discrepancies."""
        if self.status != CycleCountStatus.PENDING_SUPERVISOR_APPROVAL:
            raise InvalidDocumentStatusError(
                f"Supervisor approval requires status PENDING_SUPERVISOR_APPROVAL, current: {self.status.value}"
            )
        if not supervisor_id or not supervisor_id.strip():
            raise ValidationError("supervisor_id cannot be empty")

        self.status = CycleCountStatus.APPROVED
        self.approved_by = supervisor_id.strip()
        self.approved_at = datetime.now(timezone.utc)
        if note:
            self.note = note

    def reject_by_supervisor(self, supervisor_id: str, reason: str) -> None:
        """Supervisor rejects the discrepancies."""
        if self.status != CycleCountStatus.PENDING_SUPERVISOR_APPROVAL:
            raise InvalidDocumentStatusError(
                f"Supervisor rejection requires status PENDING_SUPERVISOR_APPROVAL, current: {self.status.value}"
            )
        if not supervisor_id or not supervisor_id.strip():
            raise ValidationError("supervisor_id cannot be empty")
        if not reason or not reason.strip():
            raise ValidationError("Rejection reason cannot be empty")

        self.status = CycleCountStatus.REJECTED
        self.approved_by = supervisor_id.strip()
        self.approved_at = datetime.now(timezone.utc)
        self.rejection_reason = reason.strip()

    def cancel(self, reason: Optional[str] = None) -> None:
        if self.status == CycleCountStatus.APPROVED:
            raise InvalidDocumentStatusError("Cannot cancel an approved cycle count sheet")
        self.status = CycleCountStatus.CANCELLED
        if reason:
            self.rejection_reason = reason

    def _get_item_by_id(self, item_id: str) -> CycleCountItem:
        for item in self.items:
            if item.item_id == item_id:
                return item
        raise EntityNotFoundError(f"Item '{item_id}' not found in cycle count sheet")
