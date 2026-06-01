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

    def cancel_document(
        self,
        document_id: int,
        cancelled_by: str,
        reason: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Document:
        document = self.document_repo.get(document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        document.cancel(cancelled_by, reason)
        self.document_repo.save(document)
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="DocumentCancelled",
            payload=document.cancelled_event_payload(request_id),
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
