from __future__ import annotations

import json

import grpc

from app.modules.reporting.infrastructure.repositories.read_model_repo import ReportingReadModelRepo
from app.shared.core.database import SessionLocal

from reporting_service.gen.wms.reporting.v1 import reporting_pb2, reporting_pb2_grpc


class ReportingServiceServicer(reporting_pb2_grpc.ReportingServiceServicer):
    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "x-request-id":
                return v
        return None

    @staticmethod
    def _json(obj) -> str:  # type: ignore[no-untyped-def]
        return json.dumps(obj, ensure_ascii=False, default=str)

    @staticmethod
    def _repo() -> tuple[ReportingReadModelRepo, object]:
        db = SessionLocal()
        return ReportingReadModelRepo(db), db

    def InventoryReport(self, request: reporting_pb2.InventoryReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        repo, db = self._repo()
        try:
            return reporting_pb2.JsonResponse(
                json=self._json(
                    repo.inventory_report(
                        warehouse_id=int(request.warehouse_id) if request.warehouse_id else None,
                        low_stock_threshold=int(request.low_stock_threshold or 10),
                    )
                )
            )
        finally:
            db.close()

    def InventoryList(self, request: reporting_pb2.InventoryListRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        repo, db = self._repo()
        try:
            return reporting_pb2.JsonResponse(json=self._json(repo.inventory_list()))
        finally:
            db.close()

    def WarehouseReport(self, request: reporting_pb2.WarehouseReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        repo, db = self._repo()
        try:
            return reporting_pb2.JsonResponse(
                json=self._json(
                    repo.warehouse_report(
                        warehouse_id=int(request.warehouse_id) if request.warehouse_id else None
                    )
                )
            )
        finally:
            db.close()

    def DocumentsReport(self, request: reporting_pb2.DocumentsReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        repo, db = self._repo()
        try:
            return reporting_pb2.JsonResponse(json=self._json(repo.documents_report()))
        finally:
            db.close()

    def ProductReport(self, request: reporting_pb2.ProductReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        repo, db = self._repo()
        try:
            return reporting_pb2.JsonResponse(
                json=self._json(
                    repo.product_report(product_id=int(request.product_id) if request.product_id else None)
                )
            )
        finally:
            db.close()

    def SalesReport(self, request: reporting_pb2.SalesReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        repo, db = self._repo()
        try:
            return reporting_pb2.JsonResponse(
                json=self._json(
                    repo.sales_report(
                        customer_id=int(request.customer_id) if request.customer_id else None,
                        salesperson=request.salesperson or None,
                    )
                )
            )
        finally:
            db.close()


add_ReportingServiceServicer_to_server = reporting_pb2_grpc.add_ReportingServiceServicer_to_server
