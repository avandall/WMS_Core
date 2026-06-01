from __future__ import annotations

import grpc

from shared_utils.events import get_publisher

from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.shared.core.database import get_session

from warehouse_service.gen.wms.warehouse.v1 import warehouse_pb2, warehouse_pb2_grpc


class WarehouseServiceServicer(warehouse_pb2_grpc.WarehouseServiceServicer):
    _publisher = get_publisher("warehouse-service")

    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "x-request-id":
                return v
        return None

    def _service(self) -> tuple[WarehouseService, object]:
        session_gen = get_session()
        db = next(session_gen)
        return WarehouseService(WarehouseRepo(db), session=db), db

    def ListWarehouses(self, request: warehouse_pb2.ListWarehousesRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            warehouses = service.get_all_warehouses()
            rows = [
                warehouse_pb2.Warehouse(
                    warehouse_id=int(w.warehouse_id),
                    name=w.location or "",
                    location=w.location or "",
                )
                for w in warehouses
            ]
            return warehouse_pb2.ListWarehousesResponse(warehouses=rows)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetWarehouse(self, request: warehouse_pb2.GetWarehouseRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            w = service.get_warehouse(int(request.warehouse_id))
            return warehouse_pb2.Warehouse(
                warehouse_id=int(w.warehouse_id),
                name=w.location or "",
                location=w.location or "",
            )
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Warehouse not found")
            return warehouse_pb2.Warehouse()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def CreateWarehouse(self, request: warehouse_pb2.CreateWarehouseRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            w = service.create_warehouse(request.name)
            self._publisher.publish(
                event_type="WarehouseCreated",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "warehouse",
                    "entity_id": int(w.warehouse_id),
                    "warehouse_id": int(w.warehouse_id),
                    "location": w.location,
                },
            )
            return warehouse_pb2.Warehouse(
                warehouse_id=int(w.warehouse_id),
                name=w.location or "",
                location=w.location or "",
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def DeleteWarehouse(self, request: warehouse_pb2.DeleteWarehouseRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            warehouse_id = int(request.warehouse_id)
            service.delete_warehouse(warehouse_id)
            self._publisher.publish(
                event_type="WarehouseDeleted",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "warehouse",
                    "entity_id": warehouse_id,
                    "warehouse_id": warehouse_id,
                },
            )
            return warehouse_pb2.DeleteWarehouseResponse(
                message=f"Warehouse {warehouse_id} deleted successfully"
            )
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Warehouse not found")
            return warehouse_pb2.DeleteWarehouseResponse(message="Warehouse not found")
        finally:
            try:
                db.close()
            except Exception:
                pass

    def TransferAllInventory(
        self, request: warehouse_pb2.TransferAllInventoryRequest, context: grpc.ServicerContext
    ):
        service, db = self._service()
        try:
            service.transfer_all_inventory(int(request.warehouse_id), int(request.to_warehouse_id))
            return warehouse_pb2.TransferAllInventoryResponse(
                from_warehouse_id=int(request.warehouse_id),
                to_warehouse_id=int(request.to_warehouse_id),
                transferred_items=[],
                message="Warehouse inventory ownership moved to inventory-service",
            )
        finally:
            try:
                db.close()
            except Exception:
                pass


class WarehouseOperationsServiceServicer(warehouse_pb2_grpc.WarehouseOperationsServiceServicer):
    def _repo(self) -> tuple[WarehouseRepo, object]:
        session_gen = get_session()
        db = next(session_gen)
        return WarehouseRepo(db), db

    def GetSystemOverview(self, request: warehouse_pb2.GetSystemOverviewRequest, context: grpc.ServicerContext):
        repo, db = self._repo()
        try:
            warehouses = repo.get_all()
            return warehouse_pb2.SystemOverview(
                total_warehouses=len(warehouses),
                total_products=0,
                total_inventory_value=0,
                warehouses=[str(w) for w in warehouses.values()],
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetInventoryHealth(self, request: warehouse_pb2.GetInventoryHealthRequest, context: grpc.ServicerContext):
        _repo, db = self._repo()
        try:
            return warehouse_pb2.InventoryHealthReport(system_health_score=0, warehouses=[])
        finally:
            try:
                db.close()
            except Exception:
                pass

    def OptimizeDistribution(
        self, request: warehouse_pb2.OptimizeDistributionRequest, context: grpc.ServicerContext
    ):
        _repo, db = self._repo()
        try:
            return warehouse_pb2.OptimizeDistributionResponse(
                product_id=int(request.product_id),
                product_name="",
                distribution=[],
                recommendations=["Inventory distribution is owned by inventory/reporting projections"],
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def BulkTransfer(self, request: warehouse_pb2.BulkTransferRequest, context: grpc.ServicerContext):
        _repo, db = self._repo()
        try:
            return warehouse_pb2.BulkTransferResponse(
                total_transfers=len(request.transfers),
                successful=0,
                failed=len(request.transfers),
            )
        finally:
            try:
                db.close()
            except Exception:
                pass


add_WarehouseServiceServicer_to_server = warehouse_pb2_grpc.add_WarehouseServiceServicer_to_server
add_WarehouseOperationsServiceServicer_to_server = (
    warehouse_pb2_grpc.add_WarehouseOperationsServiceServicer_to_server
)
