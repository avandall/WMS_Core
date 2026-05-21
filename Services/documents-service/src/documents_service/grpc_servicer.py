from __future__ import annotations

import grpc

from shared_utils.events import get_publisher

from app.modules.audit.infrastructure.repositories.audit_event_repo import AuditEventRepo
from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.infrastructure.repositories.document_repo import DocumentRepo
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.positions.infrastructure.repositories.position_repo import PositionRepo
from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.shared.core.database import get_session

from documents_service.gen.wms.documents.v1 import documents_pb2, documents_pb2_grpc


class DocumentsServiceServicer(documents_pb2_grpc.DocumentsServiceServicer):
    _publisher = get_publisher("documents-service")

    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "x-request-id":
                return v
        return None

    def _service(self) -> tuple[DocumentService, object]:
        session_gen = get_session()
        db = next(session_gen)
        service = DocumentService(
            document_repo=DocumentRepo(db),
            warehouse_repo=WarehouseRepo(db),
            product_repo=ProductRepo(db),
            inventory_repo=InventoryRepo(db),
            customer_repo=CustomerRepo(db),
            position_repo=PositionRepo(db),
            audit_event_repo=AuditEventRepo(db),
            session=db,
        )
        return service, db

    @staticmethod
    def _to_proto(doc) -> documents_pb2.Document:  # type: ignore[no-untyped-def]
        return documents_pb2.Document(
            document_id=int(getattr(doc, "document_id", 0) or 0),
            doc_type=str(getattr(doc, "doc_type", "") or getattr(getattr(doc, "doc_type", None), "value", "")),
            status=str(getattr(doc, "status", "") or getattr(getattr(doc, "status", None), "value", "")),
            from_warehouse_id=int(getattr(doc, "from_warehouse_id", 0) or 0),
            to_warehouse_id=int(getattr(doc, "to_warehouse_id", 0) or 0),
            customer_id=int(getattr(doc, "customer_id", 0) or 0),
            items=[
                documents_pb2.DocumentItem(
                    product_id=int(i.product_id),
                    quantity=int(i.quantity),
                    unit_price=float(getattr(i, "unit_price", 0) or 0),
                )
                for i in (getattr(doc, "items", []) or [])
            ],
            created_by=str(getattr(doc, "created_by", "") or ""),
            approved_by=str(getattr(doc, "approved_by", "") or ""),
            note=str(getattr(doc, "note", "") or ""),
            created_at=str(getattr(doc, "created_at", "") or ""),
            posted_at=str(getattr(doc, "posted_at", "") or ""),
        )

    def CreateImport(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            doc = service.create_import_document(
                to_warehouse_id=int(request.to_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
            )
            self._publisher.publish(
                event_type="DocumentUploaded",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "document",
                    "entity_id": int(doc.document_id),
                    "doc_type": "IMPORT",
                    "document_id": int(doc.document_id),
                },
            )
            return self._to_proto(doc)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def CreateExport(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            doc = service.create_export_document(
                from_warehouse_id=int(request.from_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
            )
            self._publisher.publish(
                event_type="DocumentUploaded",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "document",
                    "entity_id": int(doc.document_id),
                    "doc_type": "EXPORT",
                    "document_id": int(doc.document_id),
                },
            )
            return self._to_proto(doc)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def CreateSale(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            doc = service.create_sale_document(
                from_warehouse_id=int(request.from_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
                customer_id=int(request.customer_id) if request.customer_id else None,
            )
            self._publisher.publish(
                event_type="DocumentUploaded",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "document",
                    "entity_id": int(doc.document_id),
                    "doc_type": "SALE",
                    "document_id": int(doc.document_id),
                    "customer_id": int(request.customer_id) if request.customer_id else None,
                },
            )
            return self._to_proto(doc)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def CreateTransfer(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            doc = service.create_transfer_document(
                from_warehouse_id=int(request.from_warehouse_id),
                to_warehouse_id=int(request.to_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
            )
            self._publisher.publish(
                event_type="DocumentUploaded",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "document",
                    "entity_id": int(doc.document_id),
                    "doc_type": "TRANSFER",
                    "document_id": int(doc.document_id),
                },
            )
            return self._to_proto(doc)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def PostDocument(self, request: documents_pb2.PostDocumentRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            service.post_document(int(request.document_id), request.approved_by or "system")
            self._publisher.publish(
                event_type="DocumentPosted",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "document",
                    "entity_id": int(request.document_id),
                    "document_id": int(request.document_id),
                    "approved_by": request.approved_by,
                },
            )
            return documents_pb2.PostDocumentResponse(
                message=f"Document {int(request.document_id)} posted successfully"
            )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(exc))
            return documents_pb2.PostDocumentResponse(message=str(exc))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetDocument(self, request: documents_pb2.GetDocumentRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            doc = service.get_document(int(request.document_id))
            return self._to_proto(doc)
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Document not found")
            return documents_pb2.Document()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def ListDocuments(self, request: documents_pb2.ListDocumentsRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            docs = service.get_documents(
                doc_type=request.doc_type or None,
                page=int(request.page or 1),
                page_size=int(request.page_size or 20),
            )
            return documents_pb2.ListDocumentsResponse(documents=[self._to_proto(d) for d in docs])
        finally:
            try:
                db.close()
            except Exception:
                pass

    def DeleteDocument(self, request: documents_pb2.DeleteDocumentRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            service.delete_document(int(request.document_id))
            return documents_pb2.DeleteDocumentResponse(
                message=f"Document {int(request.document_id)} deleted successfully"
            )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(exc))
            return documents_pb2.DeleteDocumentResponse(message=str(exc))
        finally:
            try:
                db.close()
            except Exception:
                pass


add_DocumentsServiceServicer_to_server = documents_pb2_grpc.add_DocumentsServiceServicer_to_server
