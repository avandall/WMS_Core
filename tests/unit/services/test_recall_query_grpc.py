import inspect
from unittest.mock import MagicMock, patch

from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from inventory_service.gen.wms.documents.v1 import documents_pb2


def test_recall_query_no_sys_path_hack():
    """Verify that inventory_repo.py does not contain any sys.path.insert or importlib hacks."""
    source = inspect.getsource(InventoryRepo.recall_query)
    assert "sys.path.insert" not in source
    assert "importlib" not in source
    assert "from app.modules.documents" not in source


def test_recall_query_uses_grpc_not_import(test_session):
    """Verify recall_query calls gRPC DocumentsService.GetDocument."""
    repo = InventoryRepo(test_session)

    # Add lot in inventory location
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=10,
        product_id=999,
        quantity_delta=100,
        lpn="LPN-RECALL",
        lot_number="LOT-RECALL-99",
    )

    mock_doc = documents_pb2.Document(
        document_id=501,
        doc_type="SALE",
        status="COMPLETED",
        customer_id=777,
        from_warehouse_id=1,
        created_by="Admin",
        items=[
            documents_pb2.DocumentItem(
                product_id=999,
                quantity=25,
                unit_price=10.0,
                lot_number="LOT-RECALL-99",
            )
        ],
    )

    mock_stub = MagicMock()
    mock_stub.GetDocument.return_value = mock_doc
    mock_stub.ListDocuments.return_value = documents_pb2.ListDocumentsResponse(documents=[mock_doc])

    with patch("inventory_service.grpc_client.get_documents_stub") as mock_get_stub:
        mock_get_stub.return_value.__enter__.return_value = mock_stub
        recall_res = repo.recall_query("LOT-RECALL-99")

    assert recall_res["lot_number"] == "LOT-RECALL-99"
    assert len(recall_res["locations"]) == 1
    assert recall_res["locations"][0]["position_id"] == 10
    assert recall_res["locations"][0]["quantity"] == 100

    assert len(recall_res["customers"]) == 1
    assert recall_res["customers"][0]["customer_id"] == 777
    assert recall_res["customers"][0]["document_id"] == 501
    assert recall_res["customers"][0]["quantity"] == 25
