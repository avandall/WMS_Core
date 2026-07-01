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

    # Phase 5: Availability and reservations
    def GetAvailability(
        self, request: inventory_pb2.GetAvailabilityRequest, context: grpc.ServicerContext
    ):
        service, db = self._service()
        try:
            availability = service.inventory_repo.calculate_available_stock(
                product_id=int(request.product_id), warehouse_id=int(request.warehouse_id)
            )
            self._publisher.publish(
                event_type="AvailabilityRequested",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "inventory",
                    "product_id": int(request.product_id),
                    "warehouse_id": int(request.warehouse_id),
                },
            )
            return inventory_pb2.GetAvailabilityResponse(
                product_id=int(request.product_id),
                warehouse_id=int(request.warehouse_id),
                physical_qty=availability["physical_qty"],
                reserved_qty=availability["reserved_qty"],
                available_qty=availability["available_qty"],
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def ListReservations(
        self, request: inventory_pb2.ListReservationsRequest, context: grpc.ServicerContext
    ):
        service, db = self._service()
        try:
            # In proto3, HasField() only works on message/oneof fields, not scalars.
            # Use the default zero-value as the sentinel for "not set".
            product_id = int(request.product_id) if request.product_id != 0 else None
            warehouse_id = int(request.warehouse_id) if request.warehouse_id != 0 else None
            status = request.status if request.status else None

            reservations = service.inventory_repo.list_reservations(
                product_id=product_id,
                warehouse_id=warehouse_id,
                status=status,
            )
            self._publisher.publish(
                event_type="ReservationsListed",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "inventory",
                    "count": len(reservations),
                },
            )
            return inventory_pb2.ListReservationsResponse(
                reservations=[
                    inventory_pb2.ReservationRow(
                        id=int(r["id"]),
                        source_type=r["source_type"],
                        source_id=int(r["source_id"]) if r["source_id"] else 0,
                        document_id=int(r["document_id"]) if r["document_id"] else 0,
                        product_id=int(r["product_id"]),
                        warehouse_id=int(r["warehouse_id"]),
                        requested_qty=int(r["requested_qty"]),
                        reserved_qty=int(r["reserved_qty"]),
                        released_qty=int(r["released_qty"]),
                        consumed_qty=int(r["consumed_qty"]),
                        status=r["status"],
                        expires_at=r["expires_at"] or "",
                        created_by=r["created_by"] or "",
                        created_at=r["created_at"] or "",
                    )
                    for r in reservations
                ]
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def ReleaseReservation(
        self, request: inventory_pb2.ReleaseReservationRequest, context: grpc.ServicerContext
    ):
        service, db = self._service()
        try:
            # In proto3, 0 is the default for int64; treat 0 as "release all".
            released_qty = int(request.released_qty) if request.released_qty != 0 else None
            service.release_reservation(reservation_id=int(request.reservation_id), released_qty=released_qty)
            self._publisher.publish(
                event_type="ReservationReleased",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "inventory",
                    "reservation_id": int(request.reservation_id),
                    "released_qty": released_qty,
                },
            )
            return inventory_pb2.ReleaseReservationResponse(success=True)
        except Exception:
            return inventory_pb2.ReleaseReservationResponse(success=False)
        finally:
            try:
                db.close()
            except Exception:
                pass

    # Phase 9: Inventory transaction ledger
    def ListTransactions(
        self, request: inventory_pb2.ListTransactionsRequest, context: grpc.ServicerContext
    ):
        service, db = self._service()
        try:
            # In proto3, HasField() raises ValueError on scalar fields.
            # Use zero-value convention: 0 means "no filter", "" means "no filter".
            transactions = service.inventory_repo.list_transactions(
                document_id=int(request.document_id) if request.document_id != 0 else None,
                product_id=int(request.product_id) if request.product_id != 0 else None,
                warehouse_id=int(request.warehouse_id) if request.warehouse_id != 0 else None,
                transaction_type=request.transaction_type if request.transaction_type else None,
                limit=int(request.limit) if request.limit != 0 else 100,
                offset=int(request.offset) if request.offset != 0 else 0,
            )

            transaction_rows = []
            for tx in transactions:
                transaction_rows.append(
                    inventory_pb2.TransactionRow(
                        id=tx.get("id"),
                        transaction_type=tx.get("transaction_type"),
                        document_id=tx.get("document_id"),
                        document_line_id=tx.get("document_line_id"),
                        product_id=tx.get("product_id"),
                        warehouse_id=tx.get("warehouse_id"),
                        quantity=tx.get("quantity"),
                        physical_qty_before=tx.get("physical_qty_before"),
                        physical_qty_after=tx.get("physical_qty_after"),
                        reserved_qty_before=tx.get("reserved_qty_before"),
                        reserved_qty_after=tx.get("reserved_qty_after"),
                        available_qty_before=tx.get("available_qty_before"),
                        available_qty_after=tx.get("available_qty_after"),
                        user_id=tx.get("user_id"),
                        created_at=tx.get("created_at"),
                        payload=str(tx.get("payload")) if tx.get("payload") else "",
                        idempotency_key=tx.get("idempotency_key"),
                    )
                )
            
            return inventory_pb2.ListTransactionsResponse(transactions=transaction_rows)
        except Exception as exc:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return inventory_pb2.ListTransactionsResponse(transactions=[])
        finally:
            try:
                db.close()
            except Exception:
                pass


add_InventoryServiceServicer_to_server = inventory_pb2_grpc.add_InventoryServiceServicer_to_server
