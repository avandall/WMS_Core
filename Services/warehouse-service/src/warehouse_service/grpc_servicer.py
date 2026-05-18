from __future__ import annotations

import grpc

from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
from app.modules.warehouses.application.services.warehouse_operations_service import (
    WarehouseOperationsService,
)
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.shared.core.database import get_session

from warehouse_service.gen.wms.warehouse.v1 import warehouse_pb2, warehouse_pb2_grpc


class _NullDocumentRepo:
    def save(self, document):  # type: ignore[no-untyped-def]
        return None

    def get(self, document_id: int):  # type: ignore[no-untyped-def]
        return None

    def get_all(self):  # type: ignore[no-untyped-def]
        return []

    def update_status(self, document_id: int, new_status):  # type: ignore[no-untyped-def]
        return None

    def delete(self, document_id: int) -> None:
        return None


class WarehouseServiceServicer(warehouse_pb2_grpc.WarehouseServiceServicer):
    def _service(self) -> tuple[WarehouseService, object]:
        session_gen = get_session()
        db = next(session_gen)
        return WarehouseService(WarehouseRepo(db), ProductRepo(db), InventoryRepo(db)), db

    def ListWarehouses(self, request: warehouse_pb2.ListWarehousesRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            warehouses = service.get_all_warehouses()
            rows = []
            for w in warehouses:
                inventory = service.get_warehouse_inventory(w.warehouse_id)
                rows.append(
                    warehouse_pb2.Warehouse(
                        warehouse_id=int(w.warehouse_id),
                        name=w.location or "",
                        location=w.location or "",
                        inventory=[
                            warehouse_pb2.InventoryItem(product_id=int(i.product_id), quantity=int(i.quantity))
                            for i in inventory
                        ],
                    )
                )
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
            inventory = service.get_warehouse_inventory(int(request.warehouse_id))
            return warehouse_pb2.Warehouse(
                warehouse_id=int(w.warehouse_id),
                name=w.location or "",
                location=w.location or "",
                inventory=[
                    warehouse_pb2.InventoryItem(product_id=int(i.product_id), quantity=int(i.quantity))
                    for i in inventory
                ],
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
            service.delete_warehouse(int(request.warehouse_id))
            return warehouse_pb2.DeleteWarehouseResponse(
                message=f"Warehouse {int(request.warehouse_id)} deleted successfully"
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
            transferred = service.transfer_all_inventory(int(request.warehouse_id), int(request.to_warehouse_id))
            return warehouse_pb2.TransferAllInventoryResponse(
                from_warehouse_id=int(request.warehouse_id),
                to_warehouse_id=int(request.to_warehouse_id),
                transferred_items=[
                    warehouse_pb2.InventoryItem(product_id=int(i.product_id), quantity=int(i.quantity))
                    for i in transferred
                ],
                message=f"Successfully transferred {len(transferred)} product(s) from warehouse {int(request.warehouse_id)} to {int(request.to_warehouse_id)}",
            )
        finally:
            try:
                db.close()
            except Exception:
                pass


class WarehouseOperationsServiceServicer(warehouse_pb2_grpc.WarehouseOperationsServiceServicer):
    def _service(self) -> tuple[WarehouseOperationsService, object]:
        session_gen = get_session()
        db = next(session_gen)
        service = WarehouseOperationsService(
            warehouse_repo=WarehouseRepo(db),
            product_repo=ProductRepo(db),
            inventory_repo=InventoryRepo(db),
            document_repo=_NullDocumentRepo(),
        )
        return service, db

    def GetSystemOverview(self, request: warehouse_pb2.GetSystemOverviewRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            data = service.get_system_overview()
            return warehouse_pb2.SystemOverview(
                total_warehouses=int(data.get("total_warehouses") or 0),
                total_products=int(data.get("total_products") or 0),
                total_inventory_value=float(data.get("total_inventory_value") or 0),
                warehouses=[str(w) for w in (data.get("warehouses") or [])],
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetInventoryHealth(self, request: warehouse_pb2.GetInventoryHealthRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            data = service.get_inventory_health_report()
            warehouses = []
            for w in data.get("warehouses") or []:
                products = []
                for p in w.get("products") or []:
                    products.append(
                        warehouse_pb2.InventoryHealthProduct(
                            product_id=int(p.get("product_id") or 0),
                            name=str(p.get("name") or ""),
                            quantity=int(p.get("quantity") or 0),
                            value=float(p.get("value") or 0),
                        )
                    )
                warehouses.append(
                    warehouse_pb2.InventoryHealthWarehouse(
                        warehouse_id=int(w.get("warehouse_id") or 0),
                        location=str(w.get("location") or ""),
                        total_value=float(w.get("total_value") or 0),
                        health_score=float(w.get("health_score") or 0),
                        products=products,
                    )
                )
            return warehouse_pb2.InventoryHealthReport(
                system_health_score=float(data.get("system_health_score") or 0),
                warehouses=warehouses,
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def OptimizeDistribution(
        self, request: warehouse_pb2.OptimizeDistributionRequest, context: grpc.ServicerContext
    ):
        service, db = self._service()
        try:
            data = service.optimize_inventory_distribution(int(request.product_id))
            if "error" in data:
                return warehouse_pb2.OptimizeDistributionResponse(error=str(data["error"]))
            dist = []
            for d in data.get("distribution") or []:
                dist.append(
                    warehouse_pb2.DistributionItem(
                        warehouse_id=int(d.get("warehouse_id") or 0),
                        location=str(d.get("location") or ""),
                        quantity=int(d.get("quantity") or 0),
                    )
                )
            return warehouse_pb2.OptimizeDistributionResponse(
                product_id=int(data.get("product_id") or 0),
                product_name=str(data.get("product_name") or ""),
                distribution=dist,
                recommendations=[str(r) for r in (data.get("recommendations") or [])],
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def BulkTransfer(self, request: warehouse_pb2.BulkTransferRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            transfers = []
            for t in request.transfers:
                transfers.append(
                    {
                        "from_warehouse_id": int(t.from_warehouse_id),
                        "to_warehouse_id": int(t.to_warehouse_id),
                        "product_id": int(t.product_id),
                        "quantity": int(t.quantity),
                    }
                )
            data = service.bulk_transfer_products(transfers)
            return warehouse_pb2.BulkTransferResponse(
                total_transfers=int(data.get("total_transfers") or 0),
                successful=int(data.get("successful") or 0),
                failed=int(data.get("failed") or 0),
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

