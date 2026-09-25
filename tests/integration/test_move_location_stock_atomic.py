"""
Integration & Concurrency Tests for Atomic MoveLocationStock with Dual Row-Lock (TASK-076 / DOM-01).

Acceptance Criteria:
1. inventory.proto contains MoveLocationStock RPC with Request and Response schemas.
2. InventoryServiceServicer implements MoveLocationStock:
   - Sắp xếp thứ tự khóa ID min/max chống deadlock khi chuyển hàng qua lại giữa 2 ô kệ.
   - Cập nhật đồng bộ số lượng thực tế tại inventory_locations của cả ô nguồn và ô đích.
   - Ghi sổ nhật ký giao dịch LOCATION_TRANSFER và đồng bộ Read-Model warehouse_inventory.
3. Concurrency test: Kiểm thử chuyển hàng đồng thời giữa 2 ô kệ không bị race condition hoặc deadlock.
"""

from __future__ import annotations

import concurrent.futures
import time
from unittest.mock import MagicMock, patch

import pytest
from app.modules.inventory.application.services.inventory_service import (
    InventoryService,
)
from app.modules.inventory.infrastructure.models.draft_proposal import (
    DraftProposalModel,
)
from app.modules.inventory.infrastructure.models.inventory_location import (
    InventoryLocationModel,
)
from app.modules.inventory.infrastructure.models.inventory_transaction import (
    InventoryTransactionModel,
)
from app.modules.inventory.infrastructure.models.movement_ledger import (
    InventoryMovementLedgerModel,
)
from app.modules.inventory.infrastructure.models.position import PositionModel
from app.modules.inventory.infrastructure.models.stock_reservation import (
    StockReservationModel,
)
from app.modules.inventory.infrastructure.models.warehouse_inventory import (
    WarehouseInventoryModel,
)
from app.modules.inventory.infrastructure.repositories.inventory_repo import (
    InventoryRepo,
)
from app.shared.core.database import Base
from inventory_service.gen.wms.inventory.v1 import inventory_pb2
from inventory_service.grpc_servicer import InventoryServiceServicer
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def atomic_db_engine(tmp_path):
    """File-based SQLite engine with WAL mode and BEGIN IMMEDIATE for reliable cross-thread concurrency."""
    db_file = tmp_path / "test_atomic_move.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(
        db_url,
        connect_args={"timeout": 60, "check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA busy_timeout=60000;")

    Base.metadata.create_all(
        bind=engine,
        tables=[
            WarehouseInventoryModel.__table__,
            InventoryLocationModel.__table__,
            PositionModel.__table__,
            StockReservationModel.__table__,
            DraftProposalModel.__table__,
            InventoryTransactionModel.__table__,
            InventoryMovementLedgerModel.__table__,
        ],
    )
    yield engine
    engine.dispose()


@pytest.fixture
def atomic_session(atomic_db_engine):
    Session = sessionmaker(bind=atomic_db_engine)
    session = Session()
    yield session
    session.close()


def test_grpc_move_location_stock_success(atomic_session, atomic_db_engine):
    """Verify MoveLocationStock atomically decrements source and increments destination"""
    # 1. Setup Initial Inventory
    product_id = 101
    warehouse_id = 1
    pos_source = 10
    pos_dest = 20

    repo = InventoryRepo(atomic_session)
    # Seed Source Location with 50 units
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=pos_source,
        product_id=product_id,
        quantity_delta=50,
        lot_number="LOT-2026-A",
    )
    atomic_session.commit()

    # 2. Invoke gRPC Servicer
    servicer = InventoryServiceServicer()
    request = inventory_pb2.MoveLocationStockRequest(
        product_id=product_id,
        warehouse_id=warehouse_id,
        from_position_id=pos_source,
        to_position_id=pos_dest,
        quantity=20,
        lot_number="LOT-2026-A",
        user_id="operator-alice",
    )

    with patch("inventory_service.grpc_servicer.get_db_session") as mock_db:
        mock_db.return_value.__enter__.return_value = atomic_session
        mock_db.return_value.__exit__.side_effect = lambda *args: atomic_session.commit()
        context = MagicMock()
        response = servicer.MoveLocationStock(request, context)

    # 3. Assertions on Response
    assert response.success is True, f"MoveLocationStock failed: {response.message}"
    assert response.from_location.position_id == pos_source
    assert response.from_location.quantity == 30
    assert response.to_location.position_id == pos_dest
    assert response.to_location.quantity == 20
    assert response.transaction_id > 0

    # 4. Verify Database State
    source_loc = atomic_session.execute(
        select(InventoryLocationModel).where(
            InventoryLocationModel.warehouse_id == warehouse_id,
            InventoryLocationModel.position_id == pos_source,
            InventoryLocationModel.product_id == product_id,
        )
    ).scalar_one()
    dest_loc = atomic_session.execute(
        select(InventoryLocationModel).where(
            InventoryLocationModel.warehouse_id == warehouse_id,
            InventoryLocationModel.position_id == pos_dest,
            InventoryLocationModel.product_id == product_id,
        )
    ).scalar_one()

    assert source_loc.quantity == 30
    assert dest_loc.quantity == 20
    assert dest_loc.lot_number == "LOT-2026-A"

    # Total physical stock in warehouse_inventory must remain 50
    wh_inv = atomic_session.execute(
        select(WarehouseInventoryModel).where(
            WarehouseInventoryModel.warehouse_id == warehouse_id,
            WarehouseInventoryModel.product_id == product_id,
        )
    ).scalar_one()
    assert wh_inv.physical_qty == 50
    assert wh_inv.quantity == 50


def test_grpc_move_location_stock_insufficient_stock_rejected(atomic_session, atomic_db_engine):
    """Verify MoveLocationStock rejects transfer when source has insufficient available stock"""
    product_id = 202
    warehouse_id = 1
    pos_source = 15
    pos_dest = 25

    repo = InventoryRepo(atomic_session)
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=pos_source,
        product_id=product_id,
        quantity_delta=10,
    )
    atomic_session.commit()

    servicer = InventoryServiceServicer()
    request = inventory_pb2.MoveLocationStockRequest(
        product_id=product_id,
        warehouse_id=warehouse_id,
        from_position_id=pos_source,
        to_position_id=pos_dest,
        quantity=25,  # Requesting 25 when only 10 available
    )

    with patch("inventory_service.grpc_servicer.get_db_session") as mock_db:
        mock_db.return_value.__enter__.return_value = atomic_session
        mock_db.return_value.__exit__.side_effect = lambda *args: atomic_session.commit()
        context = MagicMock()
        response = servicer.MoveLocationStock(request, context)

    assert response.success is False
    assert "Insufficient" in response.message

    # Verify no stock was transferred
    source_loc = atomic_session.execute(
        select(InventoryLocationModel).where(
            InventoryLocationModel.warehouse_id == warehouse_id,
            InventoryLocationModel.position_id == pos_source,
            InventoryLocationModel.product_id == product_id,
        )
    ).scalar_one()
    assert source_loc.quantity == 10


def test_grpc_move_location_stock_same_position_rejected(atomic_session, atomic_db_engine):
    """Verify MoveLocationStock rejects moving to the same location"""
    product_id = 303
    warehouse_id = 1
    pos = 11

    repo = InventoryRepo(atomic_session)
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=pos,
        product_id=product_id,
        quantity_delta=20,
    )
    atomic_session.commit()

    servicer = InventoryServiceServicer()
    request = inventory_pb2.MoveLocationStockRequest(
        product_id=product_id,
        warehouse_id=warehouse_id,
        from_position_id=pos,
        to_position_id=pos,
        quantity=5,
    )

    with patch("inventory_service.grpc_servicer.get_db_session") as mock_db:
        mock_db.return_value.__enter__.return_value = atomic_session
        mock_db.return_value.__exit__.side_effect = lambda *args: atomic_session.commit()
        context = MagicMock()
        response = servicer.MoveLocationStock(request, context)

    assert response.success is False
    assert "same" in response.message.lower()


def test_move_location_stock_concurrent_bidirectional_no_deadlock(atomic_db_engine):
    """
    Concurrency Test (TASK-076):
    Multiple workers concurrently transfer stock bidirectionally between Pos 100 and Pos 200.
    Deterministic Dual Row-Lock ordering (min_pos -> max_pos) eliminates deadlocks and race conditions.
    """
    product_id = 404
    warehouse_id = 1
    pos_a = 100
    pos_b = 200

    # Seed initial inventory: 100 units at Pos A, 100 units at Pos B (Total = 200)
    init_session = sessionmaker(bind=atomic_db_engine)()
    repo = InventoryRepo(init_session)
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=pos_a,
        product_id=product_id,
        quantity_delta=100,
    )
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=pos_b,
        product_id=product_id,
        quantity_delta=100,
    )
    init_session.commit()
    init_session.close()

    def do_transfer(from_pos: int, to_pos: int, qty: int) -> bool:
        for attempt in range(5):
            session = sessionmaker(bind=atomic_db_engine)()
            try:
                service = InventoryService(
                    inventory_repo=InventoryRepo(session),
                    event_publisher=MagicMock(),
                )
                service.move_location_stock(
                    product_id=product_id,
                    from_warehouse_id=warehouse_id,
                    from_position_id=from_pos,
                    to_position_id=to_pos,
                    quantity=qty,
                )
                session.commit()
                return True
            except Exception:
                session.rollback()
                time.sleep(0.05 * (attempt + 1))
            finally:
                session.close()
        return False

    # Launch concurrent transfers in opposite directions:
    # 5 workers: Pos A -> Pos B (5 units each)
    # 5 workers: Pos B -> Pos A (5 units each)
    transfers = []
    for _ in range(5):
        transfers.append((pos_a, pos_b, 5))
        transfers.append((pos_b, pos_a, 5))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(do_transfer, f, t, q) for f, t, q in transfers]
        results = [fut.result() for fut in concurrent.futures.as_completed(futures)]

    # All transfers should succeed without deadlock
    assert all(results), f"Some transfers failed: {results}"

    # Invariant: Total stock across Pos A + Pos B must strictly equal 200
    verify_session = sessionmaker(bind=atomic_db_engine)()
    loc_a = verify_session.execute(
        select(InventoryLocationModel).where(
            InventoryLocationModel.warehouse_id == warehouse_id,
            InventoryLocationModel.position_id == pos_a,
            InventoryLocationModel.product_id == product_id,
        )
    ).scalar_one()
    loc_b = verify_session.execute(
        select(InventoryLocationModel).where(
            InventoryLocationModel.warehouse_id == warehouse_id,
            InventoryLocationModel.position_id == pos_b,
            InventoryLocationModel.product_id == product_id,
        )
    ).scalar_one()

    assert loc_a.quantity + loc_b.quantity == 200, (
        f"Stock conservation violated: Pos A ({loc_a.quantity}) + Pos B ({loc_b.quantity}) != 200"
    )
    assert loc_a.quantity == 100
    assert loc_b.quantity == 100

    verify_session.close()
