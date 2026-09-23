"""
Unit tests for WarehouseOperationsServiceServicer (TASK-033).
Tests BulkTransfer, GetInventoryHealth, and OptimizeDistribution gRPC methods with real DB interactions.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

import app.shared.core.database as warehouse_db_module
from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.positions.infrastructure.models.position import PositionModel
from app.modules.products.infrastructure.models.product import ProductModel
from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel
import warehouse_service.grpc_servicer as servicer_module
from warehouse_service.grpc_servicer import WarehouseOperationsServiceServicer
from warehouse_service.gen.wms.warehouse.v1 import warehouse_pb2


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database and build tables for all models."""
    engine = create_engine("sqlite:///:memory:")
    # Ensure metadata contains all models by registering them on Base
    warehouse_db_module.Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def servicer(db_engine):
    """Fixture providing WarehouseOperationsServiceServicer with mocked database session."""
    TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def mock_get_db_session():
        db = TestSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    with patch.object(servicer_module, "get_db_session", mock_get_db_session):
        yield WarehouseOperationsServiceServicer()


class TestBulkTransfer:
    def test_bulk_transfer_partial_success(self, db_engine, servicer):
        """
        Verify BulkTransfer with 3 items:
        - Item 1: Valid transfer (10 units of product 101 from WH 1 to WH 2) -> Success
        - Item 2: Valid transfer (15 units of product 102 from WH 1 to WH 2) -> Success
        - Item 3: Insufficient stock transfer (100 units of product 101 from WH 1 to WH 2) -> Failed
        Expect: successful=2, failed=1, total_transfers=3.
        """
        TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
        session = TestSessionLocal()

        # Create 2 warehouses
        wh1 = WarehouseModel(warehouse_id=1, location="Warehouse North", warehouse_type="ambient")
        wh2 = WarehouseModel(warehouse_id=2, location="Warehouse South", warehouse_type="ambient")
        session.add_all([wh1, wh2])

        # Create inventory in WH 1 for product 101 (50 units) and product 102 (30 units)
        inv1 = WarehouseInventoryModel(
            warehouse_id=1, owner_id="DEFAULT_OWNER", product_id=101, quantity=50, physical_qty=50
        )
        inv2 = WarehouseInventoryModel(
            warehouse_id=1, owner_id="DEFAULT_OWNER", product_id=102, quantity=30, physical_qty=30
        )
        session.add_all([inv1, inv2])
        session.commit()
        session.close()

        request = warehouse_pb2.BulkTransferRequest(
            transfers=[
                warehouse_pb2.BulkTransferItem(
                    from_warehouse_id=1, to_warehouse_id=2, product_id=101, quantity=10
                ),
                warehouse_pb2.BulkTransferItem(
                    from_warehouse_id=1, to_warehouse_id=2, product_id=102, quantity=15
                ),
                warehouse_pb2.BulkTransferItem(
                    from_warehouse_id=1, to_warehouse_id=2, product_id=101, quantity=100
                ),
            ]
        )
        context = MagicMock()
        response = servicer.BulkTransfer(request, context)

        assert response.total_transfers == 3
        assert response.successful == 2
        assert response.failed == 1

        # Check resulting inventory in database
        session = TestSessionLocal()
        inv1_after = session.query(WarehouseInventoryModel).filter_by(warehouse_id=1, product_id=101).one()
        assert inv1_after.physical_qty == 40  # 50 - 10

        inv2_after = session.query(WarehouseInventoryModel).filter_by(warehouse_id=1, product_id=102).one()
        assert inv2_after.physical_qty == 15  # 30 - 15

        inv1_wh2 = session.query(WarehouseInventoryModel).filter_by(warehouse_id=2, product_id=101).one()
        assert inv1_wh2.physical_qty == 10

        inv2_wh2 = session.query(WarehouseInventoryModel).filter_by(warehouse_id=2, product_id=102).one()
        assert inv2_wh2.physical_qty == 15
        session.close()

    def test_bulk_transfer_invalid_inputs(self, db_engine, servicer):
        """Verify invalid transfers (same wh, non-existent wh, zero quantity)."""
        TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
        session = TestSessionLocal()
        session.add(WarehouseModel(warehouse_id=1, location="WH Alpha"))
        session.commit()
        session.close()

        request = warehouse_pb2.BulkTransferRequest(
            transfers=[
                warehouse_pb2.BulkTransferItem(
                    from_warehouse_id=1, to_warehouse_id=1, product_id=101, quantity=10
                ),  # Same WH
                warehouse_pb2.BulkTransferItem(
                    from_warehouse_id=1, to_warehouse_id=2, product_id=101, quantity=0
                ),  # Zero qty
                warehouse_pb2.BulkTransferItem(
                    from_warehouse_id=99, to_warehouse_id=1, product_id=101, quantity=5
                ),  # Missing WH
            ]
        )
        context = MagicMock()
        response = servicer.BulkTransfer(request, context)

        assert response.total_transfers == 3
        assert response.successful == 0
        assert response.failed == 3


class TestGetInventoryHealth:
    def test_get_inventory_health_real_metrics(self, db_engine, servicer):
        """Verify calculation of health score based on positions, fresh inventory, and stock availability."""
        TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
        session = TestSessionLocal()

        wh = WarehouseModel(warehouse_id=1, location="Central Hub")
        prod1 = ProductModel(product_id=10, name="Widget A", price=20.0)
        prod2 = ProductModel(product_id=20, name="Widget B", price=50.0)
        session.add_all([wh, prod1, prod2])

        # Positions: 2 active, 0 inactive -> position_score = 100%
        pos1 = PositionModel(warehouse_id=1, code="A1", is_active=1)
        pos2 = PositionModel(warehouse_id=1, code="A2", is_active=1)
        session.add_all([pos1, pos2])

        # Inventory locations: 1 fresh, 1 expired -> fresh_score = 50%
        loc1 = InventoryLocationModel(
            warehouse_id=1, owner_id="DEF", position_id=1, product_id=10, quantity=5,
            expiry_date=datetime(2099, 1, 1, tzinfo=timezone.utc)
        )
        loc2 = InventoryLocationModel(
            warehouse_id=1, owner_id="DEF", position_id=2, product_id=20, quantity=5,
            expiry_date=datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
        session.add_all([loc1, loc2])

        # Warehouse Inventory: 1 in stock, 1 out of stock -> stock_availability_score = 50%
        inv1 = WarehouseInventoryModel(warehouse_id=1, owner_id="DEF", product_id=10, quantity=10, physical_qty=10)
        inv2 = WarehouseInventoryModel(warehouse_id=1, owner_id="DEF", product_id=20, quantity=0, physical_qty=0)
        session.add_all([inv1, inv2])

        session.commit()
        session.close()

        request = warehouse_pb2.GetInventoryHealthRequest()
        context = MagicMock()
        response = servicer.GetInventoryHealth(request, context)

        # Expected score = 100 * 0.3 + 50 * 0.4 + 50 * 0.3 = 30 + 20 + 15 = 65.0
        assert response.system_health_score == 65.0
        assert len(response.warehouses) == 1
        wh_report = response.warehouses[0]
        assert wh_report.warehouse_id == 1
        assert wh_report.health_score == 65.0
        assert wh_report.total_value == 200.0  # 10 * 20.0 + 0 * 50.0

    def test_get_inventory_health_empty_system(self, db_engine, servicer):
        """Verify GetInventoryHealth handles empty warehouse database gracefully."""
        request = warehouse_pb2.GetInventoryHealthRequest()
        context = MagicMock()
        response = servicer.GetInventoryHealth(request, context)

        assert response.system_health_score == 100.0
        assert len(response.warehouses) == 0


class TestOptimizeDistribution:
    def test_optimize_distribution_recommendations(self, db_engine, servicer):
        """Verify rebalance recommendations generated when inventory is imbalanced."""
        TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
        session = TestSessionLocal()

        prod = ProductModel(product_id=50, name="Laptops", price=1000.0)
        wh1 = WarehouseModel(warehouse_id=1, location="Hanoi")
        wh2 = WarehouseModel(warehouse_id=2, location="HCM")
        session.add_all([prod, wh1, wh2])

        inv1 = WarehouseInventoryModel(warehouse_id=1, owner_id="DEF", product_id=50, quantity=100, physical_qty=100)
        inv2 = WarehouseInventoryModel(warehouse_id=2, owner_id="DEF", product_id=50, quantity=0, physical_qty=0)
        session.add_all([inv1, inv2])

        session.commit()
        session.close()

        request = warehouse_pb2.OptimizeDistributionRequest(product_id=50)
        context = MagicMock()
        response = servicer.OptimizeDistribution(request, context)

        assert response.product_id == 50
        assert response.product_name == "Laptops"
        assert len(response.distribution) == 2
        assert len(response.recommendations) > 0
        assert "Transfer 50 units" in response.recommendations[0]

    def test_optimize_distribution_product_not_found(self, db_engine, servicer):
        """Verify error message when target product does not exist."""
        request = warehouse_pb2.OptimizeDistributionRequest(product_id=999)
        context = MagicMock()
        response = servicer.OptimizeDistribution(request, context)

        assert response.error == "Product 999 not found"
