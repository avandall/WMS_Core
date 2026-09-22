from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.shared.core.database import Base, import_all_models
from app.shared.domain.business_exceptions import InsufficientStockError, InvalidQuantityError
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.application.services.allocation_service import AllocationService
from app.modules.inventory.application.services.inventory_service import InventoryService



@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    import_all_models()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_inventory_location_lot_mfg_expiry_schema(db_session):
    repo = InventoryRepo(db_session)
    now = datetime.now(timezone.utc)
    mfg = now - timedelta(days=30)
    exp = now + timedelta(days=180)

    res = repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=101,
        product_id=500,
        quantity_delta=50,
        allocated_delta=0,
        lpn="LPN-001",
        status="AVAILABLE",
        lot_number="LOT-2026-A",
        mfg_date=mfg,
        expiry_date=exp,
    )

    assert res["lot_number"] == "LOT-2026-A"
    assert res["mfg_date"] == mfg.isoformat()
    assert res["expiry_date"] == exp.isoformat()

    locs = repo.get_inventory_locations(warehouse_id=1, product_id=500, lot_number="LOT-2026-A")
    assert len(locs) == 1
    assert locs[0]["lot_number"] == "LOT-2026-A"
    assert locs[0]["available_qty"] == 50


def test_fefo_allocation_sorts_by_nearest_expiry(db_session):
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    now = datetime.now(timezone.utc)
    exp_near = now + timedelta(days=10)
    exp_mid = now + timedelta(days=30)
    exp_far = now + timedelta(days=60)

    # Bin 1: Far expiry (60 days)
    repo.adjust_location_quantity(
        warehouse_id=1, position_id=1, product_id=100, quantity_delta=10, lpn="LPN-1",
        lot_number="LOT-FAR", expiry_date=exp_far,
    )

    # Bin 2: Near expiry (10 days) -> Should be allocated FIRST
    repo.adjust_location_quantity(
        warehouse_id=1, position_id=2, product_id=100, quantity_delta=10, lpn="LPN-2",
        lot_number="LOT-NEAR", expiry_date=exp_near,
    )

    # Bin 3: Mid expiry (30 days) -> Should be allocated SECOND
    repo.adjust_location_quantity(
        warehouse_id=1, position_id=3, product_id=100, quantity_delta=10, lpn="LPN-3",
        lot_number="LOT-MID", expiry_date=exp_mid,
    )

    # Request allocation of 15 units
    allocations = alloc_service.allocate_fefo(warehouse_id=1, product_id=100, quantity=15)

    assert len(allocations) == 2
    # First 10 units allocated from LOT-NEAR (position 2)
    assert allocations[0]["position_id"] == 2
    assert allocations[0]["lot_number"] == "LOT-NEAR"
    assert allocations[0]["allocated_qty"] == 10

    # Remaining 5 units allocated from LOT-MID (position 3)
    assert allocations[1]["position_id"] == 3
    assert allocations[1]["lot_number"] == "LOT-MID"
    assert allocations[1]["allocated_qty"] == 5


def test_fefo_allocation_fallback_null_expiry(db_session):
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    now = datetime.now(timezone.utc)
    exp_date = now + timedelta(days=20)

    # Bin with no expiry date
    repo.adjust_location_quantity(
        warehouse_id=1, position_id=1, product_id=200, quantity_delta=10, lpn="LPN-NO-EXP",
        lot_number="LOT-NO-EXP", expiry_date=None,
    )

    # Bin with expiry date -> Should be allocated BEFORE null expiry
    repo.adjust_location_quantity(
        warehouse_id=1, position_id=2, product_id=200, quantity_delta=10, lpn="LPN-EXP",
        lot_number="LOT-EXP", expiry_date=exp_date,
    )

    allocations = alloc_service.allocate_fefo(warehouse_id=1, product_id=200, quantity=5)

    assert len(allocations) == 1
    assert allocations[0]["position_id"] == 2
    assert allocations[0]["lot_number"] == "LOT-EXP"
    assert allocations[0]["allocated_qty"] == 5


def test_fefo_allocation_insufficient_stock(db_session):
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    repo.adjust_location_quantity(
        warehouse_id=1, position_id=1, product_id=300, quantity_delta=10, lpn="LPN-1",
        lot_number="LOT-1",
    )

    with pytest.raises(InsufficientStockError):
        alloc_service.allocate_fefo(warehouse_id=1, product_id=300, quantity=20)


def test_fefo_allocation_invalid_quantity(db_session):
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    with pytest.raises(InvalidQuantityError):
        alloc_service.allocate_fefo(warehouse_id=1, product_id=300, quantity=0)


def test_product_recall_query(db_session):
    from unittest.mock import MagicMock, patch
    from inventory_service.gen.wms.documents.v1 import documents_pb2

    repo = InventoryRepo(db_session)
    inv_service = InventoryService(repo)

    # Add lot in inventory location
    repo.adjust_location_quantity(
        warehouse_id=1, position_id=10, product_id=999, quantity_delta=100, lpn="LPN-RECALL",
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
        recall_res = inv_service.recall_query("LOT-RECALL-99")

    assert recall_res["lot_number"] == "LOT-RECALL-99"
    assert len(recall_res["locations"]) == 1
    assert recall_res["locations"][0]["position_id"] == 10
    assert recall_res["locations"][0]["quantity"] == 100

    assert len(recall_res["customers"]) == 1
    assert recall_res["customers"][0]["customer_id"] == 777
    assert recall_res["customers"][0]["document_id"] == 501
    assert recall_res["customers"][0]["quantity"] == 25
