from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.documents.application.ports import (
    DocumentEventPublisher,
    NoopDocumentEventPublisher,
)
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.modules.documents.domain.exceptions import InvalidDocumentStatusError, DocumentNotFoundError
from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo
from app.modules.documents.domain.transaction_types import REQUIRES_REASON_CODE, REQUIRES_RESERVATION
from app.shared.domain.business_exceptions import InvalidQuantityError, ValidationError
from app.shared.utils.infrastructure import document_id_generator


class DocumentService:
    """Owns document lifecycle and stores external references as IDs."""

    def __init__(
        self,
        document_repo: IDocumentRepo,
        session: Optional[Any] = None,
        event_publisher: Optional[DocumentEventPublisher] = None,
    ):
        self.document_repo = document_repo
        self.session = session
        self.event_publisher = event_publisher or NoopDocumentEventPublisher()
        self._doc_id_generator = document_id_generator()

    def create_import_document(
        self,
        to_warehouse_id: int,
        items: List[Dict[str, Any]],
        created_by: str,
        note: Optional[str] = None,
        transaction_type: Optional[str] = None,
        reason_code: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Document:
        document = Document(
            document_id=self._doc_id_generator(),
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=to_warehouse_id,
            items=self._validate_and_convert_items(items),
            created_by=created_by,
            note=note,
        )
        document.transaction_type = transaction_type
        document.reason_code = reason_code
        self.document_repo.save(document)
        self._commit_if_needed()
        self._publish_document_uploaded(document, request_id)
        return document

    def create_export_document(
        self,
        from_warehouse_id: int,
        items: List[Dict[str, Any]],
        created_by: str,
        note: Optional[str] = None,
        transaction_type: Optional[str] = None,
        reason_code: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Document:
        document = Document(
            document_id=self._doc_id_generator(),
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=from_warehouse_id,
            items=self._validate_and_convert_items(items),
            created_by=created_by,
            note=note,
        )
        document.transaction_type = transaction_type
        document.reason_code = reason_code
        self.document_repo.save(document)
        self._commit_if_needed()
        self._publish_document_uploaded(document, request_id)
        return document

    def create_sale_document(
        self,
        from_warehouse_id: int,
        items: List[Dict[str, Any]],
        created_by: str,
        note: Optional[str] = None,
        customer_id: Optional[int] = None,
        transaction_type: Optional[str] = None,
        reason_code: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Document:
        document = Document(
            document_id=self._doc_id_generator(),
            doc_type=DocumentType.SALE,
            from_warehouse_id=from_warehouse_id,
            items=self._validate_and_convert_items(items),
            created_by=created_by,
            note=note,
            customer_id=customer_id,
        )
        document.transaction_type = transaction_type
        document.reason_code = reason_code
        self.document_repo.save(document)
        self._commit_if_needed()
        self._publish_document_uploaded(document, request_id)
        return document

    def create_transfer_document(
        self,
        from_warehouse_id: int,
        to_warehouse_id: int,
        items: List[Dict[str, Any]],
        created_by: str,
        note: Optional[str] = None,
        transaction_type: Optional[str] = None,
        reason_code: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Document:
        document = Document(
            document_id=self._doc_id_generator(),
            doc_type=DocumentType.TRANSFER,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            items=self._validate_and_convert_items(items),
            created_by=created_by,
            note=note,
        )
        document.transaction_type = transaction_type
        document.reason_code = reason_code
        self.document_repo.save(document)
        self._commit_if_needed()
        self._publish_document_uploaded(document, request_id)
        return document

    def post_document(
        self,
        document_id: int,
        approved_by: str,
        request_id: Optional[str] = None,
    ) -> Document:
        document = self.get_document(document_id)
        if document.status == DocumentStatus.CANCELLED:
            raise InvalidDocumentStatusError(f"Cannot post cancelled document {document_id}")
        if document.status == DocumentStatus.POSTED:
            if approved_by and document.approved_by and approved_by != document.approved_by:
                raise InvalidDocumentStatusError(
                    f"Document {document_id} has already been posted by {document.approved_by}"
                )
            self._publish_document_posted(document, request_id)
            return document

        document.post(approved_by)
        self.document_repo.save(document)
        self._commit_if_needed()
        self._publish_document_posted(document, request_id)
        return document

    # Phase 7: Approve without stock movement
    def approve_request(
        self,
        document_id: int,
        approved_by: str,
        request_id: Optional[str] = None,
    ) -> Document:
        """Approve a document without triggering stock movement.
        
        This is the new lifecycle method that only changes document status
        and approval metadata. It does NOT emit InventoryMovementRequested.
        """
        from datetime import datetime

        document = self.get_document(document_id)
        if document.status == DocumentStatus.CANCELLED:
            raise InvalidDocumentStatusError(f"Cannot approve cancelled document {document_id}")
        if document.status == DocumentStatus.POSTED:
            if approved_by and document.approved_by and approved_by != document.approved_by:
                raise InvalidDocumentStatusError(
                    f"Document {document_id} has already been approved by {document.approved_by}"
                )
            return document

        # Only change status and approval metadata - no stock movement
        document.status = DocumentStatus.POSTED
        document.approved_by = approved_by
        document.approved_at = datetime.now()
        document.posted_at = datetime.now()  # For backward compatibility

        self.document_repo.save(document)
        self._commit_if_needed()
        
        # Only publish DocumentPosted, NOT InventoryMovementRequested
        self.event_publisher.publish(
            event_type="DocumentPosted",
            payload=document.posted_event_payload(request_id),
        )
        return document

    def cancel_document(
        self,
        document_id: int,
        cancelled_by: str,
        reason: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Document:
        document = self.get_document(document_id)  # raises DocumentNotFoundError if missing
        document.cancel(cancelled_by, reason)
        self.document_repo.save(document)
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="DocumentCancelled",
            payload=document.cancelled_event_payload(request_id),
        )
        return document

    # Phase 8: Sales reservation workflow
    def reserve_request_stock(
        self,
        document_id: int,
        request_id: Optional[str] = None,
    ) -> Document:
        """Reserve stock for SALE documents to prevent double-selling.
        
        For SALE documents, reserves each line from the source warehouse.
        Updates document line reserved_qty with the reservation ID.
        """
        from datetime import datetime

        document = self.get_document(document_id)
        
        # Phase 8: Only implement for SALE documents initially
        if document.doc_type != DocumentType.SALE:
            raise InvalidDocumentStatusError(
                f"Reservation only supported for SALE documents, got {document.doc_type}"
            )
        
        if document.status != DocumentStatus.POSTED:
            raise InvalidDocumentStatusError(
                f"Document must be POSTED before reserving, current status: {document.status}"
            )

        # Track reservation IDs for each line
        reservation_ids = []
        
        # Reserve each line from source warehouse
        for item in document.items:
            # TODO(Phase 8 → future): wire this to a real inventory service call via gRPC or
            # an application-layer port so that InventoryRepo.create_reservation() is called,
            # the ATP check is enforced, and a real stock_reservations row is written.
            # Currently this only updates the document entity in-memory (and persists via
            # document_repo.save below). The StockReserved event carries placeholder IDs.
            idempotency_key = f"doc_{document_id}_product_{item.product_id}"  # noqa: F841
            item.reserved_qty = item.requested_qty
            reservation_ids.append(f"reservation_{document_id}_{item.product_id}")
        
        # Update execution metadata
        document.execution_started_at = datetime.now()
        
        self.document_repo.save(document)
        self._commit_if_needed()
        
        # Emit StockReserved event
        self.event_publisher.publish(
            event_type="StockReserved",
            payload={
                "event_id": f"documents:{document_id}:stock-reserved",
                "request_id": request_id,
                "entity_type": "document",
                "entity_id": document_id,
                "document_id": document_id,
                "doc_type": document.doc_type.value,
                "from_warehouse_id": document.from_warehouse_id,
                "reservation_ids": reservation_ids,
                "items": document._item_snapshots(),
            },
        )
        
        return document

    def release_request_reservation(
        self,
        document_id: int,
        request_id: Optional[str] = None,
    ) -> Document:
        """Release stock reservations for a document.
        
        Releases all reservations associated with the document lines.
        Restores available stock quantity.
        """
        from datetime import datetime

        document = self.get_document(document_id)
        
        # Release reservations for each line
        reservation_ids = []
        for item in document.items:
            if item.reserved_qty > 0:
                # In real implementation, would call inventory_service.release_reservation()
                reservation_ids.append(f"reservation_{document_id}_{item.product_id}")
                item.reserved_qty = 0
        
        # Update execution metadata
        document.completed_at = datetime.now()
        
        self.document_repo.save(document)
        self._commit_if_needed()
        
        # Emit ReservationReleased event
        self.event_publisher.publish(
            event_type="ReservationReleased",
            payload={
                "event_id": f"documents:{document_id}:reservation-released",
                "request_id": request_id,
                "entity_type": "document",
                "entity_id": document_id,
                "document_id": document_id,
                "doc_type": document.doc_type.value,
                "reservation_ids": reservation_ids,
                "items": document._item_snapshots(),
            },
        )
        
        return document

    # Phase 10: Start execution
    def start_execution(
        self,
        document_id: int,
        request_id: Optional[str] = None,
    ) -> Document:
        """Transitions document to IN_PROGRESS and sets execution_started_at."""
        from datetime import datetime

        document = self.get_document(document_id)
        if document.status == DocumentStatus.CANCELLED:
            raise InvalidDocumentStatusError(f"Cannot start execution on cancelled document {document_id}")
        if document.status == DocumentStatus.COMPLETED:
            raise InvalidDocumentStatusError(f"Cannot start execution on completed document {document_id}")

        document.status = DocumentStatus.IN_PROGRESS
        document.execution_started_at = datetime.now()

        self.document_repo.save(document)
        self._commit_if_needed()

        self.event_publisher.publish(
            event_type="WarehouseExecutionStarted",
            payload={
                "event_id": f"documents:{document_id}:execution-started",
                "request_id": request_id,
                "document_id": document_id,
                "status": document.status.value,
            },
        )
        return document

    # Phase 10: Confirm execution
    def confirm_execution(
        self,
        document_id: int,
        items: List[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> Document:
        """Confirms execution of actual picked/shipped quantity per item."""
        document = self.get_document(document_id)
        if document.status not in (DocumentStatus.IN_PROGRESS, DocumentStatus.POSTED, DocumentStatus.RESERVED, DocumentStatus.EXECUTED):
            raise InvalidDocumentStatusError(
                f"Document must be IN_PROGRESS, POSTED/RESERVED, or EXECUTED before confirming execution, current status: {document.status}"
            )

        # Phase 12 & 13: Validate reason code for transaction types that require it
        if document.transaction_type in REQUIRES_REASON_CODE and not document.reason_code:
            raise ValidationError(f"Reason code is required for {document.transaction_type}")

        # Update items with actual executed quantities
        item_map = {item.product_id: item for item in document.items}
        for item_data in items:
            prod_id = int(item_data["product_id"])
            exec_qty = int(item_data["quantity"])
            if prod_id in item_map:
                item = item_map[prod_id]
                item.executed_qty = exec_qty
                item.difference_qty = item.requested_qty - exec_qty
                item.execution_status = "EXECUTED"

        document.status = DocumentStatus.EXECUTED

        self.document_repo.save(document)
        self._commit_if_needed()

        self.event_publisher.publish(
            event_type="WarehouseExecutionConfirmed",
            payload={
                "event_id": f"documents:{document_id}:execution-confirmed",
                "request_id": request_id,
                "document_id": document_id,
                "items": [{"product_id": k, "quantity": v.executed_qty} for k, v in item_map.items() if v.executed_qty is not None],
            },
        )
        return document

    # Phase 10: Complete request
    def complete_request(
        self,
        document_id: int,
        request_id: Optional[str] = None,
    ) -> Document:
        """Transitions document to COMPLETED status and sets completed_at."""
        from datetime import datetime

        document = self.get_document(document_id)
        if document.status != DocumentStatus.EXECUTED:
            raise InvalidDocumentStatusError(
                f"Document must be EXECUTED before completing, current status: {document.status}"
            )

        document.status = DocumentStatus.COMPLETED
        document.completed_at = datetime.now()

        self.document_repo.save(document)
        self._commit_if_needed()

        self.event_publisher.publish(
            event_type="DocumentCompleted",
            payload={
                "event_id": f"documents:{document_id}:completed",
                "request_id": request_id,
                "document_id": document_id,
                "status": document.status.value,
            },
        )
        return document

    def _commit_if_needed(self) -> None:

        if self.session:
            self.session.commit()

    def get_document_with_details(self, document_id: int) -> Dict[str, Any]:
        document = self.get_document(document_id)
        enriched_items = [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_value": item.unit_price * item.quantity,
            }
            for item in document.items
        ]
        return {
            "document": document,
            "items": enriched_items,
            "warehouses": {
                "from_warehouse_id": document.from_warehouse_id,
                "to_warehouse_id": document.to_warehouse_id,
            },
            "total_value": sum(i["total_value"] for i in enriched_items),
        }

    def get_pending_documents(self) -> List[Document]:
        return [d for d in self.document_repo.get_all() if d.status == DocumentStatus.DRAFT]

    def get_documents_by_status(self, status: DocumentStatus) -> List[Document]:
        return [d for d in self.document_repo.get_all() if d.status == status]

    def get_document(self, document_id: int) -> Document:
        document = self.document_repo.get(document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return document

    def get_documents(
        self,
        doc_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Document]:
        all_docs = self.document_repo.get_all()
        if doc_type:
            doc_type_enum = DocumentType(doc_type.upper())
            all_docs = [doc for doc in all_docs if doc.doc_type == doc_type_enum]
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        return all_docs[start_idx:end_idx]

    def delete_document(self, document_id: int) -> None:
        document = self.get_document(document_id)
        if document.status.value.upper() != "DRAFT":
            raise InvalidDocumentStatusError(
                f"Cannot delete document with status {document.status.value}. Only DRAFT documents can be deleted."
            )
        self.document_repo.delete(document_id)
        self._commit_if_needed()

    def _publish_document_uploaded(
        self,
        document: Document,
        request_id: Optional[str] = None,
    ) -> None:
        self.event_publisher.publish(
            event_type="DocumentUploaded",
            payload=document.uploaded_event_payload(request_id),
        )

    def _publish_document_posted(
        self,
        document: Document,
        request_id: Optional[str] = None,
    ) -> None:
        self.event_publisher.publish(
            event_type="DocumentPosted",
            payload=document.posted_event_payload(request_id),
        )
        self.event_publisher.publish(
            event_type="InventoryMovementRequested",
            payload=document.inventory_movement_requested_payload(request_id),
        )

    def _validate_and_convert_items(self, items: List[Dict[str, Any]]) -> List[DocumentProduct]:
        if not items:
            raise ValidationError("Document must contain at least one item")

        document_items: list[DocumentProduct] = []
        for item_data in items:
            product_id = item_data.get("product_id")
            quantity = item_data.get("quantity")
            unit_price = item_data.get("unit_price", 0)

            if product_id is None or quantity is None:
                raise ValidationError("Each item must have product_id and quantity")
            if quantity <= 0:
                raise InvalidQuantityError("Quantity must be positive")
            if unit_price is None:
                unit_price = 0
            if unit_price < 0:
                raise ValidationError("Unit price cannot be negative")

            document_items.append(
                DocumentProduct(
                    product_id=int(product_id),
                    quantity=int(quantity),
                    unit_price=float(unit_price),
                )
            )

        return document_items
