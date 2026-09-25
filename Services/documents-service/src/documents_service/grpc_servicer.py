from datetime import datetime, timezone
import grpc

from shared_utils.events import get_publisher
from shared_utils.security import sanitize_grpc_error

from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.application.services.wave_service import WaveService
from app.modules.documents.application.services.cycle_count_service import CycleCountService
from app.modules.documents.domain.entities.cycle_count import CycleCountItem
from app.modules.documents.application.services.packing_service import PackingService, PackItem
from app.modules.documents.infrastructure.repositories.document_repo import DocumentRepo
from app.shared.core.database import get_db_session

from documents_service.gen.wms.documents.v1 import documents_pb2, documents_pb2_grpc



class DocumentsServiceServicer(documents_pb2_grpc.DocumentsServiceServicer):
    _publisher = get_publisher("documents-service")

    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "x-request-id":
                return v
        return None

    @staticmethod
    def _user_id(context: grpc.ServicerContext) -> str:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "user-id":
                return v
        return "system"

    def _service(self, db: object) -> DocumentService:
        return DocumentService(
            document_repo=DocumentRepo(db),
            session=db,
            event_publisher=self._publisher,
        )

    @staticmethod
    def _to_proto(doc) -> documents_pb2.Document:  # type: ignore[no-untyped-def]
        proto_kwargs = dict(
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
                    lot_number=str(getattr(i, "lot_number", "") or ""),
                )
                for i in (getattr(doc, "items", []) or [])
            ],
            created_by=str(getattr(doc, "created_by", "") or ""),
            approved_by=str(getattr(doc, "approved_by", "") or ""),
            note=str(getattr(doc, "note", "") or ""),
            created_at=str(getattr(doc, "created_at", "") or ""),
            posted_at=str(getattr(doc, "posted_at", "") or ""),
        )
        if hasattr(documents_pb2.Document, "DESCRIPTOR"):
            field_names = {f.name for f in documents_pb2.Document.DESCRIPTOR.fields}
            if "transaction_type" in field_names:
                proto_kwargs["transaction_type"] = str(getattr(doc, "transaction_type", "") or "")
            if "reason_code" in field_names:
                proto_kwargs["reason_code"] = str(getattr(doc, "reason_code", "") or "")
        return documents_pb2.Document(**proto_kwargs)

    def CreateImport(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            doc = service.create_import_document(
                to_warehouse_id=int(request.to_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
                transaction_type=request.transaction_type if request.transaction_type else None,
                reason_code=request.reason_code if request.reason_code else None,
                request_id=self._request_id(context),
            )
            return self._to_proto(doc)

    def CreateExport(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            doc = service.create_export_document(
                from_warehouse_id=int(request.from_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
                transaction_type=request.transaction_type if request.transaction_type else None,
                reason_code=request.reason_code if request.reason_code else None,
                request_id=self._request_id(context),
            )
            return self._to_proto(doc)

    def CreateSale(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            doc = service.create_sale_document(
                from_warehouse_id=int(request.from_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
                customer_id=int(request.customer_id) if request.customer_id else None,
                transaction_type=request.transaction_type if request.transaction_type else None,
                reason_code=request.reason_code if request.reason_code else None,
                request_id=self._request_id(context),
            )
            return self._to_proto(doc)

    def CreateTransfer(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            doc = service.create_transfer_document(
                from_warehouse_id=int(request.from_warehouse_id),
                to_warehouse_id=int(request.to_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
                transaction_type=request.transaction_type if request.transaction_type else None,
                reason_code=request.reason_code if request.reason_code else None,
                request_id=self._request_id(context),
            )
            return self._to_proto(doc)

    def CreatePurchaseReturn(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            doc = service.create_purchase_return_document(
                from_warehouse_id=int(request.from_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
                transaction_type=request.transaction_type if request.transaction_type else None,
                reason_code=request.reason_code if request.reason_code else None,
                request_id=self._request_id(context),
            )
            return self._to_proto(doc)

    def CreateSalesReturn(self, request: documents_pb2.CreateDocumentRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            doc = service.create_sales_return_document(
                to_warehouse_id=int(request.to_warehouse_id),
                items=[
                    {"product_id": int(i.product_id), "quantity": int(i.quantity), "unit_price": float(i.unit_price)}
                    for i in request.items
                ],
                created_by=request.created_by or "system",
                note=request.note or None,
                customer_id=int(request.customer_id) if request.customer_id else None,
                transaction_type=request.transaction_type if request.transaction_type else None,
                reason_code=request.reason_code if request.reason_code else None,
                request_id=self._request_id(context),
            )
            return self._to_proto(doc)

    def InspectQa(self, request: documents_pb2.InspectQaRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                doc = service.inspect_qa_document(
                    document_id=int(request.document_id),
                    inspected_by=request.inspected_by or "system",
                    passed=request.passed,
                    note=request.note or None,
                    request_id=self._request_id(context),
                )
                return documents_pb2.InspectQaResponse(
                    message="QA inspection completed successfully",
                    document=self._to_proto(doc),
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.InspectQaResponse(message=sanitize_grpc_error(exc))

    def PostDocument(self, request: documents_pb2.PostDocumentRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.post_document(
                    int(request.document_id),
                    request.approved_by or "system",
                    request_id=self._request_id(context),
                )
                return documents_pb2.PostDocumentResponse(
                    message=f"Document {int(request.document_id)} posted successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.PostDocumentResponse(message=str(exc))

    # Phase 7: Approve without stock movement
    def ApproveRequest(self, request: documents_pb2.ApproveRequestRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.approve_request(
                    int(request.document_id),
                    request.approved_by or "system",
                    request_id=self._request_id(context),
                )
                return documents_pb2.ApproveRequestResponse(
                    message=f"Document {int(request.document_id)} approved successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.ApproveRequestResponse(message=str(exc))

    # Phase 8: Sales reservation workflow
    def ReserveRequest(self, request: documents_pb2.ReserveRequestRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.reserve_request_stock(
                    int(request.document_id),
                    request_id=self._request_id(context),
                )
                return documents_pb2.ReserveRequestResponse(
                    message=f"Document {int(request.document_id)} stock reserved successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.ReserveRequestResponse(message=str(exc))

    def ReleaseReservation(self, request: documents_pb2.ReleaseReservationRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.release_request_reservation(
                    int(request.document_id),
                    request_id=self._request_id(context),
                )
                return documents_pb2.ReleaseReservationResponse(
                    message=f"Document {int(request.document_id)} reservation released successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.ReleaseReservationResponse(message=str(exc))

    def GetDocument(self, request: documents_pb2.GetDocumentRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                doc = service.get_document(int(request.document_id))
                return self._to_proto(doc)
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Document not found")
            return documents_pb2.Document()

    def ListDocuments(self, request: documents_pb2.ListDocumentsRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            docs = service.get_documents(
                doc_type=request.doc_type or None,
                page=int(request.page or 1),
                page_size=int(request.page_size or 20),
            )
            return documents_pb2.ListDocumentsResponse(documents=[self._to_proto(d) for d in docs])

    def DeleteDocument(self, request: documents_pb2.DeleteDocumentRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.delete_document(int(request.document_id))
                return documents_pb2.DeleteDocumentResponse(
                    message=f"Document {int(request.document_id)} deleted successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.DeleteDocumentResponse(message=str(exc))

    # Phase 10: Start execution
    def StartExecution(self, request: documents_pb2.StartExecutionRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.start_execution(
                    int(request.document_id),
                    request_id=self._request_id(context),
                )
                return documents_pb2.StartExecutionResponse(
                    message=f"Document {int(request.document_id)} execution started successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.StartExecutionResponse(message=str(exc))

    # Phase 10: Confirm execution
    def ConfirmExecution(self, request: documents_pb2.ConfirmExecutionRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.confirm_execution(
                    int(request.document_id),
                    items=[
                        {"product_id": int(i.product_id), "quantity": int(i.quantity)}
                        for i in request.items
                    ],
                    request_id=self._request_id(context),
                )
                return documents_pb2.ConfirmExecutionResponse(
                    message=f"Document {int(request.document_id)} execution confirmed successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.ConfirmExecutionResponse(message=str(exc))

    # Phase 10: Complete request
    def CompleteRequest(self, request: documents_pb2.CompleteRequestRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.complete_request(
                    int(request.document_id),
                    completed_by=self._user_id(context),
                    request_id=self._request_id(context),
                )
                return documents_pb2.CompleteRequestResponse(
                    message=f"Document {int(request.document_id)} completed successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.CompleteRequestResponse(message=str(exc))

    def RevertToInProgress(self, request: documents_pb2.RevertToInProgressRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                service.revert_to_in_progress(
                    int(request.document_id),
                    request_id=self._request_id(context),
                )
                return documents_pb2.RevertToInProgressResponse(
                    message=f"Document {int(request.document_id)} reverted to IN_PROGRESS successfully"
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.RevertToInProgressResponse(message=str(exc))

    # Phase 10: Wave Picking
    def CreateWave(self, request: documents_pb2.CreateWaveRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = WaveService(session=db)
                try:
                    cutoff = datetime.fromisoformat(request.dispatch_cutoff)
                except Exception:
                    cutoff = datetime.now(timezone.utc)
                wave = service.create_wave(
                    wave_id=request.wave_id,
                    carrier=request.carrier,
                    dispatch_cutoff=cutoff,
                    max_orders=request.max_orders or 50,
                )
                return documents_pb2.WaveResponse(
                    wave_id=wave.wave_id,
                    carrier=wave.carrier,
                    dispatch_cutoff=wave.dispatch_cutoff.isoformat() if hasattr(wave.dispatch_cutoff, "isoformat") else str(wave.dispatch_cutoff),
                    max_orders=wave.max_orders,
                    status=wave.status.value if hasattr(wave.status, "value") else str(wave.status),
                    order_count=len(wave.orders),
                    created_at=wave.created_at.isoformat() if hasattr(wave.created_at, "isoformat") else str(wave.created_at),
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.WaveResponse(wave_id=request.wave_id)

    def GetWave(self, request: documents_pb2.GetWaveRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = WaveService(session=db)
                wave = service.get_wave(request.wave_id)
                return documents_pb2.WaveResponse(
                    wave_id=wave.wave_id,
                    carrier=wave.carrier,
                    dispatch_cutoff=wave.dispatch_cutoff.isoformat() if hasattr(wave.dispatch_cutoff, "isoformat") else str(wave.dispatch_cutoff),
                    max_orders=wave.max_orders,
                    status=wave.status.value if hasattr(wave.status, "value") else str(wave.status),
                    order_count=len(wave.orders),
                    created_at=wave.created_at.isoformat() if hasattr(wave.created_at, "isoformat") else str(wave.created_at),
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.NOT_FOUND if "not found" in str(exc).lower() else grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.WaveResponse(wave_id=request.wave_id)

    # Phase 10: Cycle Counting
    def CreateCycleCount(self, request: documents_pb2.CreateCycleCountRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = CycleCountService(session=db)
                items = [
                    CycleCountItem(
                        item_id=i.item_id,
                        product_id=int(i.product_id),
                        location_id=i.location_id,
                        system_qty=int(i.system_qty),
                        counted_qty=int(i.counted_qty) if i.counted_qty > 0 else None,
                        lot_number=i.lot_number or "",
                        unit_cost=float(i.unit_cost) if i.unit_cost else 0.0,
                    )
                    for i in request.items
                ]
                sheet = service.create_cycle_count_sheet(
                    cycle_count_id=request.cycle_count_id,
                    warehouse_id=int(request.warehouse_id),
                    title=request.title,
                    items=items,
                    assigned_to=request.assigned_to or None,
                    discrepancy_qty_threshold=request.discrepancy_qty_threshold,
                    discrepancy_value_threshold=request.discrepancy_value_threshold,
                    created_by=request.created_by or "system",
                    note=request.note or None,
                )
                return documents_pb2.CycleCountResponse(
                    cycle_count_id=sheet.cycle_count_id,
                    warehouse_id=sheet.warehouse_id,
                    title=sheet.title,
                    status=sheet.status.value if hasattr(sheet.status, "value") else str(sheet.status),
                    assigned_to=sheet.assigned_to or "",
                    discrepancy_qty_threshold=sheet.discrepancy_qty_threshold,
                    discrepancy_value_threshold=sheet.discrepancy_value_threshold,
                    created_by=sheet.created_by or "",
                    note=sheet.note or "",
                    items=[
                        documents_pb2.CycleCountItemProto(
                            item_id=item.item_id,
                            product_id=int(item.product_id),
                            location_id=str(item.location_id),
                            system_qty=int(item.system_qty),
                            counted_qty=int(item.counted_qty) if item.counted_qty is not None else 0,
                            lot_number=str(item.lot_number or ""),
                            unit_cost=float(item.unit_cost or 0.0),
                        )
                        for item in sheet.items
                    ],
                    created_at=sheet.created_at.isoformat() if hasattr(sheet.created_at, "isoformat") else str(sheet.created_at),
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.CycleCountResponse(cycle_count_id=request.cycle_count_id)

    def GetCycleCount(self, request: documents_pb2.GetCycleCountRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = CycleCountService(session=db)
                sheet = service.get_sheet(request.cycle_count_id)
                return documents_pb2.CycleCountResponse(
                    cycle_count_id=sheet.cycle_count_id,
                    warehouse_id=sheet.warehouse_id,
                    title=sheet.title,
                    status=sheet.status.value if hasattr(sheet.status, "value") else str(sheet.status),
                    assigned_to=sheet.assigned_to or "",
                    discrepancy_qty_threshold=sheet.discrepancy_qty_threshold,
                    discrepancy_value_threshold=sheet.discrepancy_value_threshold,
                    created_by=sheet.created_by or "",
                    note=sheet.note or "",
                    items=[
                        documents_pb2.CycleCountItemProto(
                            item_id=item.item_id,
                            product_id=int(item.product_id),
                            location_id=str(item.location_id),
                            system_qty=int(item.system_qty),
                            counted_qty=int(item.counted_qty) if item.counted_qty is not None else 0,
                            lot_number=str(item.lot_number or ""),
                            unit_cost=float(item.unit_cost or 0.0),
                        )
                        for item in sheet.items
                    ],
                    created_at=sheet.created_at.isoformat() if hasattr(sheet.created_at, "isoformat") else str(sheet.created_at),
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.NOT_FOUND if "not found" in str(exc).lower() else grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.CycleCountResponse(cycle_count_id=request.cycle_count_id)

    # Phase 10: Packing & Check-Weigher
    def VerifyPacking(self, request: documents_pb2.VerifyPackingRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                tolerance = float(request.override_tolerance_g) if request.override_tolerance_g > 0 else 50.0
                service = PackingService(tolerance_g=tolerance, session=db)
                if request.items and not service._repo.exists(request.carton_id):
                    service.create_carton(
                        carton_id=request.carton_id,
                        order_id=request.order_id or request.carton_id,
                        items=[
                            PackItem(
                                product_id=str(i.product_id),
                                sku=str(i.sku),
                                quantity=int(i.quantity),
                                unit_weight_g=float(i.unit_weight_g),
                            )
                            for i in request.items
                        ],
                        packaging_tare_weight_g=float(request.packaging_tare_weight_g) if request.packaging_tare_weight_g > 0 else 100.0,
                    )
                result = service.verify_check_weigher(
                    carton_id=request.carton_id,
                    measured_weight_g=float(request.measured_weight_g),
                    override_tolerance_g=tolerance if request.override_tolerance_g > 0 else None,
                )
                carton = service.get_carton(request.carton_id)
                return documents_pb2.VerifyPackingResponse(
                    carton_id=result.carton_id,
                    theoretical_weight_g=result.theoretical_weight_g,
                    measured_weight_g=result.measured_weight_g,
                    deviation_g=result.deviation_g,
                    is_valid=result.is_valid,
                    allowed_tolerance_g=result.allowed_tolerance_g,
                    message=result.message,
                    status=carton.status.value if hasattr(carton.status, "value") else str(carton.status),
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return documents_pb2.VerifyPackingResponse(
                carton_id=request.carton_id,
                message=str(exc),
                is_valid=False,
            )



add_DocumentsServiceServicer_to_server = documents_pb2_grpc.add_DocumentsServiceServicer_to_server
