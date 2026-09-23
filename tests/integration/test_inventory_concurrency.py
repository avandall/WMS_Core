"""
Integration test for concurrency race condition & lost update prevention in InventoryRepo.
TASK-005: Verifies that 50 concurrent orders contending for 10 available stock items:
- Exactly 10 orders succeed
- Exactly 40 orders fail with InsufficientStockError
- Final stock is exactly 0 (never negative)
"""

import concurrent.futures
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
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
    for s in services_dir.glob("*/src"):
        p = str(s / "app")
        if os.path.exists(p) and p not in app.__path__:
            app.__path__.append(p)
    import app.modules
    for s in services_dir.glob("*/src"):
        p = str(s / "app" / "modules")
        if os.path.exists(p) and p not in app.modules.__path__:
            app.modules.__path__.append(p)
except Exception:
    pass

# Import PositionModel to ensure WarehouseModel relationships initialize cleanly in SQLAlchemy
try:
    from app.modules.positions.infrastructure.models.position import PositionModel  # noqa: F401
except ImportError:
    pass

from app.modules.inventory.infrastructure.models.warehouse_inventory import (
    WarehouseInventoryModel,
)
from app.modules.inventory.infrastructure.models.stock_reservation import (
    StockReservationModel,
)
from app.modules.inventory.infrastructure.repositories.inventory_repo import (
    InventoryRepo,
)
from app.shared.core.database import Base
from app.shared.domain.business_exceptions import InsufficientStockError


@pytest.fixture(scope="module")
def concurrency_engine():
    db_url = os.getenv("TEST_DATABASE_URL")
    db_file = None
    if not db_url:
        db_file = Path(__file__).resolve().parent / "test_concurrency.db"
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

    # Create tables
    WarehouseInventoryModel.__table__.drop(bind=engine, checkfirst=True)
    StockReservationModel.__table__.drop(bind=engine, checkfirst=True)
    WarehouseInventoryModel.__table__.create(bind=engine, checkfirst=True)
    StockReservationModel.__table__.create(bind=engine, checkfirst=True)

    yield engine

    StockReservationModel.__table__.drop(bind=engine, checkfirst=True)
    WarehouseInventoryModel.__table__.drop(bind=engine, checkfirst=True)
    engine.dispose()
    if db_file and db_file.exists():
        for _ in range(3):
            try:
                db_file.unlink()
                break
            except OSError:
                pass


def test_adjust_warehouse_quantity_concurrency_50_threads(concurrency_engine):
    """
    Simulate 50 concurrent threads attempting to deduct 1 unit from 10 initial units via adjust_warehouse_quantity.
    Expectation:
    - 10 successful deductions
    - 40 InsufficientStockError exceptions
    - Final stock == 0
    """
    SessionMaker = sessionmaker(bind=concurrency_engine, autoflush=False, autocommit=False)

    # 1. Seed initial inventory: product_id=100, warehouse_id=1, initial quantity=10
    seed_session = SessionMaker()
    repo = InventoryRepo(seed_session)
    repo.adjust_warehouse_quantity(product_id=100, warehouse_id=1, quantity_delta=10)
    seed_session.commit()
    seed_session.close()

    # Verify initial quantity
    check_session = SessionMaker()
    wh = (
        check_session.query(WarehouseInventoryModel)
        .filter_by(product_id=100, warehouse_id=1)
        .one()
    )
    assert wh.quantity == 10
    assert wh.physical_qty == 10
    check_session.close()

    success_count = 0
    insufficient_error_count = 0
    other_errors = []

    def attempt_deduct(thread_id: int):
        session = SessionMaker()
        try:
            repo = InventoryRepo(session)
            # Each thread tries to deduct 1 unit
            repo.adjust_warehouse_quantity(product_id=100, warehouse_id=1, quantity_delta=-1)
            session.commit()
            return "SUCCESS"
        except InsufficientStockError:
            session.rollback()
            return "INSUFFICIENT"
        except Exception as e:
            session.rollback()
            return f"ERROR: {type(e).__name__}: {e}"
        finally:
            session.close()

    # 2. Execute 50 concurrent threads
    num_threads = 50
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(attempt_deduct, i) for i in range(num_threads)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    for res in results:
        if res == "SUCCESS":
            success_count += 1
        elif res == "INSUFFICIENT":
            insufficient_error_count += 1
        else:
            other_errors.append(res)

    assert not other_errors, f"Unexpected errors during execution: {other_errors}"
    assert success_count == 10, f"Expected 10 successes, got {success_count}"
    assert insufficient_error_count == 40, f"Expected 40 InsufficientStockError, got {insufficient_error_count}"

    # 3. Verify final stock is exactly 0
    final_session = SessionMaker()
    wh = (
        final_session.query(WarehouseInventoryModel)
        .filter_by(product_id=100, warehouse_id=1)
        .one()
    )
    assert wh.quantity == 0
    assert wh.physical_qty == 0
    final_session.close()


def test_create_reservation_concurrency_50_threads(concurrency_engine):
    """
    Simulate 50 concurrent threads attempting to reserve 1 unit from 10 physical units via create_reservation.
    Expectation:
    - 10 successful reservations
    - 40 InsufficientStockError exceptions
    - Available stock == 0 (physical=10, reserved=10)
    """
    SessionMaker = sessionmaker(bind=concurrency_engine, autoflush=False, autocommit=False)

    # Seed initial inventory: product_id=200, warehouse_id=1, physical_qty=10, reserved_qty=0
    seed_session = SessionMaker()
    repo = InventoryRepo(seed_session)
    repo.adjust_warehouse_quantity(product_id=200, warehouse_id=1, quantity_delta=10)
    seed_session.commit()
    seed_session.close()

    success_count = 0
    insufficient_error_count = 0
    other_errors = []

    def attempt_reserve(thread_id: int):
        session = SessionMaker()
        try:
            repo = InventoryRepo(session)
            repo.create_reservation(
                source_type="order",
                source_id=thread_id + 1,
                document_id=None,
                product_id=200,
                warehouse_id=1,
                requested_qty=1,
                created_by=f"thread_{thread_id}",
                idempotency_key=f"res_key_{thread_id}",
                expires_at=None,
            )
            session.commit()
            return "SUCCESS"
        except InsufficientStockError:
            session.rollback()
            return "INSUFFICIENT"
        except Exception as e:
            session.rollback()
            return f"ERROR: {type(e).__name__}: {e}"
        finally:
            session.close()

    num_threads = 50
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(attempt_reserve, i) for i in range(num_threads)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    for res in results:
        if res == "SUCCESS":
            success_count += 1
        elif res == "INSUFFICIENT":
            insufficient_error_count += 1
        else:
            other_errors.append(res)

    assert not other_errors, f"Unexpected errors: {other_errors}"
    assert success_count == 10, f"Expected 10 successes, got {success_count}"
    assert insufficient_error_count == 40, f"Expected 40 InsufficientStockError, got {insufficient_error_count}"

    final_session = SessionMaker()
    wh = (
        final_session.query(WarehouseInventoryModel)
        .filter_by(product_id=200, warehouse_id=1)
        .one()
    )
    assert wh.physical_qty == 10
    assert wh.reserved_qty == 10
    assert (wh.physical_qty - wh.reserved_qty) == 0
    final_session.close()
