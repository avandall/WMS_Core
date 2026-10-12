"""
Unit tests for 3PL Multi-Client / Multi-Tenant Inventory & Reporting (TASK-013)
Acceptance Criteria:
- Mọi truy vấn tồn kho đều phân lập theo owner_id.
- Khách hàng A không bao giờ nhìn thấy hoặc bị trừ nhầm hàng của Khách hàng B.
"""

import sys
from pathlib import Path

inv_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "inventory-service" / "src")
if inv_src not in sys.path:
    sys.path.insert(0, inv_src)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.shared.core.database import Base  # noqa: E402
from app.modules.inventory.domain.entities.inventory_location import (  # noqa: E402
    InventoryLocation,
)
from app.shared.domain.business_exceptions import (  # noqa: E402
    InsufficientStockError,
)
from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel  # noqa: E402
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel  # noqa: E402
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo  # noqa: E402


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


class TestInventoryLocationDomainEntityOwner:
    """Test owner_id support in InventoryLocation domain entity."""

    def test_location_domain_entity_with_owner(self):
        loc_a = InventoryLocation(
            id=1,
            warehouse_id=10,
            owner_id="CLIENT_A",
            position_id=100,
            product_id=500,
            lpn="PALLET-A1",
            quantity=100,
            allocated_qty=20,
        )
        assert loc_a.owner_id == "CLIENT_A"
        assert loc_a.available_qty == 80

        loc_b = InventoryLocation(
            id=2,
            warehouse_id=10,
            owner_id="CLIENT_B",
            position_id=100,
            product_id=500,
            lpn="PALLET-B1",
            quantity=50,
            allocated_qty=0,
        )
        assert loc_b.owner_id == "CLIENT_B"
        assert loc_b.available_qty == 50


class TestMultiTenantInventoryIsolation:
    """Test 3PL multi-tenant stock isolation in repository."""

    def test_adjust_and_query_location_by_owner(self, db_session):
        repo = InventoryRepo(db_session)

        # Deposit 100 units for CLIENT_A at warehouse=1, bin=5, product=10
        repo.adjust_location_quantity(
            warehouse_id=1,
            position_id=5,
            product_id=10,
            quantity_delta=100,
            owner_id="CLIENT_A",
            lpn="LPN-A",
        )

        # Deposit 40 units for CLIENT_B at same warehouse=1, bin=5, product=10
        repo.adjust_location_quantity(
            warehouse_id=1,
            position_id=5,
            product_id=10,
            quantity_delta=40,
            owner_id="CLIENT_B",
            lpn="LPN-B",
        )

        # Query Client A's stock
        locs_a = repo.get_inventory_locations(warehouse_id=1, product_id=10, owner_id="CLIENT_A")
        assert len(locs_a) == 1
        assert locs_a[0]["owner_id"] == "CLIENT_A"
        assert locs_a[0]["quantity"] == 100

        # Query Client B's stock
        locs_b = repo.get_inventory_locations(warehouse_id=1, product_id=10, owner_id="CLIENT_B")
        assert len(locs_b) == 1
        assert locs_b[0]["owner_id"] == "CLIENT_B"
        assert locs_b[0]["quantity"] == 40

    def test_client_cannot_deduct_other_client_stock(self, db_session):
        repo = InventoryRepo(db_session)

        # CLIENT_A has 50 units
        repo.adjust_location_quantity(
            warehouse_id=1,
            position_id=5,
            product_id=10,
            quantity_delta=50,
            owner_id="CLIENT_A",
        )

        # CLIENT_B has 200 units
        repo.adjust_location_quantity(
            warehouse_id=1,
            position_id=5,
            product_id=10,
            quantity_delta=200,
            owner_id="CLIENT_B",
        )

        # Attempt to deduct 80 units from CLIENT_A (who only has 50 available)
        with pytest.raises(InsufficientStockError):
            repo.adjust_location_quantity(
                warehouse_id=1,
                position_id=5,
                product_id=10,
                quantity_delta=-80,
                owner_id="CLIENT_A",
            )

        # Verify CLIENT_A's stock is still 50 and CLIENT_B's stock is still 200
        locs_a = repo.get_inventory_locations(warehouse_id=1, owner_id="CLIENT_A")
        assert locs_a[0]["quantity"] == 50

        locs_b = repo.get_inventory_locations(warehouse_id=1, owner_id="CLIENT_B")
        assert locs_b[0]["quantity"] == 200

    def test_warehouse_summary_is_isolated_by_owner(self, db_session):
        repo = InventoryRepo(db_session)

        repo.adjust_location_quantity(
            warehouse_id=2,
            position_id=1,
            product_id=99,
            quantity_delta=30,
            owner_id="CLIENT_X",
        )
        repo.adjust_location_quantity(
            warehouse_id=2,
            position_id=1,
            product_id=99,
            quantity_delta=70,
            owner_id="CLIENT_Y",
        )

        wh_inv_x = db_session.query(WarehouseInventoryModel).filter_by(
            warehouse_id=2, product_id=99, owner_id="CLIENT_X"
        ).one()
        assert wh_inv_x.physical_qty == 30

        wh_inv_y = db_session.query(WarehouseInventoryModel).filter_by(
            warehouse_id=2, product_id=99, owner_id="CLIENT_Y"
        ).one()
        assert wh_inv_y.physical_qty == 70


class TestMultiTenantDocumentsAndReporting:
    """Test 3PL multi-tenant reporting & document filters."""

    def test_documents_and_reporting_isolation(self):
        rep_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "reporting-service" / "src")
        if rep_src not in sys.path:
            sys.path.insert(0, rep_src)

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.shared.core.database import Base
        from app.modules.reporting.infrastructure.models.projections import InventorySummary, DocumentSummary
        from app.modules.reporting.infrastructure.repositories.read_model_repo import ReportingReadModelRepo

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        session = session_factory()

        # Seed InventorySummary projections for CLIENT_A and CLIENT_B
        session.add(InventorySummary(product_id=101, owner_id="CLIENT_A", total_quantity=150))
        session.add(InventorySummary(product_id=101, owner_id="CLIENT_B", total_quantity=300))

        # Seed DocumentSummary projections for CLIENT_A and CLIENT_B
        session.add(DocumentSummary(document_id=1, doc_type="IMPORT", status="COMPLETED", owner_id="CLIENT_A", total_quantity=150))
        session.add(DocumentSummary(document_id=2, doc_type="EXPORT", status="COMPLETED", owner_id="CLIENT_B", total_quantity=300))
        session.commit()

        read_repo = ReportingReadModelRepo(session)

        # Inventory report for CLIENT_A
        inv_a = read_repo.inventory_report(owner_id="CLIENT_A")
        assert len(inv_a["items"]) == 1
        assert inv_a["items"][0]["owner_id"] == "CLIENT_A"
        assert inv_a["items"][0]["quantity"] == 150

        # Inventory report for CLIENT_B
        inv_b = read_repo.inventory_report(owner_id="CLIENT_B")
        assert len(inv_b["items"]) == 1
        assert inv_b["items"][0]["owner_id"] == "CLIENT_B"
        assert inv_b["items"][0]["quantity"] == 300

        # Documents report for CLIENT_A
        docs_a = read_repo.documents_report(owner_id="CLIENT_A")
        assert len(docs_a["documents"]) == 1
        assert docs_a["documents"][0]["owner_id"] == "CLIENT_A"

        session.close()
