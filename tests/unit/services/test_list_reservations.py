"""
Unit tests for TASK-009: API Gateway & Inventory Service ListReservations optimization
Validates that document_id filtering works at DB level, preventing O(N) memory overhead.
"""

import sys
from pathlib import Path

# Purge any previously imported 'app' module to avoid cross-service namespace collisions
for mod in list(sys.modules.keys()):
    if mod == "app" or mod.startswith("app."):
        del sys.modules[mod]

inv_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "inventory-service" / "src")
sys.path = [p for p in sys.path if "/Services/" not in p]
sys.path.insert(0, inv_src)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from app.shared.core.database import Base
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from inventory_service.gen.wms.inventory.v1 import inventory_pb2
from inventory_service.grpc_servicer import InventoryServiceServicer


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create dummy warehouse inventory
    wh_inv = WarehouseInventoryModel(
        product_id=1,
        warehouse_id=1,
        quantity=1000,
        physical_qty=1000,
        reserved_qty=0,
    )
    session.add(wh_inv)
    session.commit()

    yield session
    session.close()


def test_list_reservations_request_proto_has_document_id():
    """Verify ListReservationsRequest proto message supports document_id field."""
    req = inventory_pb2.ListReservationsRequest(document_id=99, status="RESERVED")
    assert req.document_id == 99
    assert req.status == "RESERVED"


def test_repo_list_reservations_filters_by_document_id(db_session):
    """Verify InventoryRepo.list_reservations filters by document_id in SQL query."""
    repo = InventoryRepo(db_session)

    # Create reservations for document 101 and document 102
    res1_id = repo.create_reservation(
        source_type="DOCUMENT",
        source_id=1,
        document_id=101,
        product_id=1,
        warehouse_id=1,
        requested_qty=10,
        created_by="test_user",
        idempotency_key="key_1",
        expires_at=None,
    )

    res2_id = repo.create_reservation(
        source_type="DOCUMENT",
        source_id=2,
        document_id=102,
        product_id=1,
        warehouse_id=1,
        requested_qty=20,
        created_by="test_user",
        idempotency_key="key_2",
        expires_at=None,
    )

    # Fetch without document_id filter
    all_res = repo.list_reservations(status="RESERVED")
    assert len(all_res) == 2

    # Fetch with document_id=101 filter
    doc101_res = repo.list_reservations(document_id=101, status="RESERVED")
    assert len(doc101_res) == 1
    assert doc101_res[0]["id"] == res1_id
    assert doc101_res[0]["document_id"] == 101

    # Fetch with document_id=102 filter
    doc102_res = repo.list_reservations(document_id=102, status="RESERVED")
    assert len(doc102_res) == 1
    assert doc102_res[0]["id"] == res2_id
    assert doc102_res[0]["document_id"] == 102

    # Fetch with non-existent document_id
    empty_res = repo.list_reservations(document_id=999, status="RESERVED")
    assert len(empty_res) == 0


def test_servicer_list_reservations_passes_document_id(db_session):
    """Verify InventoryServicer.ListReservations extracts document_id from gRPC request."""
    repo = InventoryRepo(db_session)

    repo.create_reservation(
        source_type="DOCUMENT",
        source_id=1,
        document_id=200,
        product_id=1,
        warehouse_id=1,
        requested_qty=5,
        created_by="user1",
        idempotency_key="k1",
        expires_at=None,
    )

    servicer = InventoryServiceServicer()
    servicer._service = lambda: (MagicMock(inventory_repo=repo), db_session)

    context = MagicMock()
    request = inventory_pb2.ListReservationsRequest(document_id=200, status="RESERVED")
    response = servicer.ListReservations(request, context)

    assert len(response.reservations) == 1
    assert response.reservations[0].document_id == 200

    # Request with different document_id
    req_other = inventory_pb2.ListReservationsRequest(document_id=999, status="RESERVED")
    resp_other = servicer.ListReservations(req_other, context)
    assert len(resp_other.reservations) == 0
