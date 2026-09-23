"""
Integration Concurrency Test for Reservation Expiry Scheduler with Redis Distributed Lock & Lock Ordering Rule.

TASK-031 Acceptance Criteria:
- Expiry job acquires Redis Distributed Lock ('lock:reservation_expiry') before querying.
- Query SQL uses `SELECT ... FOR UPDATE SKIP LOCKED`.
- Adheres to Lock Ordering Rule: Lock inventory_locations & warehouse_inventory FIRST, StockReservationModel SECOND.
- Expired reservations (expires_at <= now, status='RESERVED') transition to 'EXPIRED' and reserved_qty is decremented.
- Concurrent execution of 5 workers simultaneously on real DB (PostgreSQL or SQLite fallback) + Redis runs cleanly without race condition or deadlock.
"""

import concurrent.futures
from datetime import datetime, timedelta, timezone
import os
import sys
from pathlib import Path

import pytest
import redis
from sqlalchemy import create_engine, select
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

try:
    from app.modules.positions.infrastructure.models.position import PositionModel  # noqa: F401
    from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel  # noqa: F401
except ImportError:
    pass

from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from inventory_service.jobs.expire_reservations import expire_expired_reservations


@pytest.fixture(scope="module")
def db_engine():
    db_url = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wms_test")
    db_file = None
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            pass
    except Exception:
        # Fallback to SQLite WAL for offline / isolated environments
        db_file = Path(__file__).resolve().parent / "test_expiry_concurrency.db"
        if db_file.exists():
            try:
                db_file.unlink()
            except OSError:
                pass
        db_url = f"sqlite:///{db_file}"
        engine = create_engine(db_url, connect_args={"timeout": 60, "check_same_thread": False})

    # Drop and recreate tables
    InventoryLocationModel.__table__.drop(bind=engine, checkfirst=True)
    StockReservationModel.__table__.drop(bind=engine, checkfirst=True)
    WarehouseInventoryModel.__table__.drop(bind=engine, checkfirst=True)

    InventoryLocationModel.__table__.create(bind=engine, checkfirst=True)
    WarehouseInventoryModel.__table__.create(bind=engine, checkfirst=True)
    StockReservationModel.__table__.create(bind=engine, checkfirst=True)

    yield engine

    StockReservationModel.__table__.drop(bind=engine, checkfirst=True)
    WarehouseInventoryModel.__table__.drop(bind=engine, checkfirst=True)
    InventoryLocationModel.__table__.drop(bind=engine, checkfirst=True)
    engine.dispose()
    if db_file and db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass


@pytest.fixture(scope="module")
def redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(redis_url)
        r.ping()
        yield r
    except Exception:
        pytest.skip("Real Redis is required for integration concurrency testing.")


def test_concurrent_reservation_expiry_workers(db_engine, redis_client):
    """
    Test 5 concurrent workers running expire_expired_reservations on PostgreSQL + Redis.
    Verifies that:
    1. Only 1 worker acquires Redis lock per run cycle (or workers process without duplicate releases).
    2. All expired reservations transition from RESERVED -> EXPIRED.
    3. Non-expired reservations stay RESERVED.
    4. Warehouse reserved_qty is correctly decremented.
    5. No AB-BA deadlock occurs.
    """
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    # Clear old locks in Redis
    redis_client.delete("lock:reservation_expiry")

    # 1. Seed initial data
    product_id = 901
    warehouse_id = 1
    initial_physical = 500
    initial_reserved = 100

    wh = WarehouseInventoryModel(
        product_id=product_id,
        warehouse_id=warehouse_id,
        physical_qty=initial_physical,
        reserved_qty=initial_reserved,
        quantity=initial_physical,
    )
    db.add(wh)

    loc = InventoryLocationModel(
        warehouse_id=warehouse_id,
        owner_id="DEFAULT_OWNER",
        position_id=10,
        product_id=product_id,
        lpn="LPN-TEST-EXP",
        lot_number="LOT-EXP",
        quantity=initial_physical,
        allocated_qty=initial_reserved,
        status="AVAILABLE",
    )
    db.add(loc)

    now = datetime.now(timezone.utc)
    expired_time = now - timedelta(minutes=10)
    future_time = now + timedelta(minutes=60)

    # Add 10 expired reservations (10 qty each = 100 total)
    expired_res_ids = []
    for i in range(10):
        res = StockReservationModel(
            source_type="order",
            source_id=i + 1,
            document_id=100 + i,
            product_id=product_id,
            warehouse_id=warehouse_id,
            requested_qty=10,
            reserved_qty=10,
            released_qty=0,
            status="RESERVED",
            expires_at=expired_time,
            idempotency_key=f"exp-key-{i}",
        )
        db.add(res)

    # Add 5 future non-expired reservations
    future_res_ids = []
    for i in range(5):
        res = StockReservationModel(
            source_type="order",
            source_id=i + 100,
            document_id=200 + i,
            product_id=product_id,
            warehouse_id=warehouse_id,
            requested_qty=5,
            reserved_qty=5,
            released_qty=0,
            status="RESERVED",
            expires_at=future_time,
            idempotency_key=f"fut-key-{i}",
        )
        db.add(res)

    db.commit()
    db.close()

    # 2. Run 5 concurrent worker threads invoking expire_expired_reservations
    results = []

    def worker_task(worker_id: int) -> int:
        session = SessionLocal()
        try:
            return expire_expired_reservations(db=session, redis_client=redis_client, lock_timeout=10)
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_task, i) for i in range(5)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # 3. Assert total expired reservations across workers equals exactly 10
    total_expired = sum(results)
    assert total_expired == 10, f"Expected exactly 10 expired reservations, got {total_expired} across results {results}"

    # 4. Verify DB state after workers complete
    verify_db = SessionLocal()
    try:
        # Check warehouse inventory reserved_qty decreased from 100 -> 0
        wh_after = verify_db.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id,
                WarehouseInventoryModel.warehouse_id == warehouse_id,
            )
        ).scalar_one()
        assert wh_after.reserved_qty == 0, f"Expected reserved_qty=0, got {wh_after.reserved_qty}"

        # Check expired reservations status
        expired_rows = verify_db.execute(
            select(StockReservationModel).where(
                StockReservationModel.product_id == product_id,
                StockReservationModel.expires_at <= now,
            )
        ).scalars().all()
        assert len(expired_rows) == 10
        for r in expired_rows:
            assert r.status == "EXPIRED"
            assert r.reserved_qty == 0
            assert r.released_qty == 10

        # Check future reservations remain RESERVED
        future_rows = verify_db.execute(
            select(StockReservationModel).where(
                StockReservationModel.product_id == product_id,
                StockReservationModel.expires_at > now,
            )
        ).scalars().all()
        assert len(future_rows) == 5
        for r in future_rows:
            assert r.status == "RESERVED"
            assert r.reserved_qty == 5
            assert r.released_qty == 0

    finally:
        verify_db.close()
