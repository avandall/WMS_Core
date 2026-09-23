import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Clean up sys.modules to load documents-service app module cleanly
for mod in list(sys.modules.keys()):
    if mod == "app" or mod.startswith("app."):
        del sys.modules[mod]

doc_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "documents-service" / "src")
if doc_src not in sys.path:
    sys.path.insert(0, doc_src)

import pytest
from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo
from app.modules.documents.domain.transaction_mapping import DOC_TYPE_TO_TRANSACTION_TYPE, TransactionType
from app.shared.domain.business_exceptions import ValidationError


@pytest.fixture
def mock_document_repo():
    repo = MagicMock(spec=IDocumentRepo)
    store = {}
    next_id = [1]

    def mock_get(doc_id):
        return store.get(doc_id)

    def mock_save(doc):
        if not doc.document_id:
            doc.document_id = next_id[0]
            next_id[0] += 1
        store[doc.document_id] = doc

    repo.get.side_effect = mock_get
    repo.save.side_effect = mock_save
    repo._store = store
    return repo


@pytest.fixture
def document_service(mock_document_repo):
    return DocumentService(document_repo=mock_document_repo)


def test_purchase_return_workflow(document_service, mock_document_repo):
    """
    Test creation and execution flow of a PURCHASE_RETURN document.
    PURCHASE_RETURN requires a source warehouse and deducts stock (ADJUSTMENT_OUT / PURCHASE_RETURN_SHIPMENT).
    """
    # 1. Validation check: from_warehouse_id is required
    with pytest.raises(ValidationError):
        Document(
            document_id=0,
            doc_type=DocumentType.PURCHASE_RETURN,
            from_warehouse_id=None,
            items=[DocumentProduct(product_id=101, quantity=5, unit_price=10.0)],
            created_by="tester",
        )

    # 2. Create purchase return document
    items = [{"product_id": 101, "quantity": 5, "unit_price": 20.0}]
    doc = document_service.create_purchase_return_document(
        from_warehouse_id=1,
        items=items,
        created_by="supplier_mgr",
        note="Defective items return to vendor",
    )

    assert doc.document_id == 1
    assert doc.doc_type == DocumentType.PURCHASE_RETURN
    assert doc.from_warehouse_id == 1
    assert doc.status == DocumentStatus.DRAFT
    assert doc.transaction_type == "PURCHASE_RETURN_SHIPMENT"
    assert DOC_TYPE_TO_TRANSACTION_TYPE[doc.doc_type] == TransactionType.PURCHASE_RETURN_SHIPMENT

    # 3. Test inventory reduction logic on inventory-service side
    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    inv_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "inventory-service" / "src")
    if inv_src not in sys.path:
        sys.path.insert(0, inv_src)

    from app.modules.inventory.application.services.inventory_service import InventoryService
    mock_inv_repo = MagicMock()
    mock_event_pub = MagicMock()
    mock_inv_repo.has_movement_event.return_value = False

    inv_service = InventoryService(
        inventory_repo=mock_inv_repo,
        event_publisher=mock_event_pub,
    )

    with patch.object(inv_service, "_apply_outbound") as mock_outbound, \
         patch.object(inv_service, "_write_transaction") as mock_write_tx, \
         patch.object(inv_service, "_record_movement") as mock_record_mov:
        payload = {
            "event_id": "evt-pur-ret-1",
            "document_id": doc.document_id,
            "doc_type": "PURCHASE_RETURN",
            "from_warehouse_id": 1,
            "to_warehouse_id": None,
            "items": [{"product_id": 101, "quantity": 5}],
            "executed_by": "inventory_mgr",
        }
        res = inv_service.apply_document_movement(payload)
        assert res is not False
        mock_outbound.assert_called_once_with(101, 1, 5)


def test_sales_return_quarantine_stock(document_service, mock_document_repo):
    """
    Test SALES_RETURN workflow:
    1. Creating a SALES_RETURN document (requires destination warehouse).
    2. Inventory receiving puts items in QUARANTINED status.
    3. QA inspection updates document status to QA_INSPECTED.
    """
    # 1. Validation check: to_warehouse_id is required
    with pytest.raises(ValidationError):
        Document(
            document_id=0,
            doc_type=DocumentType.SALES_RETURN,
            to_warehouse_id=None,
            items=[DocumentProduct(product_id=202, quantity=2, unit_price=50.0)],
            created_by="tester",
        )

    # 2. Create sales return document
    items = [{"product_id": 202, "quantity": 2, "unit_price": 50.0}]
    doc = document_service.create_sales_return_document(
        to_warehouse_id=2,
        items=items,
        created_by="customer_service",
        note="Customer return - damage inspection needed",
        customer_id=1001,
    )

    assert doc.doc_type == DocumentType.SALES_RETURN
    assert doc.to_warehouse_id == 2
    assert doc.customer_id == 1001
    assert doc.status == DocumentStatus.DRAFT

    # 3. Test inventory receiving creates QUARANTINED inventory item
    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    inv_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "inventory-service" / "src")
    if inv_src not in sys.path:
        sys.path.insert(0, inv_src)

    from app.modules.inventory.application.services.inventory_service import InventoryService
    mock_inv_repo = MagicMock()
    mock_event_pub = MagicMock()
    mock_inv_repo.has_movement_event.return_value = False

    inv_service = InventoryService(
        inventory_repo=mock_inv_repo,
        event_publisher=mock_event_pub,
    )

    with patch.object(inv_service, "_apply_inbound") as mock_inbound, \
         patch.object(inv_service, "_write_transaction") as mock_write_tx, \
         patch.object(inv_service, "_record_movement") as mock_record_mov:
        payload = {
            "event_id": "evt-sal-ret-1",
            "document_id": doc.document_id,
            "doc_type": "SALES_RETURN",
            "from_warehouse_id": None,
            "to_warehouse_id": 2,
            "items": [{"product_id": 202, "quantity": 2, "position_id": 10, "lpn": "LPN-RET-01"}],
            "executed_by": "receiving_clerk",
        }
        res = inv_service.apply_document_movement(payload)
        assert res is not False

        mock_inbound.assert_called_once_with(
            202,
            2,
            2,
            position_id=10,
            lpn="LPN-RET-01",
            status="QUARANTINED",
            lot_number="",
        )

    # 4. QA Inspection on DocumentService
    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    doc_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "documents-service" / "src")
    if doc_src not in sys.path:
        sys.path.insert(0, doc_src)

    from app.modules.documents.application.services.document_service import DocumentService
    doc_service_qa = DocumentService(document_repo=mock_document_repo)

    qa_doc = doc_service_qa.inspect_qa_document(
        document_id=doc.document_id,
        inspected_by="qa_inspector",
        passed=True,
        note="All items pass quality check",
    )

    assert qa_doc.status == DocumentStatus.QA_INSPECTED


def test_return_documents_proto_serialization():
    """
    Test Protobuf serialization & deserialization for PURCHASE_RETURN and SALES_RETURN enum values.
    """
    from documents_service.gen.wms.documents.v1 import documents_pb2

    # Verify enum values
    assert documents_pb2.DocumentType.PURCHASE_RETURN == 6
    assert documents_pb2.DocumentType.SALES_RETURN == 7

    # Create proto Document request
    doc_msg = documents_pb2.Document(
        doc_type="PURCHASE_RETURN",
        from_warehouse_id=1,
        created_by="unit_test",
        note="Proto serialization test",
    )
    doc_msg.items.add(product_id=123, quantity=10, unit_price=99.99)

    # Serialize & Deserialize
    serialized = doc_msg.SerializeToString()
    deserialized = documents_pb2.Document()
    deserialized.ParseFromString(serialized)

    assert deserialized.doc_type == "PURCHASE_RETURN"
    assert deserialized.from_warehouse_id == 1
    assert len(deserialized.items) == 1
    assert deserialized.items[0].product_id == 123
    assert deserialized.items[0].quantity == 10
    assert abs(deserialized.items[0].unit_price - 99.99) < 1e-4

    # Create Sales Return Proto Document
    sales_doc = documents_pb2.Document(
        doc_type="SALES_RETURN",
        to_warehouse_id=2,
        customer_id=888,
        created_by="unit_test",
    )
    sales_serialized = sales_doc.SerializeToString()
    sales_deserialized = documents_pb2.Document()
    sales_deserialized.ParseFromString(sales_serialized)

    assert sales_deserialized.doc_type == "SALES_RETURN"
    assert sales_deserialized.to_warehouse_id == 2
    assert sales_deserialized.customer_id == 888
