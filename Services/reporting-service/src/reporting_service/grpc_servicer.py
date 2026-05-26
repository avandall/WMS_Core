from __future__ import annotations

import json

import grpc

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

    def InventoryReport(self, request: reporting_pb2.InventoryReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        return reporting_pb2.JsonResponse(
            json=self._json(
                {
                    "report_type": "inventory",
                    "source": "reporting_read_model",
                    "warehouse_id": int(request.warehouse_id) if request.warehouse_id else None,
                    "low_stock_threshold": int(request.low_stock_threshold or 10),
                    "items": [],
                }
            )
        )

    def InventoryList(self, request: reporting_pb2.InventoryListRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        return reporting_pb2.JsonResponse(json=self._json([]))

    def WarehouseReport(self, request: reporting_pb2.WarehouseReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        return reporting_pb2.JsonResponse(
            json=self._json(
                {
                    "report_type": "warehouse",
                    "source": "reporting_read_model",
                    "warehouse_id": int(request.warehouse_id) if request.warehouse_id else None,
                    "items": [],
                }
            )
        )

    def DocumentsReport(self, request: reporting_pb2.DocumentsReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        return reporting_pb2.JsonResponse(
            json=self._json(
                {
                    "report_type": "documents",
                    "source": "reporting_read_model",
                    "documents": [],
                }
            )
        )

    def ProductReport(self, request: reporting_pb2.ProductReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        return reporting_pb2.JsonResponse(
            json=self._json(
                {
                    "report_type": "product",
                    "source": "reporting_read_model",
                    "product_id": int(request.product_id) if request.product_id else None,
                    "items": [],
                }
            )
        )

    def SalesReport(self, request: reporting_pb2.SalesReportRequest, context: grpc.ServicerContext):
        _ = self._request_id(context)
        return reporting_pb2.JsonResponse(
            json=self._json(
                {
                    "report_type": "sales",
                    "source": "reporting_read_model",
                    "customer_id": int(request.customer_id) if request.customer_id else None,
                    "salesperson": request.salesperson or None,
                    "items": [],
                }
            )
        )


add_ReportingServiceServicer_to_server = reporting_pb2_grpc.add_ReportingServiceServicer_to_server
