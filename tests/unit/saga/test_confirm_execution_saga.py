"""
Unit tests for ConfirmExecutionSaga (TASK-026).
Tests saga compensation restoring document status to IN_PROGRESS via RevertToInProgress,
preserving executed_steps, CRITICAL level log emissions, and pushing failures to dlq_retry_stack.
"""

import logging
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException, Request

from api_gateway.gen.wms.documents.v1 import documents_pb2
from api_gateway.saga.confirm_execution_saga import (
    ConfirmExecutionSaga,
    ExecutedInventoryStep,
    SagaState,
)
from api_gateway.schemas import ConfirmExecutionPayload, ConfirmItemPayload


@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.state.request_id = "req-test-dlq"
    req.state.traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    req.state.user = MagicMock(user_id=1, email="admin@example.com")
    return req


def test_saga_compensation_rolls_back_document_status_and_logs_dlq(mock_request, caplog):
    """
    TASK-026 Acceptance Criteria:
    - Document status rolled back to IN_PROGRESS via RevertToInProgress.
    - executed_steps preserved without being popped.
    - Compensation step exception logged with CRITICAL and pushed to dlq_retry_stack.
    """
    caplog.set_level(logging.CRITICAL)

    saga = ConfirmExecutionSaga(document_id=201)

    mock_doc = MagicMock()
    mock_doc.doc_type = "SALE"
    mock_doc.transaction_type = "SALES_SHIPMENT"
    mock_doc.status = "APPROVED"
    mock_doc.from_warehouse_id = 1
    mock_doc.to_warehouse_id = 0
    mock_doc.reason_code = ""

    mock_doc_stub = MagicMock()
    mock_doc_stub.GetDocument.return_value = mock_doc
    # Document execution confirmation fails
    mock_doc_stub.ConfirmExecution.side_effect = RuntimeError("Service unavailable")
    mock_doc_stub.RevertToInProgress.return_value = documents_pb2.RevertToInProgressResponse(
        message="Document 201 reverted to IN_PROGRESS successfully"
    )

    mock_inv_stub = MagicMock()
    # Step 1 forward succeeds, Step 2 forward succeeds.
    # Then during compensation, Step 2 compensation fails with exception.
    mock_inv_stub.ConfirmInventoryTransaction.side_effect = [
        MagicMock(success=True, transaction_id=10),  # Forward Step 1
        MagicMock(success=True, transaction_id=11),  # Forward Step 2
        RuntimeError("gRPC network timeout on compensation"),  # Comp Step 2 fails!
        MagicMock(success=True, transaction_id=12),  # Comp Step 1 succeeds
    ]
    mock_inv_stub.ListReservations.return_value = MagicMock(reservations=[])

    payload = ConfirmExecutionPayload(
        items=[
            ConfirmItemPayload(product_id=10, quantity=5),
            ConfirmItemPayload(product_id=20, quantity=2),
        ]
    )

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub
        mock_is.return_value.__enter__.return_value = mock_inv_stub

        with pytest.raises(HTTPException) as exc_info:
            saga.execute(payload, mock_request)

        assert exc_info.value.status_code == 500
        assert saga.state == SagaState.FAILED

        # 1. Check RevertToInProgress was called
        mock_doc_stub.RevertToInProgress.assert_called_once()
        revert_arg = mock_doc_stub.RevertToInProgress.call_args[0][0]
        assert revert_arg.document_id == 201

        # 2. Check executed_steps is NOT empty (preserved)
        assert len(saga.executed_steps) == 2
        assert saga.executed_steps[0].product_id == 10
        assert saga.executed_steps[1].product_id == 20

        # 3. Check CRITICAL log and dlq_retry_stack
        critical_logs = [record for record in caplog.records if record.levelno == logging.CRITICAL]
        assert len(critical_logs) >= 1
        assert "Failed compensating step for product_id=20" in caplog.text

        assert len(saga.dlq_retry_stack) == 1
        dlq_entry = saga.dlq_retry_stack[0]
        assert dlq_entry["action"] == "inventory_compensation"
        assert dlq_entry["document_id"] == 201
        assert dlq_entry["product_id"] == 20
        assert "gRPC network timeout on compensation" in dlq_entry["error"]


def test_saga_compensation_dlq_stack_on_revert_failure(mock_request, caplog):
    """Verify DLQ entry and CRITICAL log when RevertToInProgress itself fails."""
    caplog.set_level(logging.CRITICAL)

    saga = ConfirmExecutionSaga(document_id=202)
    saga.executed_steps.append(
        ExecutedInventoryStep(
            transaction_type="SALES_SHIPMENT",
            product_id=1,
            warehouse_id=1,
            quantity=10,
            is_outbound=True,
        )
    )

    mock_doc_stub = MagicMock()
    mock_doc_stub.RevertToInProgress.side_effect = RuntimeError("Documents DB lock timeout")

    mock_inv_stub = MagicMock()
    mock_inv_stub.ConfirmInventoryTransaction.return_value = MagicMock(success=True)

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub
        mock_is.return_value.__enter__.return_value = mock_inv_stub

        saga.compensate(mock_request)

        assert saga.state == SagaState.FAILED
        assert mock_doc_stub.RevertToInProgress.call_count == 1
        assert len(saga.executed_steps) == 1

        # Verify DLQ stack captures revert_document_status failure
        assert len(saga.dlq_retry_stack) == 1
        dlq_item = saga.dlq_retry_stack[0]
        assert dlq_item["action"] == "revert_document_status"
        assert dlq_item["document_id"] == 202
        assert "Documents DB lock timeout" in dlq_item["error"]
        assert "Failed to revert document 202 status to IN_PROGRESS" in caplog.text


def test_saga_transfers_owner_id_to_inventory_service(mock_request):
    """TASK-095: Verify ConfirmExecutionSaga extracts doc.owner_id and forwards it to inventory-service."""
    saga = ConfirmExecutionSaga(document_id=301)

    mock_doc = MagicMock()
    mock_doc.doc_type = "SALE"
    mock_doc.transaction_type = "SALES_SHIPMENT"
    mock_doc.status = "APPROVED"
    mock_doc.from_warehouse_id = 1
    mock_doc.to_warehouse_id = 0
    mock_doc.reason_code = ""
    mock_doc.owner_id = "CLIENT_A"

    mock_doc_stub = MagicMock()
    mock_doc_stub.GetDocument.return_value = mock_doc
    mock_doc_stub.ConfirmExecution.return_value = documents_pb2.ConfirmExecutionResponse(
        message="Confirmed"
    )

    mock_inv_stub = MagicMock()
    mock_inv_stub.ConfirmInventoryTransaction.return_value = MagicMock(success=True, transaction_id=99)
    mock_inv_stub.ListReservations.return_value = MagicMock(reservations=[])

    payload = ConfirmExecutionPayload(
        items=[
            ConfirmItemPayload(product_id=10, quantity=5),
        ]
    )

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub
        mock_is.return_value.__enter__.return_value = mock_inv_stub

        res = saga.execute(payload, mock_request)

        assert saga.state == SagaState.COMPLETED
        mock_inv_stub.ConfirmInventoryTransaction.assert_called_once()
        inv_call_req = mock_inv_stub.ConfirmInventoryTransaction.call_args[0][0]
        assert inv_call_req.owner_id == "CLIENT_A"
        assert len(saga.executed_steps) == 1
        assert saga.executed_steps[0].owner_id == "CLIENT_A"


def test_saga_compensation_preserves_owner_id(mock_request):
    """TASK-095: Verify compensation step sends exact owner_id from executed step."""
    saga = ConfirmExecutionSaga(document_id=302)
    saga.executed_steps.append(
        ExecutedInventoryStep(
            transaction_type="SALES_SHIPMENT",
            product_id=15,
            warehouse_id=1,
            quantity=8,
            is_outbound=True,
            owner_id="CLIENT_A",
        )
    )

    mock_doc_stub = MagicMock()
    mock_doc_stub.RevertToInProgress.return_value = MagicMock()

    mock_inv_stub = MagicMock()
    mock_inv_stub.ConfirmInventoryTransaction.return_value = MagicMock(success=True)

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub
        mock_is.return_value.__enter__.return_value = mock_inv_stub

        saga.compensate(mock_request)

        mock_inv_stub.ConfirmInventoryTransaction.assert_called_once()
        comp_call_req = mock_inv_stub.ConfirmInventoryTransaction.call_args[0][0]
        assert comp_call_req.owner_id == "CLIENT_A"
        assert comp_call_req.transaction_type == "ADJUSTMENT_IN"


def test_inventory_service_confirm_transaction_isolates_3pl_owner_id():
    """TASK-095: Confirming outbound transaction for CLIENT_A reduces only CLIENT_A stock, CLIENT_B is untouched."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.shared.core.database import Base, import_all_models
    from shared_utils.outbox.models import OutboxEventModel
    from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
    from app.modules.inventory.application.services.inventory_service import InventoryService
    from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel

    engine = create_engine("sqlite:///:memory:", echo=False)
    import_all_models()
    Base.metadata.create_all(bind=engine)
    OutboxEventModel.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Pre-populate stock for both owners
    inv_a = WarehouseInventoryModel(
        warehouse_id=1,
        product_id=50,
        owner_id="CLIENT_A",
        quantity=10,
        physical_qty=10,
    )
    inv_b = WarehouseInventoryModel(
        warehouse_id=1,
        product_id=50,
        owner_id="CLIENT_B",
        quantity=10,
        physical_qty=10,
    )
    session.add_all([inv_a, inv_b])
    session.commit()

    repo = InventoryRepo(session)
    service = InventoryService(repo)

    # Confirm outbound shipment of 4 units for CLIENT_A
    service.confirm_inventory_transaction(
        transaction_type="SALES_SHIPMENT",
        product_id=50,
        warehouse_id=1,
        quantity=4,
        owner_id="CLIENT_A",
    )

    session.expire_all()
    updated_a = session.query(WarehouseInventoryModel).filter_by(
        warehouse_id=1, product_id=50, owner_id="CLIENT_A"
    ).one()
    updated_b = session.query(WarehouseInventoryModel).filter_by(
        warehouse_id=1, product_id=50, owner_id="CLIENT_B"
    ).one()

    # Assert CLIENT_A decremented by 4 (10 - 4 = 6)
    assert updated_a.quantity == 6
    assert updated_a.physical_qty == 6

    # Assert CLIENT_B remained unchanged (10)
    assert updated_b.quantity == 10
    assert updated_b.physical_qty == 10
    session.close()
