"""
Integration tests for ConfirmExecutionSaga.
TASK-008: Tests distributed transaction orchestration for document confirmation across
documents-service and inventory-service, state transitions (PENDING, EXECUTING, COMPENSATING,
COMPLETED, FAILED), and automatic compensating actions on inventory or document failure.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException, Request

from api_gateway.gen.wms.documents.v1 import documents_pb2
from api_gateway.gen.wms.inventory.v1 import inventory_pb2
from api_gateway.saga.confirm_execution_saga import ConfirmExecutionSaga, SagaState
from api_gateway.schemas import ConfirmExecutionPayload, ConfirmItemPayload


@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.state.request_id = "req-12345"
    req.state.traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    req.state.user = MagicMock(user_id=1, email="admin@example.com")
    return req


def test_saga_happy_path_success(mock_request):
    """Happy path: All inventory items confirmed, document state updated to EXECUTED."""
    saga = ConfirmExecutionSaga(document_id=101)
    assert saga.state == SagaState.PENDING

    mock_doc = MagicMock()
    mock_doc.doc_type = "SALE"
    mock_doc.transaction_type = "SALES_SHIPMENT"
    mock_doc.status = "APPROVED"
    mock_doc.from_warehouse_id = 1
    mock_doc.to_warehouse_id = 0
    mock_doc.reason_code = ""

    mock_doc_stub = MagicMock()
    mock_doc_stub.GetDocument.return_value = mock_doc
    mock_doc_stub.ConfirmExecution.return_value = MagicMock(message="Document confirmed successfully")

    mock_inv_stub = MagicMock()
    mock_inv_stub.ConfirmInventoryTransaction.return_value = MagicMock(success=True, transaction_id=99)
    mock_inv_stub.ListReservations.return_value = MagicMock(reservations=[])

    payload = ConfirmExecutionPayload(
        items=[
            ConfirmItemPayload(product_id=1, quantity=5),
            ConfirmItemPayload(product_id=2, quantity=3),
        ]
    )

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub
        mock_is.return_value.__enter__.return_value = mock_inv_stub

        res = saga.execute(payload, mock_request)

        assert res["message"] == "Document confirmed successfully"
        assert saga.state == SagaState.COMPLETED
        assert len(saga.executed_steps) == 2
        assert mock_inv_stub.ConfirmInventoryTransaction.call_count == 2
        mock_doc_stub.ConfirmExecution.assert_called_once()


def test_saga_inventory_failure_triggers_compensation(mock_request):
    """When an item inventory update fails, Saga compensates already executed items and fails."""
    saga = ConfirmExecutionSaga(document_id=102)

    mock_doc = MagicMock()
    mock_doc.doc_type = "SALE"
    mock_doc.transaction_type = "SALES_SHIPMENT"
    mock_doc.status = "APPROVED"
    mock_doc.from_warehouse_id = 1
    mock_doc.to_warehouse_id = 0
    mock_doc.reason_code = ""

    mock_doc_stub = MagicMock()
    mock_doc_stub.GetDocument.return_value = mock_doc

    mock_inv_stub = MagicMock()
    # First item succeeds, second item fails
    mock_inv_stub.ConfirmInventoryTransaction.side_effect = [
        MagicMock(success=True, transaction_id=10),
        RuntimeError("Insufficient stock for product 2"),
        MagicMock(success=True, transaction_id=11),  # Compensating call
    ]
    mock_inv_stub.ListReservations.return_value = MagicMock(reservations=[])

    payload = ConfirmExecutionPayload(
        items=[
            ConfirmItemPayload(product_id=1, quantity=5),
            ConfirmItemPayload(product_id=2, quantity=3),
        ]
    )

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub
        mock_is.return_value.__enter__.return_value = mock_inv_stub

        with pytest.raises(HTTPException) as exc_info:
            saga.execute(payload, mock_request)

        assert exc_info.value.status_code == 400
        assert "Rollback completed" in exc_info.value.detail
        assert saga.state == SagaState.FAILED
        # Document ConfirmExecution should NEVER be called if inventory step fails
        mock_doc_stub.ConfirmExecution.assert_not_called()

        # Check compensating call (item 1 compensated with ADJUSTMENT_IN)
        assert mock_inv_stub.ConfirmInventoryTransaction.call_count == 3
        comp_call_args = mock_inv_stub.ConfirmInventoryTransaction.call_args_list[2][0][0]
        assert comp_call_args.transaction_type == "ADJUSTMENT_IN"
        assert comp_call_args.product_id == 1
        assert comp_call_args.quantity == 5


def test_saga_document_update_failure_triggers_compensation(mock_request):
    """When document status update fails, Saga compensates all executed inventory steps."""
    saga = ConfirmExecutionSaga(document_id=103)

    mock_doc = MagicMock()
    mock_doc.doc_type = "SALE"
    mock_doc.transaction_type = "SALES_SHIPMENT"
    mock_doc.status = "APPROVED"
    mock_doc.from_warehouse_id = 1
    mock_doc.to_warehouse_id = 0
    mock_doc.reason_code = ""

    mock_doc_stub = MagicMock()
    mock_doc_stub.GetDocument.return_value = mock_doc
    mock_doc_stub.ConfirmExecution.side_effect = RuntimeError("Database error in documents service")

    mock_inv_stub = MagicMock()
    mock_inv_stub.ConfirmInventoryTransaction.return_value = MagicMock(success=True, transaction_id=1)
    mock_inv_stub.ListReservations.return_value = MagicMock(reservations=[])

    payload = ConfirmExecutionPayload(
        items=[
            ConfirmItemPayload(product_id=1, quantity=5),
            ConfirmItemPayload(product_id=2, quantity=3),
        ]
    )

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub
        mock_is.return_value.__enter__.return_value = mock_inv_stub

        with pytest.raises(HTTPException) as exc_info:
            saga.execute(payload, mock_request)

        assert exc_info.value.status_code == 500
        assert "Rollback completed" in exc_info.value.detail
        assert saga.state == SagaState.FAILED

        # Total inventory calls: 2 forward calls + 2 reverse compensating calls = 4 calls
        assert mock_inv_stub.ConfirmInventoryTransaction.call_count == 4


def test_saga_missing_reason_code_fails_fast(mock_request):
    """Saga aborts fast if required reason code is missing."""
    saga = ConfirmExecutionSaga(document_id=104)

    mock_doc = MagicMock()
    mock_doc.doc_type = "EXPORT"
    mock_doc.transaction_type = "SCRAP"
    mock_doc.status = "APPROVED"
    mock_doc.from_warehouse_id = 1
    mock_doc.to_warehouse_id = 0
    mock_doc.reason_code = ""  # Missing!

    mock_doc_stub = MagicMock()
    mock_doc_stub.GetDocument.return_value = mock_doc

    payload = ConfirmExecutionPayload(
        items=[ConfirmItemPayload(product_id=1, quantity=5)]
    )

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub

        with pytest.raises(HTTPException) as exc_info:
            saga.execute(payload, mock_request)

        assert exc_info.value.status_code == 400
        assert "Reason code is required" in exc_info.value.detail
        assert saga.state == SagaState.FAILED
        mock_is.assert_not_called()


def test_saga_transfer_receipt_workflow(mock_request):
    """Transfer document in EXECUTED status triggers TRANSFER_RECEIPT and CompleteRequest."""
    saga = ConfirmExecutionSaga(document_id=105)

    mock_doc = MagicMock()
    mock_doc.doc_type = "TRANSFER"
    mock_doc.transaction_type = ""
    mock_doc.status = "EXECUTED"  # Indicates Transfer Receipt step
    mock_doc.from_warehouse_id = 1
    mock_doc.to_warehouse_id = 2
    mock_doc.reason_code = ""

    mock_doc_stub = MagicMock()
    mock_doc_stub.GetDocument.return_value = mock_doc
    mock_doc_stub.ConfirmExecution.return_value = MagicMock(message="Transfer completed")
    mock_doc_stub.CompleteRequest.return_value = MagicMock(message="Transfer document marked complete")

    mock_inv_stub = MagicMock()
    mock_inv_stub.ConfirmInventoryTransaction.return_value = MagicMock(success=True, transaction_id=50)

    payload = ConfirmExecutionPayload(
        items=[ConfirmItemPayload(product_id=1, quantity=10)]
    )

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as mock_ds, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as mock_is:

        mock_ds.return_value.__enter__.return_value = mock_doc_stub
        mock_is.return_value.__enter__.return_value = mock_inv_stub

        res = saga.execute(payload, mock_request)

        assert res["message"] == "Transfer completed"
        assert saga.state == SagaState.COMPLETED
        mock_doc_stub.CompleteRequest.assert_called_once()
