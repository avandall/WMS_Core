"""
Integration tests for Transactional Outbox Pattern.
TASK-007: Verifies atomic outbox recording during DB transactions, OutboxDispatcher processing,
and resilient retry mechanism upon Redis connection failure.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Setup sys.path to resolve microservices and shared libraries
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

# Import models to ensure WarehouseModel relationships initialize cleanly in SQLAlchemy
try:
    from app.modules.positions.infrastructure.models.position import PositionModel  # noqa: F401
    from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel  # noqa: F401
except ImportError:
    pass

from shared_utils.outbox.dispatcher import OutboxDispatcher
from shared_utils.outbox.models import OutboxEventModel, record_outbox_event
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.application.services.inventory_service import InventoryService
from app.shared.core.database import Base


@pytest.fixture(scope="module")
def outbox_engine():
    db_file = Path(__file__).resolve().parent / "test_outbox.db"
    if db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass

    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    if db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass


@pytest.fixture
def outbox_session(outbox_engine):
    Session = sessionmaker(bind=outbox_engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.rollback()
    session.close()


class MockFailingEventPublisher:
    """Mock publisher that simulates Redis failure on demand."""

    def __init__(self, should_fail: bool = True):
        self.should_fail = should_fail
        self.published_events = []

    def publish(self, *, event_type: str, payload: dict) -> None:
        if self.should_fail:
            raise ConnectionError("Redis cluster connection refused")
        self.published_events.append((event_type, payload))


def test_outbox_event_created_in_same_db_transaction(outbox_session):
    """Verify outbox event is created inside the same SQL transaction as inventory change."""
    repo = InventoryRepo(outbox_session)
    mock_publisher = MagicMock()
    service = InventoryService(repo, event_publisher=mock_publisher)

    # Adjust stock for product 101
    success = service.adjust_inventory(
        product_id=101,
        quantity_delta=50,
        warehouse_id=1,
        event_id="evt_outbox_test_001",
        reason="initial_stocking",
    )
    assert success is True

    # Check outbox_events table in DB
    stmt = select(OutboxEventModel).where(OutboxEventModel.event_id == "evt_outbox_test_001")
    record = outbox_session.execute(stmt).scalar_one_or_none()

    assert record is not None
    assert record.event_type == "InventoryAdjusted"
    assert record.status == "PENDING"
    payload = record.get_payload_dict()
    assert payload["product_id"] == 101
    assert payload["quantity_delta"] == 50


def test_outbox_dispatcher_publishes_pending_events(outbox_session):
    """Verify OutboxDispatcher scans PENDING events, publishes to Redis Stream, and marks PUBLISHED."""
    # Manually record an outbox event
    outbox_record = record_outbox_event(
        outbox_session,
        event_type="StockReserved",
        payload={
            "product_id": 202,
            "warehouse_id": 1,
            "quantity": 10,
            "reservation_id": 55,
        },
        event_id="evt_outbox_test_002",
    )
    outbox_session.commit()

    mock_publisher = MagicMock()
    dispatcher = OutboxDispatcher(publisher=mock_publisher)

    # Run dispatch
    published_count = dispatcher.dispatch_pending(session=outbox_session)
    assert published_count >= 1

    # Verify outbox record status updated to PUBLISHED
    stmt = select(OutboxEventModel).where(OutboxEventModel.event_id == "evt_outbox_test_002")
    record = outbox_session.execute(stmt).scalar_one_or_none()

    assert record is not None
    assert record.status == "PUBLISHED"
    assert record.published_at is not None
    mock_publisher.publish.assert_called()


def test_redis_disconnection_and_automatic_retry(outbox_session):
    """Simulate Redis disconnection during inventory update:

    - DB transaction succeeds and saves PENDING outbox record.
    - When Redis recovers, OutboxDispatcher retries and successfully publishes.
    """
    repo = InventoryRepo(outbox_session)
    failing_publisher = MockFailingEventPublisher(should_fail=True)
    service = InventoryService(repo, event_publisher=failing_publisher)

    # 1. Update stock while Redis publisher is down/failing
    with pytest.raises(ConnectionError, match="Redis cluster connection refused"):
        service.adjust_inventory(
            product_id=303,
            quantity_delta=100,
            warehouse_id=2,
            event_id="evt_redis_down_001",
            reason="bulk_receipt",
        )

    # Verify DB stock WAS updated and committed with PENDING outbox record
    stock_qty = repo.get_quantity(303)
    assert stock_qty == 100

    stmt = select(OutboxEventModel).where(OutboxEventModel.event_id == "evt_redis_down_001")
    record = outbox_session.execute(stmt).scalar_one_or_none()
    assert record is not None
    assert record.status == "PENDING"

    # 2. Simulate Redis connection restored
    recovering_publisher = MockFailingEventPublisher(should_fail=False)
    dispatcher = OutboxDispatcher(publisher=recovering_publisher)

    count = dispatcher.dispatch_pending(session=outbox_session)
    assert count >= 1

    # 3. Verify event now PUBLISHED and delivered to Redis stream
    outbox_session.refresh(record)
    assert record.status == "PUBLISHED"
    assert len(recovering_publisher.published_events) >= 1
    published_types = [t for t, p in recovering_publisher.published_events]
    assert "InventoryAdjusted" in published_types
