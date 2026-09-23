import unittest
from unittest.mock import MagicMock, patch
import pytest

from shared_utils.security import sanitize_grpc_error
from api_gateway.saga.confirm_execution_saga import ConfirmExecutionSaga, _extract_user_id, _extract_md


def test_grpc_error_sanitization():
    # 1. Traceback string sanitization
    tb_err = 'Traceback (most recent call last):\n  File "app/main.py", line 45, in execute\n    res = db.query()'
    assert sanitize_grpc_error(tb_err) == "WMS_ERR_DATABASE_ERROR"

    # 2. SQL queries and database drivers
    sql_err = "sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) SELECT * FROM users WHERE id = 10"
    assert sanitize_grpc_error(sql_err) == "WMS_ERR_DATABASE_ERROR"

    dup_err = "psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint 'users_email_key'"
    assert sanitize_grpc_error(dup_err) == "WMS_ERR_DUPLICATE_ENTRY"

    fk_err = "sqlalchemy.exc.IntegrityError: violates foreign key constraint 'fk_order_user'"
    assert sanitize_grpc_error(fk_err) == "WMS_ERR_FOREIGN_KEY_VIOLATION"

    # 3. Domain errors
    assert sanitize_grpc_error("Item not found in warehouse") == "WMS_ERR_NOT_FOUND"
    assert sanitize_grpc_error("Unauthorized access to resource") == "WMS_ERR_UNAUTHORIZED"
    assert sanitize_grpc_error("Permission denied for action") == "WMS_ERR_UNAUTHORIZED"
    assert sanitize_grpc_error("Invalid argument provided") == "WMS_ERR_INVALID_ARGUMENT"
    assert sanitize_grpc_error("Insufficient stock available") == "WMS_ERR_INSUFFICIENT_STOCK"

    # 4. Standard WMS codes pass through
    assert sanitize_grpc_error("WMS_ERR_CUSTOM_CODE") == "WMS_ERR_CUSTOM_CODE"

    # 5. Empty / None fallback
    assert sanitize_grpc_error(None) == "WMS_ERR_INTERNAL"
    assert sanitize_grpc_error("") == "WMS_ERR_INTERNAL"
    assert sanitize_grpc_error("   ") == "WMS_ERR_INTERNAL"


def test_saga_user_id_propagation():
    # 1. Test _extract_user_id helper with object user
    mock_req_obj = MagicMock()
    mock_user_obj = MagicMock()
    mock_user_obj.user_id = 101
    mock_req_obj.state.user = mock_user_obj
    assert _extract_user_id(mock_req_obj) == "101"

    # 2. Test _extract_user_id with dict user
    mock_req_dict = MagicMock()
    mock_req_dict.state.user = {"user_id": 202, "email": "admin@example.com"}
    assert _extract_user_id(mock_req_dict) == "202"

    # 3. Test _extract_user_id with state.user_id attribute fallback
    mock_req_attr = MagicMock()
    mock_req_attr.state.user = None
    mock_req_attr.state.user_id = 303
    assert _extract_user_id(mock_req_attr) == "303"

    # 4. Test _extract_user_id fallback to system
    mock_req_empty = MagicMock()
    mock_req_empty.state = MagicMock(spec=[])
    assert _extract_user_id(mock_req_empty) == "system"
    assert _extract_user_id(None) == "system"

    # 5. Test _extract_md helper metadata propagation
    mock_req_md = MagicMock()
    mock_req_md.state.request_id = "req-abc-123"
    mock_req_md.state.traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    mock_req_md.state.user = {"user_id": 505, "email": "user505@test.com"}
    md = _extract_md(mock_req_md)
    assert ("x-request-id", "req-abc-123") in md
    assert ("user-id", "505") in md
    assert ("user-email", "user505@test.com") in md


def test_saga_confirm_execution_propagates_jwt_user_id():
    # Setup mock request with JWT user in state
    request = MagicMock()
    request.state.request_id = "req-999"
    request.state.user = {"user_id": 777, "email": "jwt_user@wms.com"}

    payload = MagicMock()
    item_mock = MagicMock()
    item_mock.product_id = 10
    item_mock.quantity = 5
    payload.items = [item_mock]

    # Mock document gRPC response
    doc_resp = MagicMock()
    doc_resp.doc_type = "SALE"
    doc_resp.transaction_type = "SALES_SHIPMENT"
    doc_resp.status = "DRAFT"
    doc_resp.from_warehouse_id = 1
    doc_resp.to_warehouse_id = 0
    doc_resp.reason_code = ""

    mock_doc_stub = MagicMock()
    mock_doc_stub.GetDocument.return_value = doc_resp
    mock_doc_stub.ConfirmExecution.return_value = MagicMock(message="Confirmed")

    # Mock inventory gRPC response
    inv_confirm_resp = MagicMock()
    inv_confirm_resp.success = True
    inv_confirm_resp.transaction_id = 12345

    mock_inv_stub = MagicMock()
    mock_inv_stub.ConfirmInventoryTransaction.return_value = inv_confirm_resp

    with patch("api_gateway.saga.confirm_execution_saga.documents_stub") as patch_doc_stub, \
         patch("api_gateway.saga.confirm_execution_saga.inventory_stub") as patch_inv_stub:
        
        patch_doc_stub.return_value.__enter__.return_value = mock_doc_stub
        patch_inv_stub.return_value.__enter__.return_value = mock_inv_stub

        saga = ConfirmExecutionSaga(document_id=100)
        res = saga.execute(payload, request)

        assert res == {"message": "Confirmed"}
        
        # Verify ConfirmInventoryTransaction was called with user_id="777"
        mock_inv_stub.ConfirmInventoryTransaction.assert_called_once()
        call_args = mock_inv_stub.ConfirmInventoryTransaction.call_args
        req_arg = call_args[0][0]
        assert req_arg.user_id == "777"
