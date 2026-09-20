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


class InboundStatus(str, Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    ARRIVED = "ARRIVED"
    RECEIVING = "RECEIVING"
    QA_PENDING = "QA_PENDING"
    QA_IN_PROGRESS = "QA_IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class QAResultStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIALLY_PASSED = "PARTIALLY_PASSED"


@dataclass
class DockAppointment:
    """Represents a dock appointment booking for inbound shipments."""

    dock_door: str
    appointment_time: datetime
    status: str = "SCHEDULED"  # SCHEDULED, CHECKED_IN, COMPLETED, CANCELLED
    carrier: Optional[str] = None
    driver_name: Optional[str] = None
    vehicle_plate: Optional[str] = None

    def check_in(self) -> None:
        if self.status == "CANCELLED":
            raise BusinessRuleViolationError("Cannot check in a cancelled appointment")
        self.status = "CHECKED_IN"

    def complete(self) -> None:
        self.status = "COMPLETED"

    def cancel(self) -> None:
        self.status = "CANCELLED"


@dataclass
class InboundItem:
    """Item detail within an Inbound Shipment (ASN/PO)."""

    product_id: int
    expected_qty: int
    received_qty: int = 0
    passed_qa_qty: int = 0
    failed_qa_qty: int = 0
    lot_number: str = ""
    mfg_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    unit_volume: float = 0.0  # in m3
    unit_weight: float = 0.0  # in kg
    abc_classification: str = "C"  # A, B, or C
    inventory_status: str = "QUARANTINED"  # Initially QUARANTINED on receive
    qa_status: QAResultStatus = QAResultStatus.PENDING

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidIDError("product_id must be positive")
        if self.expected_qty <= 0:
            raise InvalidQuantityError("expected_qty must be positive")
        if self.received_qty < 0 or self.passed_qa_qty < 0 or self.failed_qa_qty < 0:
            raise InvalidQuantityError("Quantity fields cannot be negative")
        if self.abc_classification not in {"A", "B", "C"}:
            raise ValidationError(f"Invalid ABC classification: {self.abc_classification}")

    def receive(self, quantity: int) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("Received quantity must be positive")
        self.received_qty += quantity
        # Upon receiving, inventory status is initially QUARANTINED per AC2
        self.inventory_status = "QUARANTINED"

    def inspect_qa(self, passed_qty: int, failed_qty: int) -> None:
        if passed_qty < 0 or failed_qty < 0:
            raise InvalidQuantityError("QA inspection quantities cannot be negative")
        if passed_qty + failed_qty > self.received_qty:
            raise BusinessRuleViolationError(
                f"Total inspected quantity ({passed_qty + failed_qty}) exceeds received quantity ({self.received_qty})"
            )
        self.passed_qa_qty = passed_qty
        self.failed_qa_qty = failed_qty

        if passed_qty == self.received_qty:
            self.qa_status = QAResultStatus.PASSED
            self.inventory_status = "AVAILABLE"
        elif passed_qty > 0 and failed_qty > 0:
            self.qa_status = QAResultStatus.PARTIALLY_PASSED
            # Passed portion becomes AVAILABLE, failed remains QUARANTINED
        else:
            self.qa_status = QAResultStatus.FAILED
            self.inventory_status = "QUARANTINED"


class InboundShipment(DomainEntity):
    """Domain entity representing an Inbound Shipment (ASN / Purchase Order)."""

    def __init__(
        self,
        shipment_id: int,
        asn_number: str,
        destination_warehouse_id: int,
        po_number: Optional[str] = None,
        supplier_id: Optional[int] = None,
        items: Optional[List[InboundItem]] = None,
        created_by: str = "system",
        note: Optional[str] = None,
    ) -> None:
        if shipment_id < 0:
            raise InvalidIDError("shipment_id must be non-negative")
        if not asn_number or not asn_number.strip():
            raise ValidationError("asn_number cannot be empty")
        if destination_warehouse_id <= 0:
            raise InvalidIDError("destination_warehouse_id must be positive")

        self.shipment_id = shipment_id
        self.asn_number = asn_number.strip()
        self.po_number = po_number.strip() if po_number else None
        self.supplier_id = supplier_id
        self.destination_warehouse_id = destination_warehouse_id
        self.items: List[InboundItem] = items or []
        self.status: InboundStatus = InboundStatus.DRAFT
        self.appointment: Optional[DockAppointment] = None
        self.created_by = created_by
        self.note = note
        self.created_at = datetime.now(timezone.utc)
        self.received_at: Optional[datetime] = None
        self.qa_completed_at: Optional[datetime] = None

    @property
    def identity(self) -> int:
        return self.shipment_id

    def add_item(self, item: InboundItem) -> None:
        if self.status not in (InboundStatus.DRAFT, InboundStatus.SCHEDULED):
            raise InvalidDocumentStatusError("Cannot add items after receiving has started")
        for existing in self.items:
            if existing.product_id == item.product_id:
                raise BusinessRuleViolationError(f"Product {item.product_id} already exists in shipment")
        self.items.append(item)

    def schedule_dock_appointment(
        self,
        dock_door: str,
        appointment_time: datetime,
        carrier: Optional[str] = None,
        driver_name: Optional[str] = None,
        vehicle_plate: Optional[str] = None,
    ) -> DockAppointment:
        if not dock_door or not dock_door.strip():
            raise ValidationError("dock_door must not be empty")
        if self.status == InboundStatus.CANCELLED:
            raise InvalidDocumentStatusError("Cannot schedule appointment for cancelled shipment")

        self.appointment = DockAppointment(
            dock_door=dock_door.strip(),
            appointment_time=appointment_time,
            carrier=carrier,
            driver_name=driver_name,
            vehicle_plate=vehicle_plate,
        )
        if self.status == InboundStatus.DRAFT:
            self.status = InboundStatus.SCHEDULED
        return self.appointment

    def confirm_dock_arrival(self) -> None:
        if not self.appointment:
            raise BusinessRuleViolationError("Cannot confirm arrival without a scheduled dock appointment")
        self.appointment.check_in()
        self.status = InboundStatus.ARRIVED

    def receive_goods(self, received_quantities: Dict[int, int]) -> None:
        """Receives goods at the dock. All received goods initially enter QUARANTINED status."""
        if self.status not in (InboundStatus.ARRIVED, InboundStatus.RECEIVING, InboundStatus.SCHEDULED):
            raise InvalidDocumentStatusError(f"Cannot receive goods when status is {self.status.value}")
        if not self.items:
            raise BusinessRuleViolationError("Cannot receive goods for a shipment with no items")

        for product_id, qty in received_quantities.items():
            item = self._get_item_by_product_id(product_id)
            item.receive(qty)

        self.status = InboundStatus.RECEIVING
        self.received_at = datetime.now(timezone.utc)

    def perform_qa_inspection(self, product_id: int, passed_qty: int, failed_qty: int) -> None:
        """Performs QA inspection on a specific product in the shipment."""
        if self.status not in (InboundStatus.RECEIVING, InboundStatus.QA_PENDING, InboundStatus.QA_IN_PROGRESS):
            raise InvalidDocumentStatusError("QA inspection can only be performed after receiving goods")

        item = self._get_item_by_product_id(product_id)
        item.inspect_qa(passed_qty, failed_qty)
        self.status = InboundStatus.QA_IN_PROGRESS

    def complete_qa_process(self) -> None:
        """Finalizes QA inspection for all items in shipment."""
        if not self.items:
            raise BusinessRuleViolationError("Shipment has no items to complete QA")
        for item in self.items:
            if item.qa_status == QAResultStatus.PENDING and item.received_qty > 0:
                raise BusinessRuleViolationError(f"Product {item.product_id} has not been inspected by QA yet")

        self.status = InboundStatus.COMPLETED
        self.qa_completed_at = datetime.now(timezone.utc)
        if self.appointment:
            self.appointment.complete()

    def cancel_shipment(self, reason: Optional[str] = None) -> None:
        if self.status == InboundStatus.COMPLETED:
            raise InvalidDocumentStatusError("Cannot cancel a completed shipment")
        self.status = InboundStatus.CANCELLED
        if self.appointment:
            self.appointment.cancel()

    def _get_item_by_product_id(self, product_id: int) -> InboundItem:
        for item in self.items:
            if item.product_id == product_id:
                return item
        raise EntityNotFoundError(f"Product {product_id} not found in inbound shipment")
