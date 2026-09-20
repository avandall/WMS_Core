from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import HTTPException, Request
import grpc

from api_gateway.errors import grpc_http_exception
from api_gateway.gen.wms.documents.v1 import documents_pb2
from api_gateway.gen.wms.inventory.v1 import inventory_pb2
from api_gateway.grpc_clients import documents_stub, inventory_stub
from api_gateway.schemas import ConfirmExecutionPayload

logger = logging.getLogger(__name__)

GRPC_TIMEOUT_DEFAULT = 10.0
GRPC_TIMEOUT_SLOW = 30.0

REQUIRES_REASON_CODE = {"ADJUSTMENT_IN", "ADJUSTMENT_OUT", "SCRAP", "INTERNAL_CONSUMPTION"}
REQUIRES_RESERVATION = {"SALES_SHIPMENT", "PRODUCTION_ISSUE", "TRANSFER_ISSUE"}
OUTBOUND_TYPES = {
    "SALES_SHIPMENT",
    "PRODUCTION_ISSUE",
    "PURCHASE_RETURN_SHIPMENT",
    "TRANSFER_ISSUE",
    "INTERNAL_CONSUMPTION",
    "SCRAP",
    "ADJUSTMENT_OUT",
}


class SagaState(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPENSATING = "COMPENSATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(slots=True)
class ExecutedInventoryStep:
    transaction_type: str
    product_id: int
    warehouse_id: int
    quantity: int
    reservation_id: int = 0
    source_warehouse_id: int = 0
    is_outbound: bool = True
    idempotency_key: str = ""


def _extract_md(request: Request) -> list[tuple[str, str]] | None:
    request_id = getattr(request.state, "request_id", None)
    traceparent = getattr(request.state, "traceparent", None)
    metadata = []
    if request_id:
        metadata.append(("x-request-id", str(request_id)))
    if traceparent:
        metadata.append(("traceparent", str(traceparent)))

    user = getattr(request.state, "user", None)
    if user:
        metadata.append(("user-id", str(user.user_id)))
        metadata.append(("user-email", str(getattr(user, "email", ""))))
    return metadata or None


class ConfirmExecutionSaga:
    """Saga Orchestrator managing distributed document execution confirmation

    across documents-service and inventory-service.
    Guarantees eventual consistency with automatic compensating rollbacks upon failure.
    """

    def __init__(self, document_id: int):
        self.document_id: int = document_id
        self.state: SagaState = SagaState.PENDING
        self.executed_steps: list[ExecutedInventoryStep] = []
        self.error_message: str | None = None

    def execute(self, payload: ConfirmExecutionPayload, request: Request) -> dict[str, Any]:
        md = _extract_md(request)

        # ---------------------------------------------------------------------
        # 1. Pre-flight Document Retrieval & Validation
        # ---------------------------------------------------------------------
        with documents_stub() as doc_stub:
            try:
                doc = doc_stub.GetDocument(
                    documents_pb2.GetDocumentRequest(document_id=self.document_id),
                    timeout=GRPC_TIMEOUT_DEFAULT,
                    metadata=md,
                )
            except grpc.RpcError as exc:
                self.state = SagaState.FAILED
                raise grpc_http_exception(exc)
            except Exception as exc:
                self.state = SagaState.FAILED
                raise HTTPException(status_code=404, detail=f"Document {self.document_id} not found: {exc}")

        doc_type = (doc.doc_type or "").upper()
        tx_type = (doc.transaction_type or "").upper()
        current_status = (doc.status or "").upper()

        # Determine target transaction type & validate reason code
        if doc_type == "TRANSFER":
            is_transfer_receipt = (current_status == "EXECUTED")
            target_tx_type = "TRANSFER_RECEIPT" if is_transfer_receipt else "TRANSFER_ISSUE"
        else:
            is_transfer_receipt = False
            if tx_type:
                target_tx_type = tx_type
            else:
                if doc_type in ("SALE", "SALES_SHIPMENT"):
                    target_tx_type = "SALES_SHIPMENT"
                elif doc_type in ("IMPORT", "PURCHASE_RECEIPT"):
                    target_tx_type = "PURCHASE_RECEIPT"
                elif doc_type in ("EXPORT", "SCRAP"):
                    target_tx_type = "SCRAP"
                else:
                    target_tx_type = doc_type

            if target_tx_type in REQUIRES_REASON_CODE and not doc.reason_code:
                self.state = SagaState.FAILED
                raise HTTPException(
                    status_code=400,
                    detail=f"Reason code is required for {target_tx_type}",
                )

        # Transition Saga to EXECUTING state
        self.state = SagaState.EXECUTING

        is_outbound = target_tx_type in OUTBOUND_TYPES
        wh_id = doc.from_warehouse_id if is_outbound else (doc.to_warehouse_id or doc.from_warehouse_id)

        # If reservations are required, pre-fetch reservation mapping
        reservations_by_product: dict[int, Any] = {}
        if target_tx_type in REQUIRES_RESERVATION and doc_type != "TRANSFER":
            with inventory_stub() as inv_stub:
                try:
                    res_resp = inv_stub.ListReservations(
                        inventory_pb2.ListReservationsRequest(status="RESERVED"),
                        timeout=GRPC_TIMEOUT_DEFAULT,
                        metadata=md,
                    )
                    reservations_by_product = {
                        r.product_id: r
                        for r in res_resp.reservations
                        if r.document_id == self.document_id
                    }
                except Exception as exc:
                    logger.warning("Failed to list reservations for doc %d: %s", self.document_id, exc)

        # ---------------------------------------------------------------------
        # 2. Inventory Transactions Forward Execution
        # ---------------------------------------------------------------------
        try:
            with inventory_stub() as inv_stub:
                for item in payload.items:
                    if doc_type == "TRANSFER":
                        if is_transfer_receipt:
                            item_tx_type = "TRANSFER_RECEIPT"
                            item_wh_id = doc.to_warehouse_id
                            src_wh_id = doc.from_warehouse_id
                            res_id = 0
                            idempotency_key = f"confirm_{self.document_id}_{item.product_id}_receipt"
                            item_is_outbound = False
                        else:
                            item_tx_type = "TRANSFER_ISSUE"
                            item_wh_id = doc.from_warehouse_id
                            src_wh_id = 0
                            res_id = 0
                            idempotency_key = f"confirm_{self.document_id}_{item.product_id}_issue"
                            item_is_outbound = True
                    else:
                        item_tx_type = target_tx_type
                        src_wh_id = 0
                        idempotency_key = f"confirm_{self.document_id}_{item.product_id}"
                        item_is_outbound = is_outbound
                        if target_tx_type in REQUIRES_RESERVATION:
                            res = reservations_by_product.get(item.product_id)
                            res_id = res.id if res else 0
                            item_wh_id = res.warehouse_id if res else wh_id
                        else:
                            res_id = 0
                            item_wh_id = wh_id

                    inv_resp = inv_stub.ConfirmInventoryTransaction(
                        inventory_pb2.ConfirmInventoryTransactionRequest(
                            transaction_type=item_tx_type,
                            product_id=item.product_id,
                            warehouse_id=item_wh_id,
                            quantity=item.quantity,
                            reservation_id=res_id,
                            user_id="system",
                            idempotency_key=idempotency_key,
                            source_warehouse_id=src_wh_id,
                        ),
                        timeout=GRPC_TIMEOUT_SLOW,
                        metadata=md,
                    )

                    if not inv_resp.success:
                        raise RuntimeError(
                            f"Inventory transaction rejected for product_id={item.product_id}"
                        )

                    # Store successful step into executed_steps stack for potential compensation
                    self.executed_steps.append(
                        ExecutedInventoryStep(
                            transaction_type=item_tx_type,
                            product_id=item.product_id,
                            warehouse_id=item_wh_id,
                            quantity=item.quantity,
                            reservation_id=res_id,
                            source_warehouse_id=src_wh_id,
                            is_outbound=item_is_outbound,
                            idempotency_key=idempotency_key,
                        )
                    )

        except (grpc.RpcError, Exception) as exc:
            err_detail = exc.details() if isinstance(exc, grpc.RpcError) else str(exc)
            logger.error(
                "Saga failed during inventory execution for doc %d: %s. Initiating compensation.",
                self.document_id,
                err_detail,
            )
            self.error_message = err_detail
            self.compensate(request)
            raise HTTPException(
                status_code=400,
                detail=f"Confirm inventory execution failed for doc {self.document_id}: {err_detail}. Rollback completed.",
            )

        # ---------------------------------------------------------------------
        # 3. Document Service State Update
        # ---------------------------------------------------------------------
        try:
            with documents_stub() as doc_stub:
                confirm_resp = doc_stub.ConfirmExecution(
                    documents_pb2.ConfirmExecutionRequest(
                        document_id=self.document_id,
                        items=[
                            documents_pb2.DocumentItem(
                                product_id=item.product_id,
                                quantity=item.quantity,
                            )
                            for item in payload.items
                        ],
                    ),
                    timeout=GRPC_TIMEOUT_SLOW,
                    metadata=md,
                )

                if is_transfer_receipt:
                    doc_stub.CompleteRequest(
                        documents_pb2.CompleteRequestRequest(document_id=self.document_id),
                        timeout=GRPC_TIMEOUT_SLOW,
                        metadata=md,
                    )

        except (grpc.RpcError, Exception) as exc:
            err_detail = exc.details() if isinstance(exc, grpc.RpcError) else str(exc)
            logger.error(
                "Saga failed during document status update for doc %d: %s. Initiating compensation.",
                self.document_id,
                err_detail,
            )
            self.error_message = err_detail
            self.compensate(request)
            raise HTTPException(
                status_code=500,
                detail=f"Document execution update failed for doc {self.document_id}: {err_detail}. Rollback completed.",
            )

        # ---------------------------------------------------------------------
        # 4. Saga Completion
        # ---------------------------------------------------------------------
        self.state = SagaState.COMPLETED
        return {"message": confirm_resp.message}

    def compensate(self, request: Request) -> None:
        """Executes compensating actions for all previously executed inventory steps in reverse order."""
        self.state = SagaState.COMPENSATING
        md = _extract_md(request)

        logger.info(
            "Starting compensation for doc %d with %d executed steps.",
            self.document_id,
            len(self.executed_steps),
        )

        with inventory_stub() as inv_stub:
            while self.executed_steps:
                step = self.executed_steps.pop()
                try:
                    # Inverse action selection:
                    # Outbound forward steps subtract stock -> Compensate with ADJUSTMENT_IN (adds stock back)
                    # Inbound forward steps add stock -> Compensate with ADJUSTMENT_OUT (removes added stock)
                    if step.transaction_type == "TRANSFER_RECEIPT":
                        compensating_tx_type = "ADJUSTMENT_OUT"
                    elif step.transaction_type == "TRANSFER_ISSUE":
                        compensating_tx_type = "ADJUSTMENT_IN"
                    elif step.is_outbound:
                        compensating_tx_type = "ADJUSTMENT_IN"
                    else:
                        compensating_tx_type = "ADJUSTMENT_OUT"

                    comp_key = f"compensate_{self.document_id}_{step.product_id}_{step.transaction_type}"

                    inv_stub.ConfirmInventoryTransaction(
                        inventory_pb2.ConfirmInventoryTransactionRequest(
                            transaction_type=compensating_tx_type,
                            product_id=step.product_id,
                            warehouse_id=step.warehouse_id,
                            quantity=step.quantity,
                            reservation_id=0,
                            user_id="system_saga_compensate",
                            idempotency_key=comp_key,
                            source_warehouse_id=0,
                        ),
                        timeout=GRPC_TIMEOUT_SLOW,
                        metadata=md,
                    )
                    logger.info(
                        "Compensated product_id=%d on warehouse_id=%d with tx_type=%s",
                        step.product_id,
                        step.warehouse_id,
                        compensating_tx_type,
                    )
                except Exception as comp_exc:
                    logger.error(
                        "Failed compensating step for product_id=%d: %s",
                        step.product_id,
                        comp_exc,
                    )

        self.state = SagaState.FAILED
