from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.domain.exceptions import DocumentNotFoundError
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.shared.utils.infrastructure.id_generator import IDGenerator
from app.shared.core.transaction import TransactionalRepository
from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo
from app.modules.documents.infrastructure.models.document import DocumentModel
from app.modules.documents.infrastructure.models.document_item import DocumentItemModel


class DocumentRepo(TransactionalRepository, IDocumentRepo):
    """PostgreSQL-backed repository for documents and their items."""

    def __init__(self, session: Session):
        super().__init__(session)
        self._sync_id_generator()

    def _sync_id_generator(self) -> None:
        max_id = self.session.execute(
            select(func.max(DocumentModel.document_id))
        ).scalar()
        # Handle Mock objects in testing
        if hasattr(max_id, '__class__') and max_id.__class__.__name__ == 'Mock':
            start_id = 1
        else:
            start_id = (max_id or 0) + 1
        IDGenerator.reset_generator("document", start_id)

    def save(self, document: Document) -> None:
        model = self.session.get(DocumentModel, document.document_id)
        if not model:
            model = DocumentModel(
                document_id=document.document_id,
                doc_type=document.doc_type.value,
                status=document.status.value,
                from_warehouse_id=document.from_warehouse_id,
                to_warehouse_id=document.to_warehouse_id,
                created_by=document.created_by,
                approved_by=document.approved_by,
                note=document.note,
                customer_id=document.customer_id,
                created_at=document.date,
                posted_at=document.posted_at,
                cancelled_at=document.cancelled_at,
                cancellation_reason=document.cancellation_reason,
                # Phase 6: lifecycle fields (set on creation too)
                transaction_type=getattr(document, "transaction_type", None),
                reason_code=getattr(document, "reason_code", None),
                requested_by=getattr(document, "requested_by", None),
                approved_at=getattr(document, "approved_at", None),
                execution_started_at=getattr(document, "execution_started_at", None),
                completed_at=getattr(document, "completed_at", None),
                assigned_to=getattr(document, "assigned_to", None),
            )
            self.session.add(model)
        else:
            model.doc_type = document.doc_type.value
            model.status = document.status.value
            model.from_warehouse_id = document.from_warehouse_id
            model.to_warehouse_id = document.to_warehouse_id
            model.created_by = document.created_by
            model.approved_by = document.approved_by
            model.note = document.note
            model.customer_id = document.customer_id
            model.created_at = document.date
            model.posted_at = document.posted_at
            model.cancelled_at = document.cancelled_at
            model.cancellation_reason = document.cancellation_reason
            # Phase 6: Persist all lifecycle fields on update
            model.transaction_type = getattr(document, "transaction_type", None)
            model.reason_code = getattr(document, "reason_code", None)
            model.requested_by = getattr(document, "requested_by", None)
            model.approved_at = getattr(document, "approved_at", None)
            model.execution_started_at = getattr(document, "execution_started_at", None)
            model.completed_at = getattr(document, "completed_at", None)
            model.assigned_to = getattr(document, "assigned_to", None)

            # Clear existing items before re-adding
            model.items.clear()

        # Replace items with current state (Phase 6 line fields included)
        for item in document.items:
            model.items.append(
                DocumentItemModel(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    # Phase 6: Persist line lifecycle fields
                    requested_qty=getattr(item, "requested_qty", item.quantity),
                    reserved_qty=getattr(item, "reserved_qty", 0),
                    executed_qty=getattr(item, "executed_qty", None),
                    rejected_qty=getattr(item, "rejected_qty", 0),
                    difference_qty=getattr(item, "difference_qty", 0),
                    execution_status=getattr(item, "execution_status", None),
                )
            )

        self._commit_if_auto()

    def get(self, document_id: int) -> Optional[Document]:
        model = self.session.get(DocumentModel, document_id)
        return self._to_domain(model) if model else None

    def get_all(self) -> List[Document]:
        rows = self.session.execute(select(DocumentModel)).scalars().all()
        return [self._to_domain(row) for row in rows]

    def update_status(self, document_id: int, new_status: DocumentStatus) -> None:
        model = self.session.get(DocumentModel, document_id)
        if not model:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        model.status = new_status.value
        self._commit_if_auto()

    def delete(self, document_id: int) -> None:
        model = self.session.get(DocumentModel, document_id)
        if not model:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        self.session.delete(model)
        self._commit_if_auto()

    @staticmethod
    def _to_domain(model: DocumentModel) -> Document:
        items = []
        for item in model.items:
            dp = DocumentProduct(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            # Phase 6: Restore line lifecycle fields from DB
            dp.requested_qty = item.requested_qty if item.requested_qty is not None else item.quantity
            dp.reserved_qty = item.reserved_qty if item.reserved_qty is not None else 0
            dp.executed_qty = item.executed_qty
            dp.rejected_qty = item.rejected_qty if item.rejected_qty is not None else 0
            dp.difference_qty = item.difference_qty if item.difference_qty is not None else 0
            dp.execution_status = item.execution_status
            items.append(dp)

        document = Document(
            document_id=model.document_id,
            doc_type=DocumentType(model.doc_type),
            from_warehouse_id=model.from_warehouse_id,
            to_warehouse_id=model.to_warehouse_id,
            items=items,
            created_by=model.created_by,
            note=model.note,
            customer_id=model.customer_id,
        )
        document.status = DocumentStatus(model.status)
        document.date = model.created_at
        document.posted_at = model.posted_at
        document.cancelled_at = model.cancelled_at
        document.cancelled_by = getattr(model, "cancelled_by", None)
        document.cancellation_reason = model.cancellation_reason
        document.approved_by = model.approved_by
        # Phase 6: Restore header lifecycle fields from DB
        document.transaction_type = getattr(model, "transaction_type", None)
        document.reason_code = getattr(model, "reason_code", None)
        document.requested_by = getattr(model, "requested_by", None)
        document.approved_at = getattr(model, "approved_at", None)
        document.execution_started_at = getattr(model, "execution_started_at", None)
        document.completed_at = getattr(model, "completed_at", None)
        document.assigned_to = getattr(model, "assigned_to", None)
        return document

