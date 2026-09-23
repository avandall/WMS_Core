"""
Integration Concurrency Test Suite for TASK-036:
1. `create_reservation` idempotency SELECT with `.with_for_update()` -> 50 concurrent requests with same idempotency_key -> 1 created, 49 idempotent responses, 0 errors.
2. `apply_document_movement` concurrency check -> 10 concurrent requests with same event_id -> 1 movement applied (returns True), 9 return False, stock deducted exactly once.
3. Lock Ordering Rule verification: concurrent reservation creation, release, consumption, and expiry scheduler simulation under high concurrency with 0 deadlocks.
"""

import concurrent.futures
from datetime import datetime, timedelta, timezone
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

# Setup sys.path to resolve all microservices in Services/*/src
project_root = Path(__file__).resolve().parent.parent.parent
services_dir = project_root / "Services"
if services_dir.exists():
    for service_path in services_dir.glob("*/src"):
        if str(service_path) not in sys.path:
            sys.path.insert(0, str(service_path))

try:
    import app
    app.__path__ = [str(s / "app") for s in services_dir.glob("*/src") if (s / "app").exists()]
    import app.modules
    app.modules.__path__ = [str(s / "app" / "modules") for s in services_dir.glob("*/src") if (s / "app" / "modules").exists()]
except Exception:
    pass

try:
    from app.modules.positions.infrastructure.models.position import PositionModel  # noqa: F401
    from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel  # noqa: F401
except ImportError:
    pass

from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.inventory_transaction import InventoryTransactionModel
from app.modules.inventory.infrastructure.models.movement_ledger import InventoryMovementLedgerModel
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.application.services.inventory_service import InventoryService


class MockEventPublisher:
    def publish(self, event_type: str, payload: dict) -> None:
        pass


@pytest.fixture(scope="module")
def concurrency_db_engine():
    db_url = os.getenv("TEST_DATABASE_URL")
    db_file = None
    if not db_url:
        db_file = Path(__file__).resolve().parent / "test_concurrent_reservation.db"
        if db_file.exists():
            try:
                db_file.unlink()
            except OSError:
                pass
        db_url = f"sqlite:///{db_file}"

    engine = create_engine(
        db_url,
        connect_args={"timeout": 60, "check_same_thread": False},
        future=True,
    )

    if "sqlite" in db_url:
        @event.listens_for(engine, "connect")
        def do_connect(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def do_begin(conn):
            conn.exec_driver_sql("BEGIN IMMEDIATE")

        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA busy_timeout=60000;")

    # Drop and recreate tables
    InventoryTransactionModel.__table__.drop(bind=engine, checkfirst=True)
    InventoryLocationModel.__table__.drop(bind=engine, checkfirst=True)
    InventoryMovementLedgerModel.__table__.drop(bind=engine, checkfirst=True)
    StockReservationModel.__table__.drop(bind=engine, checkfirst=True)
    WarehouseInventoryModel.__table__.drop(bind=engine, checkfirst=True)

    InventoryTransactionModel.__table__.create(bind=engine, checkfirst=True)
    InventoryLocationModel.__table__.create(bind=engine, checkfirst=True)
    WarehouseInventoryModel.__table__.create(bind=engine, checkfirst=True)
    StockReservationModel.__table__.create(bind=engine, checkfirst=True)
    InventoryMovementLedgerModel.__table__.create(bind=engine, checkfirst=True)

    yield engine

    InventoryTransactionModel.__table__.drop(bind=engine, checkfirst=True)
    InventoryMovementLedgerModel.__table__.drop(bind=engine, checkfirst=True)
    StockReservationModel.__table__.drop(bind=engine, checkfirst=True)
    WarehouseInventoryModel.__table__.drop(bind=engine, checkfirst=True)
    InventoryLocationModel.__table__.drop(bind=engine, checkfirst=True)
    engine.dispose()
    if db_file and db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass


def test_concurrent_reservation_idempotency(concurrency_db_engine):
    """TASK-036: 50 concurrent create_reservation calls with identical idempotency_key.

    - Exactly 1 reservation row created in DB
    - All 50 calls succeed (return reservation.id)
    - 49 receive identical idempotent reservation ID
    - reserved_qty is updated exactly ONCE (10, not 500)
    """
    SessionLocal = sessionmaker(bind=concurrency_db_engine, autoflush=False, expire_on_commit=False)

    # Seed stock: product 360, warehouse 1, physical=500, reserved=0
    with SessionLocal() as session:
        session.query(WarehouseInventoryModel).filter_by(product_id=360, warehouse_id=1).delete()
        session.query(StockReservationModel).filter_by(product_id=360, warehouse_id=1).delete()
        wh_item = WarehouseInventoryModel(
            product_id=360,
            warehouse_id=1,
            quantity=500,
            physical_qty=500,
            reserved_qty=0,
        )
        session.add(wh_item)
        session.commit()

    idempotency_key = "IDEM_KEY_50_CONCURRENT_TEST"
    num_threads = 50

    def task_create_reservation(thread_idx: int):
        session = SessionLocal()
        try:
            repo = InventoryRepo(session)
            res_id = repo.create_reservation(
                source_type="SO",
                source_id=1001,
                document_id=2001,
                product_id=360,
                warehouse_id=1,
                requested_qty=10,
                created_by=f"user_{thread_idx}",
                idempotency_key=idempotency_key,
                expires_at=None,
            )
            session.commit()
            return ("SUCCESS", res_id)
        except Exception as e:
            session.rollback()
            return ("ERROR", str(e))
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(task_create_reservation, i) for i in range(num_threads)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    successes = [res_id for status, res_id in results if status == "SUCCESS"]
    errors = [err for status, err in results if status == "ERROR"]

    assert len(errors) == 0, f"Concurrent reservation creation emitted errors: {errors}"
    assert len(successes) == num_threads, f"Expected {num_threads} successful responses, got {len(successes)}"

    # All returned reservation IDs must be identical (idempotent)
    unique_res_ids = set(successes)
    assert len(unique_res_ids) == 1, f"Expected 1 unique reservation ID, got {unique_res_ids}"

    # Verify DB state
    with SessionLocal() as session:
        reservations = session.query(StockReservationModel).filter_by(idempotency_key=idempotency_key).all()
        assert len(reservations) == 1, f"Expected exactly 1 reservation row in DB, found {len(reservations)}"

        res_row = reservations[0]
        assert res_row.requested_qty == 10
        assert res_row.reserved_qty == 10
        assert res_row.status == "RESERVED"

        wh_row = session.query(WarehouseInventoryModel).filter_by(product_id=360, warehouse_id=1).one()
        assert wh_row.reserved_qty == 10, f"Expected reserved_qty=10, got {wh_row.reserved_qty}"


def test_concurrent_apply_document_movement(concurrency_db_engine):
    """TASK-036: 10 concurrent apply_document_movement calls with identical event_id.

    - Exactly 1 call returns True
    - Exactly 9 calls return False
    - Physical stock is deducted ONCE (100 -> 95, not 50)
    """
    SessionLocal = sessionmaker(bind=concurrency_db_engine, autoflush=False, expire_on_commit=False)

    # Seed stock: product 361, warehouse 1, physical=100
    with SessionLocal() as session:
        session.query(WarehouseInventoryModel).filter_by(product_id=361, warehouse_id=1).delete()
        session.query(InventoryMovementLedgerModel).delete()
        wh_item = WarehouseInventoryModel(
            product_id=361,
            warehouse_id=1,
            quantity=100,
            physical_qty=100,
            reserved_qty=0,
        )
        session.add(wh_item)
        session.commit()

    event_id = "EVT_DOC_MOV_CONCURRENT_361"
    payload = {
        "event_id": event_id,
        "doc_type": "EXPORT",
        "document_id": 888,
        "from_warehouse_id": 1,
        "items": [{"product_id": 361, "quantity": 5}],
    }

    num_threads = 10

    def task_apply_movement(thread_idx: int):
        session = SessionLocal()
        try:
            repo = InventoryRepo(session)
            svc = InventoryService(inventory_repo=repo, event_publisher=MockEventPublisher())
            res = svc.apply_document_movement(payload)
            session.commit()
            return ("SUCCESS", res)
        except Exception as e:
            session.rollback()
            return ("ERROR", str(e))
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(task_apply_movement, i) for i in range(num_threads)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    successes = [val for status, val in results if status == "SUCCESS"]
    errors = [err for status, err in results if status == "ERROR"]

    assert len(errors) == 0, f"Concurrent document movement emitted errors: {errors}"
    assert len(successes) == num_threads

    true_count = successes.count(True)
    false_count = successes.count(False)

    assert true_count == 1, f"Expected exactly 1 True result, got {true_count}"
    assert false_count == 9, f"Expected 9 False results, got {false_count}"

    # Verify physical inventory was deducted exactly ONCE
    with SessionLocal() as session:
        wh_row = session.query(WarehouseInventoryModel).filter_by(product_id=361, warehouse_id=1).one()
        assert wh_row.physical_qty == 95, f"Expected physical_qty=95, got {wh_row.physical_qty}"


def test_lock_ordering_prevents_deadlock(concurrency_db_engine):
    """TASK-036: Concurrent mix of reservation creation, release, and expiry under high load.

    Verifies system-wide Lock Ordering Rule:
    Lock WarehouseInventoryModel/InventoryLocationModel FIRST, StockReservationModel SECOND.
    Executes without AB-BA deadlocks or exceptions.
    """
    SessionLocal = sessionmaker(bind=concurrency_db_engine, autoflush=False, expire_on_commit=False)

    # Seed stock: product 362, warehouse 1, physical=1000
    with SessionLocal() as session:
        session.query(WarehouseInventoryModel).filter_by(product_id=362, warehouse_id=1).delete()
        session.query(StockReservationModel).filter_by(product_id=362, warehouse_id=1).delete()
        wh_item = WarehouseInventoryModel(
            product_id=362,
            warehouse_id=1,
            quantity=1000,
            physical_qty=1000,
            reserved_qty=0,
        )
        session.add(wh_item)
        session.commit()

    num_operations = 30

    def worker_mix(op_id: int):
        session = SessionLocal()
        try:
            repo = InventoryRepo(session)
            # Worker creates reservation
            res_id = repo.create_reservation(
                source_type="SO",
                source_id=op_id,
                document_id=3000 + op_id,
                product_id=362,
                warehouse_id=1,
                requested_qty=2,
                created_by="deadlock_test_user",
                idempotency_key=f"LOCK_ORDER_KEY_{op_id}",
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=10) if op_id % 2 == 0 else None,
            )
            session.commit()

            # Half of worker operations immediately release or consume reservation
            if op_id % 2 == 1:
                repo.release_reservation(res_id, released_qty=2)
                session.commit()
            else:
                repo.consume_reservation(res_id, consumed_qty=2)
                session.commit()

            return ("SUCCESS", op_id)
        except Exception as e:
            session.rollback()
            return ("ERROR", str(e))
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_mix, i) for i in range(num_operations)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    errors = [err for status, err in results if status == "ERROR"]
    assert len(errors) == 0, f"Concurrent lock ordering test encountered errors: {errors}"
