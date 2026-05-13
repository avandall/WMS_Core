from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.shared.core.logging import get_logger
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.shared.domain.business_exceptions import (
    InsufficientStockError,
    InvalidQuantityError,
    ValidationError,
)
from app.modules.documents.domain.exceptions import InvalidDocumentStatusError, DocumentNotFoundError
from app.modules.products.domain.exceptions import ProductNotFoundError
from app.modules.warehouses.domain.exceptions import WarehouseNotFoundError
from app.modules.audit.domain.interfaces.audit_event_repo import IAuditEventRepo
from app.modules.customers.domain.interfaces.customer_repo import ICustomerRepo
from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo
from app.modules.positions.domain.interfaces.position_repo import IPositionRepo
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo
from app.shared.utils.infrastructure import document_id_generator

logger = get_logger(__name__)


class DocumentService:
    """Orchestrates document lifecycle (create/post/cancel)."""

    def __init__(
        self,
        document_repo: IDocumentRepo,
        warehouse_repo: IWarehouseRepo,
        product_repo: IProductRepo,
        inventory_repo: IInventoryRepo,
        customer_repo: Optional[ICustomerRepo] = None,
        position_repo: Optional[IPositionRepo] = None,
        audit_event_repo: Optional[IAuditEventRepo] = None,
        session: Optional[Any] = None,
    ):
        self.document_repo = document_repo
        self.warehouse_repo = warehouse_repo
        self.product_repo = product_repo
        self.inventory_repo = inventory_repo
        self.customer_repo = customer_repo
        self.position_repo = position_repo
        self.audit_event_repo = audit_event_repo
        self.session = session
        self._doc_id_generator = document_id_generator()

    async def create_import_document(
        self,
        to_warehouse_id: int,
        items: List[Dict[str, Any]],
        created_by: str,
        note: Optional[str] = None,
    ) -> Document:
        if not self.warehouse_repo.get(to_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {to_warehouse_id} not found")
        document_items = self._validate_and_convert_items(items, check_product_exists=True)
        document_id = self._doc_id_generator()
        document = Document(
            document_id=document_id,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=to_warehouse_id,
            items=document_items,
            created_by=created_by,
            note=note,
        )
        self.document_repo.save(document)
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
            filtered_docs = [doc for doc in all_docs if doc.doc_type == doc_type_enum]
        else:
            filtered_docs = all_docs
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        return filtered_docs[start_idx:end_idx]

    def delete_document(self, document_id: int) -> None:
        document = self.get_document(document_id)
        if document.status.value.upper() != "DRAFT":
            raise InvalidDocumentStatusError(
                f"Cannot delete document with status {document.status.value}. Only DRAFT documents can be deleted."
            )
        self.document_repo.delete(document_id)

    async def create_export_document(
        self,
        from_warehouse_id: int,
        items: List[Dict[str, Any]],
        created_by: str,
        note: Optional[str] = None,
    ) -> Document:
        if not self.warehouse_repo.get(from_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {from_warehouse_id} not found")
        document_items = self._validate_and_convert_items(items, check_product_exists=True)
        document_id = self._doc_id_generator()
        document = Document(
            document_id=document_id,
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=from_warehouse_id,
            items=document_items,
            created_by=created_by,
            note=note,
        )
        self.document_repo.save(document)
        return document

    async def create_sale_document(
        self,
        from_warehouse_id: int,
        items: List[Dict[str, Any]],
        created_by: str,
        note: Optional[str] = None,
        customer_id: Optional[int] = None,
    ) -> Document:
        if not self.warehouse_repo.get(from_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {from_warehouse_id} not found")
        document_items = self._validate_and_convert_items(items, check_product_exists=True)
        document_id = self._doc_id_generator()
        document = Document(
            document_id=document_id,
            doc_type=DocumentType.SALE,
            from_warehouse_id=from_warehouse_id,
            items=document_items,
            created_by=created_by,
            note=note,
            customer_id=customer_id,
        )
        self.document_repo.save(document)
        return document

    async def create_transfer_document(
        self,
        from_warehouse_id: int,
        to_warehouse_id: int,
        items: List[Dict[str, Any]],
        created_by: str,
        note: Optional[str] = None,
    ) -> Document:
        if not self.warehouse_repo.get(from_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {from_warehouse_id} not found")
        if not self.warehouse_repo.get(to_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {to_warehouse_id} not found")
        document_items = self._validate_and_convert_items(items, check_product_exists=True)
        document_id = self._doc_id_generator()
        document = Document(
            document_id=document_id,
            doc_type=DocumentType.TRANSFER,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            items=document_items,
            created_by=created_by,
            note=note,
        )
        self.document_repo.save(document)
        return document

    def post_document(self, document_id: int, approved_by: str) -> Document:
        document = self._get_document_for_processing(document_id)
        if not self.session:
            logger.warning("No session provided - using auto-commit mode")
            return self._post_document_legacy(document, approved_by)

        try:
            self._set_repos_auto_commit(False)

            if document.doc_type == DocumentType.IMPORT:
                self._execute_import_operations(document)
            elif document.doc_type in (DocumentType.EXPORT, DocumentType.SALE):
                self._execute_export_operations(document)
            elif document.doc_type == DocumentType.TRANSFER:
                self._execute_transfer_operations(document)

            if document.doc_type == DocumentType.SALE and document.customer_id and self.customer_repo:
                total_value = sum(item.quantity * item.unit_price for item in document.items)
                self.customer_repo.record_purchase(document.customer_id, document.document_id, total_value)

            document.post(approved_by)
            self.document_repo.save(document)

            if self.audit_event_repo:
                self.audit_event_repo.create_event(
                    action="DOCUMENT_POSTED",
                    entity_type="document",
                    entity_id=str(document.document_id),
                    warehouse_id=document.from_warehouse_id or document.to_warehouse_id,
                    payload={
                        "document_id": document.document_id,
                        "doc_type": document.doc_type.value,
                        "from_warehouse_id": document.from_warehouse_id,
                        "to_warehouse_id": document.to_warehouse_id,
                        "approved_by": approved_by,
                        "items": [
                            {
                                "product_id": item.product_id,
                                "quantity": item.quantity,
                                "unit_price": item.unit_price,
                            }
                            for item in document.items
                        ],
                    },
                )

            self.session.commit()
            return document

        except InsufficientStockError:
            self.session.rollback()
            raise
        except Exception as exc:
            self.session.rollback()
            raise ValidationError(f"Failed to post document {document_id}: {exc}") from exc
        finally:
            self._set_repos_auto_commit(True)

    def _post_document_legacy(self, document: Document, approved_by: str) -> Document:
        if document.doc_type == DocumentType.IMPORT:
            self._execute_import_operations(document)
        elif document.doc_type in (DocumentType.EXPORT, DocumentType.SALE):
            self._execute_export_operations(document)
        elif document.doc_type == DocumentType.TRANSFER:
            self._execute_transfer_operations(document)

        if document.doc_type == DocumentType.SALE and document.customer_id and self.customer_repo:
            total_value = sum(item.quantity * item.unit_price for item in document.items)
            self.customer_repo.record_purchase(document.customer_id, document.document_id, total_value)

        document.post(approved_by)
        self.document_repo.save(document)
        return document

    def _set_repos_auto_commit(self, enabled: bool) -> None:
        for repo in [
            self.warehouse_repo,
            self.inventory_repo,
            self.document_repo,
            self.position_repo,
            self.audit_event_repo,
            self.customer_repo,
        ]:
            if repo is None:
                continue
            if hasattr(repo, "set_auto_commit"):
                repo.set_auto_commit(enabled)

    def cancel_document(
        self, document_id: int, cancelled_by: str, reason: Optional[str] = None
    ) -> Document:
        document = self.document_repo.get(document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        if document.status == DocumentStatus.POSTED:
            raise InvalidDocumentStatusError(f"Cannot cancel a posted document {document_id}")
        if document.status == DocumentStatus.CANCELLED:
            raise InvalidDocumentStatusError(f"Document {document_id} is already cancelled")

        document.status = DocumentStatus.CANCELLED
        document.cancelled_by = cancelled_by
        document.cancelled_at = datetime.now()
        document.cancellation_reason = reason
        self.document_repo.save(document)
        return document

    def get_document_with_details(self, document_id: int) -> Dict[str, Any]:
        document = self.document_repo.get(document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        enriched_items = []
        for item in document.items:
            product = self.product_repo.get(item.product_id)
            enriched_items.append(
                {
                    "product": product,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_value": item.unit_price * item.quantity,
                }
            )

        warehouse_info: dict[str, Any] = {}
        if document.from_warehouse_id:
            warehouse_info["from_warehouse"] = self.warehouse_repo.get(document.from_warehouse_id)
        if document.to_warehouse_id:
            warehouse_info["to_warehouse"] = self.warehouse_repo.get(document.to_warehouse_id)

        return {
            "document": document,
            "items": enriched_items,
            "warehouses": warehouse_info,
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

    def _validate_and_convert_items(
        self, items: List[Dict[str, Any]], check_product_exists: bool = True
    ) -> List[DocumentProduct]:
        if not items:
            raise ValidationError("Document must contain at least one item")

        document_items: list[DocumentProduct] = []
        for item_data in items:
            product_id = item_data.get("product_id")
            quantity = item_data.get("quantity")
            unit_price = item_data.get("unit_price")

            if product_id is None or quantity is None:
                raise ValidationError("Each item must have product_id and quantity")

            if unit_price is None:
                unit_price = 0

            if quantity <= 0:
                raise InvalidQuantityError("Quantity must be positive")
            if unit_price < 0:
                raise ValidationError("Unit price cannot be negative")

            if check_product_exists:
                product = self.product_repo.get(int(product_id))
                if not product:
                    raise ProductNotFoundError(f"Product {product_id} not found")

            document_items.append(
                DocumentProduct(
                    product_id=int(product_id),
                    quantity=int(quantity),
                    unit_price=float(unit_price),
                )
            )

        return document_items

    def _get_document_for_processing(self, document_id: int) -> Document:
        document = self.document_repo.get(document_id)
        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        if document.status != DocumentStatus.DRAFT:
            raise InvalidDocumentStatusError(
                f"Document {document_id} is not in DRAFT status"
            )
        return document

    def _execute_import_operations(self, document: Document) -> None:
        assert document.to_warehouse_id is not None
        if not self.warehouse_repo.get(document.to_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {document.to_warehouse_id} not found")

        for item in document.items:
            if self.position_repo:
                self._ensure_positions_balanced(document.to_warehouse_id, item.product_id)
                receiving = self.position_repo.get_position_model(document.to_warehouse_id, "RECEIVING")
                self.position_repo.adjust_position_stock(
                    position_id=receiving.id,
                    product_id=item.product_id,
                    delta=item.quantity,
                )

            self.warehouse_repo.add_product_to_warehouse(
                document.to_warehouse_id, item.product_id, item.quantity
            )
            self.inventory_repo.add_quantity(item.product_id, item.quantity)

    def _execute_export_operations(self, document: Document) -> None:
        if not document.from_warehouse_id:
            raise ValidationError("Export document must have from_warehouse_id")
        if not self.warehouse_repo.get(document.from_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {document.from_warehouse_id} not found")

        warehouse_inventory = self.warehouse_repo.get_warehouse_inventory(document.from_warehouse_id)
        inventory_map = {item.product_id: item.quantity for item in warehouse_inventory}

        for item in document.items:
            available = inventory_map.get(item.product_id, 0)
            if available < item.quantity:
                raise InsufficientStockError(
                    f"Insufficient stock for product {item.product_id}: requested {item.quantity}, available {available}"
                )

            if self.position_repo:
                self._ensure_positions_balanced(document.from_warehouse_id, item.product_id)
                self.position_repo.allocate_and_remove(
                    warehouse_id=document.from_warehouse_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    preferred_position_codes=[
                        "SHIPPING",
                        "STAGING",
                        "STORAGE",
                        "UNASSIGNED",
                        "RECEIVING",
                    ],
                )

            self.warehouse_repo.remove_product_from_warehouse(
                document.from_warehouse_id, item.product_id, item.quantity
            )
            self.inventory_repo.remove_quantity(item.product_id, item.quantity)

    def _execute_transfer_operations(self, document: Document) -> None:
        assert document.from_warehouse_id is not None
        assert document.to_warehouse_id is not None
        if not self.warehouse_repo.get(document.from_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {document.from_warehouse_id} not found")
        if not self.warehouse_repo.get(document.to_warehouse_id):
            raise WarehouseNotFoundError(f"Warehouse {document.to_warehouse_id} not found")

        for item in document.items:
            if self.position_repo:
                self._ensure_positions_balanced(document.from_warehouse_id, item.product_id)
                self._ensure_positions_balanced(document.to_warehouse_id, item.product_id)

                self.position_repo.allocate_and_remove(
                    warehouse_id=document.from_warehouse_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    preferred_position_codes=[
                        "SHIPPING",
                        "STAGING",
                        "STORAGE",
                        "UNASSIGNED",
                        "RECEIVING",
                    ],
                )

                receiving = self.position_repo.get_position_model(document.to_warehouse_id, "RECEIVING")
                self.position_repo.adjust_position_stock(
                    position_id=receiving.id,
                    product_id=item.product_id,
                    delta=item.quantity,
                )

            self.warehouse_repo.remove_product_from_warehouse(
                document.from_warehouse_id, item.product_id, item.quantity
            )
            self.warehouse_repo.add_product_to_warehouse(
                document.to_warehouse_id, item.product_id, item.quantity
            )

    def _get_warehouse_product_quantity(self, warehouse_id: int, product_id: int) -> int:
        items = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
        for row in items:
            if row.product_id == product_id:
                return int(row.quantity)
        return 0

    def _ensure_positions_balanced(self, warehouse_id: int, product_id: int) -> None:
        if not self.position_repo:
            return

        self.position_repo.ensure_default_positions(warehouse_id)
        wh_qty = self._get_warehouse_product_quantity(warehouse_id, product_id)
        pos_total = self.position_repo.get_total_quantity_for_product(warehouse_id, product_id)
        diff = wh_qty - pos_total
        if diff == 0:
            return

        unassigned = self.position_repo.get_position_model(warehouse_id, "UNASSIGNED")
        self.position_repo.adjust_position_stock(
            position_id=unassigned.id, product_id=product_id, delta=diff
        )
        logger.warning(
            f"Reconciled UNASSIGNED for warehouse_id={warehouse_id} product_id={product_id} diff={diff}"
        )
