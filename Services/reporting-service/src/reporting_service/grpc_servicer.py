from __future__ import annotations

import json
from datetime import date

import grpc

from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
from app.modules.documents.infrastructure.repositories.document_repo import DocumentRepo
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.shared.application.services.report_orchestrator import ReportOrchestrator
from app.shared.core.database import get_session

from reporting_service.gen.wms.reporting.v1 import reporting_pb2, reporting_pb2_grpc


class ReportingServiceServicer(reporting_pb2_grpc.ReportingServiceServicer):
    def _service(self) -> tuple[ReportOrchestrator, object]:
        session_gen = get_session()
        db = next(session_gen)
        svc = ReportOrchestrator(
            product_repo=ProductRepo(db),
            document_repo=DocumentRepo(db),
            warehouse_repo=WarehouseRepo(db),
            inventory_repo=InventoryRepo(db),
            customer_repo=CustomerRepo(db),
        )
        return svc, db

    @staticmethod
    def _json(obj) -> str:  # type: ignore[no-untyped-def]
        return json.dumps(obj, ensure_ascii=False, default=str)

    def InventoryReport(self, request: reporting_pb2.InventoryReportRequest, context: grpc.ServicerContext):
        svc, db = self._service()
        try:
            data = svc.generate_inventory_report(
                warehouse_id=int(request.warehouse_id) if request.warehouse_id else None,
                low_stock_threshold=int(request.low_stock_threshold or 10),
            )
            return reporting_pb2.JsonResponse(json=self._json(data))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def InventoryList(self, request: reporting_pb2.InventoryListRequest, context: grpc.ServicerContext):
        svc, db = self._service()
        try:
            data = svc.list_inventory_by_warehouse()
            return reporting_pb2.JsonResponse(json=self._json(data))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def WarehouseReport(self, request: reporting_pb2.WarehouseReportRequest, context: grpc.ServicerContext):
        svc, db = self._service()
        try:
            start = date.fromisoformat(request.start_date) if request.start_date else None
            end = date.fromisoformat(request.end_date) if request.end_date else None
            data = svc.generate_warehouse_performance_report(
                warehouse_id=int(request.warehouse_id),
                start_date=start,
                end_date=end,
            )
            return reporting_pb2.JsonResponse(json=self._json(data))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def DocumentsReport(self, request: reporting_pb2.DocumentsReportRequest, context: grpc.ServicerContext):
        svc, db = self._service()
        try:
            start = date.fromisoformat(request.start_date) if request.start_date else None
            end = date.fromisoformat(request.end_date) if request.end_date else None
            data = svc.list_documents_report(start_date=start, end_date=end)
            return reporting_pb2.JsonResponse(json=self._json(data))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def ProductReport(self, request: reporting_pb2.ProductReportRequest, context: grpc.ServicerContext):
        svc, db = self._service()
        try:
            start = date.fromisoformat(request.start_date) if request.start_date else None
            end = date.fromisoformat(request.end_date) if request.end_date else None
            data = svc.generate_product_movement_report(
                product_id=int(request.product_id),
                start_date=start,
                end_date=end,
            )
            return reporting_pb2.JsonResponse(json=self._json(data))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def SalesReport(self, request: reporting_pb2.SalesReportRequest, context: grpc.ServicerContext):
        svc, db = self._service()
        try:
            start = date.fromisoformat(request.start_date) if request.start_date else None
            end = date.fromisoformat(request.end_date) if request.end_date else None
            data = svc.generate_sales_report(
                start_date=start,
                end_date=end,
                customer_id=int(request.customer_id) if request.customer_id else None,
                salesperson=request.salesperson or None,
            )
            return reporting_pb2.JsonResponse(json=self._json(data))
        finally:
            try:
                db.close()
            except Exception:
                pass


add_ReportingServiceServicer_to_server = reporting_pb2_grpc.add_ReportingServiceServicer_to_server

