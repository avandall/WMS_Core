from __future__ import annotations

import json
from datetime import datetime
import grpc

from shared_utils.events import get_publisher
from shared_utils.security import sanitize_grpc_error

from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.shared.core.database import get_db_session

from inventory_service.gen.wms.inventory.v1 import inventory_pb2, inventory_pb2_grpc


class InventoryServiceServicer(inventory_pb2_grpc.InventoryServiceServicer):
    _publisher = get_publisher("inventory-service")

    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        if context:
            for k, v in context.invocation_metadata() or []:
                if k.lower() == "x-request-id":
                    return v
        return None

    @staticmethod
    def _user_id(context: grpc.ServicerContext) -> str:
        if context:
            for k, v in context.invocation_metadata() or []:
                if k.lower() == "user-id":
                    return v
        return "system"


    def _service(self, db: object) -> InventoryService:
        return InventoryService(
            inventory_repo=InventoryRepo(db),
            event_publisher=self._publisher,
        )

    def ListInventoryItems(self, request: inventory_pb2.ListInventoryItemsRequest, context: grpc.ServicerContext):
        with get_db_session() as db:
            service = self._service(db)
            items = service.get_all_inventory_items()
            return inventory_pb2.ListInventoryItemsResponse(
                items=[
                    inventory_pb2.InventoryItem(product_id=int(i.product_id), quantity=int(i.quantity))
                    for i in items
                ]
            )

    def GetInventoryByWarehouse(
        self, request: inventory_pb2.GetInventoryByWarehouseRequest, context: grpc.ServicerContext
    ):
        with get_db_session() as db:
            service = self._service(db)
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

    def GetProductQuantity(
        self, request: inventory_pb2.GetProductQuantityRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
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

    # Phase 5: Availability and reservations
    def GetAvailability(
        self, request: inventory_pb2.GetAvailabilityRequest, context: grpc.ServicerContext
    ):
        with get_db_session() as db:
            service = self._service(db)
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

    def ListReservations(
        self, request: inventory_pb2.ListReservationsRequest, context: grpc.ServicerContext
    ):
        with get_db_session() as db:
            service = self._service(db)
            # In proto3, HasField() only works on message/oneof fields, not scalars.
            # Use the default zero-value as the sentinel for "not set".
            product_id = int(request.product_id) if request.product_id != 0 else None
            warehouse_id = int(request.warehouse_id) if request.warehouse_id != 0 else None
            status = request.status if request.status else None
            document_id = int(request.document_id) if request.document_id != 0 else None

            reservations = service.inventory_repo.list_reservations(
                product_id=product_id,
                warehouse_id=warehouse_id,
                status=status,
                document_id=document_id,
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

    def ReleaseReservation(
        self, request: inventory_pb2.ReleaseReservationRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
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
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.ReleaseReservationResponse(success=False)

    # Phase 9: Inventory transaction ledger
    def ListTransactions(
        self, request: inventory_pb2.ListTransactionsRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
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
                            id=int(tx.get("id")),
                            transaction_type=tx.get("transaction_type"),
                            document_id=int(tx.get("document_id")) if tx.get("document_id") else 0,
                            document_line_id=int(tx.get("document_line_id")) if tx.get("document_line_id") else 0,
                            product_id=int(tx.get("product_id")),
                            warehouse_id=int(tx.get("warehouse_id")),
                            quantity=int(tx.get("quantity")),
                            physical_qty_before=int(tx.get("physical_qty_before")) if tx.get("physical_qty_before") is not None else 0,
                            physical_qty_after=int(tx.get("physical_qty_after")) if tx.get("physical_qty_after") is not None else 0,
                            reserved_qty_before=int(tx.get("reserved_qty_before")) if tx.get("reserved_qty_before") is not None else 0,
                            reserved_qty_after=int(tx.get("reserved_qty_after")) if tx.get("reserved_qty_after") is not None else 0,
                            available_qty_before=int(tx.get("available_qty_before")) if tx.get("available_qty_before") is not None else 0,
                            available_qty_after=int(tx.get("available_qty_after")) if tx.get("available_qty_after") is not None else 0,
                            user_id=tx.get("user_id") or "",
                            created_at=tx.get("created_at") or "",
                            payload=json.dumps(tx.get("payload")) if tx.get("payload") else "",
                            idempotency_key=tx.get("idempotency_key") or "",
                        )
                    )
                
                return inventory_pb2.ListTransactionsResponse(transactions=transaction_rows)
        except Exception as exc:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.ListTransactionsResponse(transactions=[])

    def ConfirmInventoryTransaction(
        self, request: inventory_pb2.ConfirmInventoryTransactionRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
                req_user = (request.user_id or "").strip()
                ctx_user = self._user_id(context)
                eff_user_id = req_user if (req_user and req_user != "system") else ctx_user

                tx_id = service.confirm_inventory_transaction(
                    transaction_type=request.transaction_type,
                    product_id=int(request.product_id),
                    warehouse_id=int(request.warehouse_id),
                    quantity=int(request.quantity),
                    reservation_id=int(request.reservation_id),
                    user_id=eff_user_id,
                    idempotency_key=request.idempotency_key or None,
                    source_warehouse_id=int(request.source_warehouse_id) if request.source_warehouse_id else 0,
                )
                return inventory_pb2.ConfirmInventoryTransactionResponse(
                    success=True,
                    transaction_id=tx_id,
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.ConfirmInventoryTransactionResponse(success=False, transaction_id=0)

    def ReserveStock(self, request: inventory_pb2.ReserveStockRequest, context: grpc.ServicerContext):
        try:
            with get_db_session() as db:
                service = self._service(db)
                res_id = service.reserve_stock(
                    product_id=int(request.product_id),
                    quantity=int(request.quantity),
                    warehouse_id=int(request.warehouse_id) if request.warehouse_id else None,
                    event_id=request.event_id or None,
                    source_type=request.source_type or "manual",
                    source_id=int(request.source_id) if request.source_id else None,
                    document_id=int(request.document_id) if request.document_id else None,
                    created_by=request.created_by or None,
                    expires_at=request.expires_at or None,
                )
                return inventory_pb2.ReserveStockResponse(
                    success=True,
                    reservation_id=res_id,
                    message="Stock reserved successfully",
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.ReserveStockResponse(
                success=False,
                reservation_id=0,
                message=sanitize_grpc_error(exc)
            )

    def GetInventoryLocations(
        self, request: inventory_pb2.GetInventoryLocationsRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
                warehouse_id = int(request.warehouse_id) if request.warehouse_id != 0 else None
                product_id = int(request.product_id) if request.product_id != 0 else None
                position_id = int(request.position_id) if request.position_id != 0 else None
                lpn = request.lpn if request.lpn else None
                status = request.status if request.status else None
                lot_number = request.lot_number if request.lot_number else None

                locations = service.inventory_repo.list_inventory_locations(
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                    position_id=position_id,
                    lpn=lpn,
                    status=status,
                    lot_number=lot_number,
                )
                rows = [
                    inventory_pb2.InventoryLocationRow(
                        id=int(loc["id"]),
                        warehouse_id=int(loc["warehouse_id"]),
                        position_id=int(loc["position_id"]),
                        product_id=int(loc["product_id"]),
                        lpn=loc["lpn"] or "",
                        quantity=int(loc["quantity"]),
                        allocated_qty=int(loc["allocated_qty"]),
                        status=loc["status"] or "AVAILABLE",
                        available_qty=int(loc["available_qty"]),
                        lot_number=loc["lot_number"] or "",
                        mfg_date=loc["mfg_date"] or "",
                        expiry_date=loc["expiry_date"] or "",
                        x_coordinate=float(loc.get("x_coordinate", 0.0)),
                        y_coordinate=float(loc.get("y_coordinate", 0.0)),
                        z_coordinate=float(loc.get("z_coordinate", 0.0)),
                        zone_id=loc.get("zone_id", "ZONE-A"),
                        aisle=loc.get("aisle", "AISLE-01"),
                        bay=loc.get("bay", "BAY-01"),
                        level=loc.get("level", "1"),
                        location_code=loc.get("location_code", ""),
                    )
                    for loc in locations
                ]
                return inventory_pb2.GetInventoryLocationsResponse(locations=rows)
        except Exception as exc:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.GetInventoryLocationsResponse(locations=[])

    def UpdateInventoryLocation(
        self, request: inventory_pb2.UpdateInventoryLocationRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
                loc = service.inventory_repo.adjust_location_quantity(
                    warehouse_id=int(request.warehouse_id),
                    position_id=int(request.position_id),
                    product_id=int(request.product_id),
                    quantity_delta=int(request.quantity_delta),
                    allocated_delta=int(request.allocated_delta),
                    lpn=request.lpn or "",
                    status=request.status or "AVAILABLE",
                    lot_number=request.lot_number or "",
                    mfg_date=datetime.fromisoformat(request.mfg_date) if request.mfg_date else None,
                    expiry_date=datetime.fromisoformat(request.expiry_date) if request.expiry_date else None,
                )
                return inventory_pb2.UpdateInventoryLocationResponse(
                    success=True,
                    location=inventory_pb2.InventoryLocationRow(
                        id=int(loc["id"]),
                        warehouse_id=int(loc["warehouse_id"]),
                        position_id=int(loc["position_id"]),
                        product_id=int(loc["product_id"]),
                        lpn=loc["lpn"] or "",
                        quantity=int(loc["quantity"]),
                        allocated_qty=int(loc["allocated_qty"]),
                        status=loc["status"],
                        available_qty=int(loc["available_qty"]),
                        lot_number=loc["lot_number"] or "",
                        mfg_date=loc["mfg_date"] or "",
                        expiry_date=loc["expiry_date"] or "",
                        x_coordinate=float(loc.get("x_coordinate", 0.0)),
                        y_coordinate=float(loc.get("y_coordinate", 0.0)),
                        z_coordinate=float(loc.get("z_coordinate", 0.0)),
                        zone_id=loc.get("zone_id", "ZONE-A"),
                        aisle=loc.get("aisle", "AISLE-01"),
                        bay=loc.get("bay", "BAY-01"),
                        level=loc.get("level", "1"),
                        location_code=loc.get("location_code", ""),
                    )
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.UpdateInventoryLocationResponse(success=False)

    def ListDraftProposals(
        self, request: inventory_pb2.ListDraftProposalsRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
                status_filter = request.status if request.status else None
                limit = int(request.limit) if request.limit > 0 else 100
                offset = int(request.offset) if request.offset > 0 else 0
                proposals, total = service.list_draft_proposals(
                    status=status_filter, limit=limit, offset=offset
                )
                return inventory_pb2.ListDraftProposalsResponse(
                    proposals=[self._proposal_to_proto(p) for p in proposals],
                    total=total,
                )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.ListDraftProposalsResponse(proposals=[], total=0)

    def ApproveDraftProposal(
        self, request: inventory_pb2.ApproveDraftProposalRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
                eff_user = (request.approved_by or "").strip() or self._user_id(context)
                proposal, tx_id = service.approve_draft_proposal(
                    proposal_id=request.proposal_id,
                    approved_by=eff_user,
                    digital_signature=request.digital_signature or None,
                )
                return inventory_pb2.ApproveDraftProposalResponse(
                    success=True,
                    message="Proposal approved and executed successfully",
                    proposal=self._proposal_to_proto(proposal),
                    transaction_id=tx_id,
                )
        except ValueError as exc:
            if context:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.ApproveDraftProposalResponse(
                success=False,
                message=str(exc),
            )
        except Exception as exc:
            if context:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.ApproveDraftProposalResponse(
                success=False,
                message=sanitize_grpc_error(exc),
            )

    def RejectDraftProposal(
        self, request: inventory_pb2.RejectDraftProposalRequest, context: grpc.ServicerContext
    ):
        try:
            with get_db_session() as db:
                service = self._service(db)
                eff_user = (request.rejected_by or "").strip() or self._user_id(context)
                proposal = service.reject_draft_proposal(
                    proposal_id=request.proposal_id,
                    rejected_by=eff_user,
                    rejection_reason=request.rejection_reason or "Rejected by manager",
                )
                return inventory_pb2.RejectDraftProposalResponse(
                    success=True,
                    message="Proposal rejected successfully",
                    proposal=self._proposal_to_proto(proposal),
                )
        except ValueError as exc:
            if context:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.RejectDraftProposalResponse(
                success=False,
                message=str(exc),
            )
        except Exception as exc:
            if context:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(sanitize_grpc_error(exc))
            return inventory_pb2.RejectDraftProposalResponse(
                success=False,
                message=sanitize_grpc_error(exc),
            )

    @staticmethod
    def _proposal_to_proto(p) -> inventory_pb2.DraftProposalRow:
        return inventory_pb2.DraftProposalRow(
            proposal_id=str(p.proposal_id or ""),
            proposal_type=str(p.proposal_type or ""),
            sku_code=str(p.sku_code or ""),
            current_quantity=int(p.current_quantity or 0),
            proposed_quantity=int(p.proposed_quantity or 0),
            adjustment=int(p.adjustment or 0),
            reason=str(p.reason or ""),
            requested_by=str(p.requested_by or ""),
            status=str(p.status or ""),
            created_at=p.created_at.isoformat() if p.created_at else "",
            approved_by=str(p.approved_by or ""),
            approved_at=p.approved_at.isoformat() if p.approved_at else "",
            rejection_reason=str(p.rejection_reason or ""),
            executed_at=p.executed_at.isoformat() if p.executed_at else "",
            executed_by=str(p.executed_by or ""),
            digital_signature=str(p.digital_signature or ""),
        )


add_InventoryServiceServicer_to_server = inventory_pb2_grpc.add_InventoryServiceServicer_to_server
