from __future__ import annotations

import grpc

from shared_utils.events import get_publisher

from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.shared.core.database import get_session

from inventory_service.gen.wms.inventory.v1 import inventory_pb2, inventory_pb2_grpc


class InventoryServiceServicer(inventory_pb2_grpc.InventoryServiceServicer):
    _publisher = get_publisher("inventory-service")

    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "x-request-id":
                return v
        return None

    def _service(self) -> tuple[InventoryService, object]:
        session_gen = get_session()
        db = next(session_gen)
        service = InventoryService(
            inventory_repo=InventoryRepo(db),
            event_publisher=self._publisher,
        )
        return service, db

    def ListInventoryItems(self, request: inventory_pb2.ListInventoryItemsRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            items = service.get_all_inventory_items()
            self._publisher.publish(
                event_type="InventoryListed",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "inventory",
                    "count": len(items),
                },
            )
            return inventory_pb2.ListInventoryItemsResponse(
                items=[
                    inventory_pb2.InventoryItem(product_id=int(i.product_id), quantity=int(i.quantity))
                    for i in items
                ]
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetInventoryByWarehouse(
        self, request: inventory_pb2.GetInventoryByWarehouseRequest, context: grpc.ServicerContext
    ):
        service, db = self._service()
        try:
            rows = service.get_inventory_by_warehouse_rows()
            self._publisher.publish(
                event_type="InventoryByWarehouseListed",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "inventory",
                    "count": len(rows),
                },
            )
            return inventory_pb2.GetInventoryByWarehouseResponse(
                rows=[
                    inventory_pb2.WarehouseInventoryRow(
                        product_id=int(r["product_id"]),
                        warehouse_id=int(r["warehouse_id"]),
                        warehouse_name=str(r["warehouse_name"]),
                        quantity=int(r["quantity"]),
                        # Phase 3: Quantity matrix fields
                        physical_qty=int(r.get("physical_qty", r["quantity"])),
                        reserved_qty=int(r.get("reserved_qty", 0)),
                        incoming_qty=int(r.get("incoming_qty", 0)),
                        in_transit_qty=int(r.get("in_transit_qty", 0)),
                        available_qty=int(r.get("available_qty", r["quantity"])),
                    )
                    for r in rows
                ]
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetProductQuantity(
        self, request: inventory_pb2.GetProductQuantityRequest, context: grpc.ServicerContext
    ):
        service, db = self._service()
        try:
            qty = service.get_total_quantity(int(request.product_id))
            self._publisher.publish(
                event_type="InventoryQuantityRead",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "inventory",
                    "entity_id": int(request.product_id),
                    "product_id": int(request.product_id),
                    "quantity": int(qty),
                },
            )
            return inventory_pb2.GetProductQuantityResponse(product_id=int(request.product_id), quantity=int(qty))
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Product not found")
            return inventory_pb2.GetProductQuantityResponse(product_id=int(request.product_id), quantity=0)
        finally:
            try:
                db.close()
            except Exception:
                pass


add_InventoryServiceServicer_to_server = inventory_pb2_grpc.add_InventoryServiceServicer_to_server
