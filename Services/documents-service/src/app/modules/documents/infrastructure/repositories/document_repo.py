from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.documents.domain.exceptions import DocumentNotFoundError
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.shared.core.transaction import TransactionalRepository
from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo
from app.modules.documents.infrastructure.models.document import DocumentModel
from app.modules.documents.infrastructure.models.document_item import DocumentItemModel


class DocumentRepo(TransactionalRepository, IDocumentRepo):
    """PostgreSQL-backed repository for documents and their items.

    TASK-001: ID assignment is fully delegated to the PostgreSQL BIGSERIAL
    sequence (autoincrement=True on DocumentModel.document_id).  The former
    _sync_id_generator / IDGenerator approach has been removed.

    Insert path:
      When document.document_id == 0 (sentinel), the primary-key column is
      omitted from the INSERT so the DB sequence assigns the next value.
      After session.flush() the ORM model carries the generated ID, which is
      written back to document.document_id before returning.
    """

    def __init__(self, session: Session):
        super().__init__(session)

    def save(self, document: Document) -> None:
        # --- Determine create vs. update -----------------------------------
        is_new = document.document_id == 0

        if not is_new:
            model = self.session.get(DocumentModel, document.document_id)
        else:
            model = None

        if model is None:
            # New document: omit document_id so the DB sequence auto-assigns it.
            model_kwargs: dict = {
                "doc_type": document.doc_type.value,
                "status": document.status.value,
                "from_warehouse_id": document.from_warehouse_id,
                "to_warehouse_id": document.to_warehouse_id,
                "created_by": document.created_by,
                "approved_by": document.approved_by,
                "note": document.note,
                "customer_id": document.customer_id,
                "created_at": document.date,
                "posted_at": document.posted_at,
                "cancelled_at": document.cancelled_at,
                "cancellation_reason": document.cancellation_reason,
                # Phase 6: lifecycle fields (set on creation too)
                "transaction_type": getattr(document, "transaction_type", None),
                "reason_code": getattr(document, "reason_code", None),
                "requested_by": getattr(document, "requested_by", None),
                "approved_at": getattr(document, "approved_at", None),
                "execution_started_at": getattr(document, "execution_started_at", None),
                "completed_at": getattr(document, "completed_at", None),
                "assigned_to": getattr(document, "assigned_to", None),
                "reference_doc_id": getattr(document, "reference_doc_id", None),
            }
            # Only pass document_id explicitly when it is already a real DB id
            # (i.e., was loaded from DB or assigned by a test mock).
            if not is_new:
                model_kwargs["document_id"] = document.document_id

            model = DocumentModel(**model_kwargs)
            self.session.add(model)

            # Flush so the DB sequence assigns the primary key, then write it
            # back to the domain entity so callers have the real ID.
            self.session.flush()
            document.document_id = model.document_id

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
            model.reference_doc_id = getattr(document, "reference_doc_id", None)

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

    def get_all(
        self,
        limit: int = 0,
        offset: int = 0,
        status: Optional[DocumentStatus] = None,
        doc_type: Optional[DocumentType] = None,
    ) -> List[Document]:
        """Return documents, optionally filtered by status/doc_type and paginated at the SQL level.

        Args:
            limit: Maximum rows to return. 0 means no limit (backward-compatible default).
            offset: Number of rows to skip.
            status: Optional status filter.
            doc_type: Optional doc_type filter.
        """
        query = select(DocumentModel).order_by(DocumentModel.document_id.desc())
        if status is not None:
            status_val = status.value if hasattr(status, "value") else str(status)
            query = query.where(DocumentModel.status == status_val)
        if doc_type is not None:
            doc_type_val = doc_type.value if hasattr(doc_type, "value") else str(doc_type)
            query = query.where(DocumentModel.doc_type == doc_type_val)
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        rows = self.session.execute(query).scalars().all()
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
        document.reference_doc_id = getattr(model, "reference_doc_id", None)
        return document
