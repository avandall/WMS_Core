from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidDocumentStatusError,
    InvalidIDError,
    InvalidQuantityError,
    ValidationError,
)
from app.shared.domain.entity import DomainEntity


class DocumentType(str, Enum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    TRANSFER = "TRANSFER"
    SALE = "SALE"


class DocumentStatus(str, Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class DocumentProduct:
    """Domain entity for document line items."""

    def __init__(self, product_id: int, quantity: int, unit_price: float) -> None:
        self._validate_product_id(product_id)
        self._validate_quantity(quantity)
        self._validate_unit_price(unit_price)

        self.product_id = product_id
        self.quantity = quantity
        self.unit_price = float(unit_price)

        self.requested_qty: int = quantity
        self.reserved_qty: int = 0
        self.executed_qty: Optional[int] = None
        self.rejected_qty: int = 0
        self.difference_qty: int = 0
        self.execution_status: Optional[str] = None

    @staticmethod
    def _validate_product_id(product_id: int) -> None:
        if not isinstance(product_id, int) or product_id <= 0:
            raise InvalidIDError("product_id must be a positive integer")

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidQuantityError("quantity must be a positive integer")

    @staticmethod
    def _validate_unit_price(unit_price: float) -> None:
        if not isinstance(unit_price, (int, float)) or unit_price < 0:
            raise InvalidQuantityError("unit_price must be a non-negative number")

    def calculate_total_value(self) -> float:
        return self.quantity * self.unit_price

    def __str__(self) -> str:
        return (
            f"DocumentProduct(product_id={self.product_id}, quantity={self.quantity}, unit_price={self.unit_price})"
        )

    def __repr__(self) -> str:
        return self.__str__()


class Document(DomainEntity):
    """Domain entity for warehouse documents."""

    def __init__(
        self,
        document_id: int,
        doc_type: DocumentType,
        from_warehouse_id: Optional[int] = None,
        to_warehouse_id: Optional[int] = None,
        items: Optional[List[DocumentProduct]] = None,
        created_by: str = "",
        note: Optional[str] = None,
        customer_id: Optional[int] = None,
    ) -> None:
        self._validate_document_id(document_id)
        self._validate_document_type(doc_type)
        self._validate_warehouses(doc_type, from_warehouse_id, to_warehouse_id)
        self._validate_created_by(created_by)

        self.document_id = document_id
        self.doc_type = doc_type
        self.status = DocumentStatus.DRAFT
        self.date = datetime.now()
        self.created_at = self.date
        self.posted_at = None
        self.cancelled_at = None
        self.cancelled_by = None
        self.cancellation_reason = None
        self.from_warehouse_id = from_warehouse_id
        self.to_warehouse_id = to_warehouse_id
        self.customer_id = customer_id
        self.items = items or []
        self.created_by = created_by
        self.note = note
        self.approved_by = None

        self.transaction_type: Optional[str] = None
        self.reason_code: Optional[str] = None
        self.requested_by: Optional[str] = None
        self.approved_at: Optional[datetime] = None
        self.execution_started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.assigned_to: Optional[str] = None

    @staticmethod
    def _validate_document_id(document_id: int) -> None:
        if not isinstance(document_id, int) or document_id <= 0:
            raise InvalidIDError("document_id must be a positive integer")

    @staticmethod
    def _validate_document_type(doc_type: DocumentType) -> None:
        if doc_type not in DocumentType:
            raise ValidationError("doc_type must be a valid DocumentType")

    @staticmethod
    def _validate_warehouses(
        doc_type: DocumentType,
        from_warehouse_id: Optional[int],
        to_warehouse_id: Optional[int],
    ) -> None:
        if doc_type == DocumentType.IMPORT:
            if to_warehouse_id is None:
                raise ValidationError("IMPORT documents require a destination warehouse")
        elif doc_type in (DocumentType.EXPORT, DocumentType.SALE):
            if from_warehouse_id is None:
                raise ValidationError("EXPORT and SALE documents require a source warehouse")
        elif doc_type == DocumentType.TRANSFER:
            if from_warehouse_id is None or to_warehouse_id is None:
                raise ValidationError("TRANSFER documents require both source and destination warehouses")
            if from_warehouse_id == to_warehouse_id:
                raise BusinessRuleViolationError("TRANSFER documents cannot use the same warehouse for source and destination")

    @staticmethod
    def _validate_created_by(created_by: str) -> None:
        if not isinstance(created_by, str) or not created_by.strip():
            raise ValidationError("created_by must be a non-empty string")

    def add_item(self, item: DocumentProduct) -> None:
        self._ensure_draft_status()
        for existing_item in self.items:
            if existing_item.product_id == item.product_id:
                raise BusinessRuleViolationError(
                    f"Product {item.product_id} already exists in document"
                )
        self.items.append(item)

    def remove_item(self, product_id: int) -> None:
        self._ensure_draft_status()
        for index, item in enumerate(self.items):
            if item.product_id == product_id:
                self.items.pop(index)
                return
        raise EntityNotFoundError(f"Product {product_id} not found in document")

    def update_item(self, product_id: int, quantity: int, unit_price: float) -> None:
        self._ensure_draft_status()
        DocumentProduct._validate_quantity(quantity)
        DocumentProduct._validate_unit_price(unit_price)

        for item in self.items:
            if item.product_id == product_id:
                item.quantity = quantity
                item.unit_price = float(unit_price)
                return
        raise EntityNotFoundError(f"Product {product_id} not found in document")

    def post(self, approved_by: str) -> None:
        if self.status != DocumentStatus.DRAFT:
            raise InvalidDocumentStatusError(
                f"Document {self.document_id} is not in DRAFT status"
            )
        if not isinstance(approved_by, str) or not approved_by.strip():
            raise ValidationError("approved_by must be a non-empty string")
        if not self.items:
            raise BusinessRuleViolationError("Cannot post document without items")

        self.status = DocumentStatus.POSTED
        self.approved_by = approved_by
        self.posted_at = datetime.now()

    def cancel(self, cancelled_by: str, reason: Optional[str] = None) -> None:
        if self.status == DocumentStatus.POSTED:
            raise InvalidDocumentStatusError(
                f"Cannot cancel a posted document {self.document_id}"
            )
        if self.status == DocumentStatus.CANCELLED:
            raise InvalidDocumentStatusError(f"Document {self.document_id} is already cancelled")
        if not isinstance(cancelled_by, str) or not cancelled_by.strip():
            raise ValidationError("cancelled_by must be a non-empty string")

        self.status = DocumentStatus.CANCELLED
        self.cancelled_at = datetime.now()
        self.cancelled_by = cancelled_by
        self.cancellation_reason = reason

    def uploaded_event_payload(self, request_id: Optional[str] = None) -> dict:
        return {
            "event_id": f"documents:{self.document_id}:uploaded",
            "request_id": request_id,
            "entity_type": "document",
            "entity_id": self.document_id,
            "document_id": self.document_id,
            "doc_type": self.doc_type.value,
            "status": self.status.value,
            "customer_id": self.customer_id,
            "from_warehouse_id": self.from_warehouse_id,
            "to_warehouse_id": self.to_warehouse_id,
            "items": self._item_snapshots(),
        }

    def posted_event_payload(self, request_id: Optional[str] = None) -> dict:
        return {
            "event_id": f"documents:{self.document_id}:posted",
            "request_id": request_id,
            "entity_type": "document",
            "entity_id": self.document_id,
            "document_id": self.document_id,
            "doc_type": self.doc_type.value,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }

    def inventory_movement_requested_payload(self, request_id: Optional[str] = None) -> dict:
        return {
            "event_id": f"documents:{self.document_id}:inventory-movement-requested",
            "request_id": request_id,
            "entity_type": "document",
            "entity_id": self.document_id,
            "document_id": self.document_id,
            "doc_type": self.doc_type.value,
            "from_warehouse_id": self.from_warehouse_id,
            "to_warehouse_id": self.to_warehouse_id,
            "items": self._item_snapshots(),
        }

    def cancelled_event_payload(self, request_id: Optional[str] = None) -> dict:
        return {
            "event_id": f"documents:{self.document_id}:cancelled",
            "request_id": request_id,
            "entity_type": "document",
            "entity_id": self.document_id,
            "document_id": self.document_id,
            "doc_type": self.doc_type.value,
            "status": self.status.value,
            "cancelled_by": self.cancelled_by,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "reason": self.cancellation_reason,
        }

    def _item_snapshots(self) -> list[dict]:
        return [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "requested_qty": item.requested_qty,
                "executed_qty": item.executed_qty,
            }
            for item in self.items
        ]

    def _ensure_draft_status(self) -> None:
        if self.status != DocumentStatus.DRAFT:
            raise InvalidDocumentStatusError(
                f"Cannot modify document {self.document_id} when not in DRAFT status"
            )

    def calculate_total_value(self) -> float:
        return sum(item.calculate_total_value() for item in self.items)

    def get_summary(self) -> dict:
        return {
            "document_id": self.document_id,
            "type": self.doc_type.value,
            "status": self.status.value,
            "date": self.date.isoformat(),
            "from_warehouse": self.from_warehouse_id,
            "to_warehouse": self.to_warehouse_id,
            "total_items": len(self.items),
            "total_quantity": sum(item.quantity for item in self.items),
            "total_value": self.calculate_total_value(),
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "transaction_type": self.transaction_type,
            "reason_code": self.reason_code,
        }

    def can_be_modified(self) -> bool:
        return self.status == DocumentStatus.DRAFT

    @property
    def identity(self) -> int:
        return self.document_id

    def __str__(self) -> str:
        return (
            f"Document(id={self.document_id}, type={self.doc_type.value}, status={self.status.value}, items={len(self.items)})"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Document):
            return False
        return self.document_id == other.document_id

    def __hash__(self) -> int:
        return hash(self.document_id)
