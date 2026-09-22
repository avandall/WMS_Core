"""
Unit tests for Warehouse and Position physical attributes (TASK-029).
Tests domain validation, full_address property, and model persistence.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.shared.core.database import Base
from app.shared.domain.business_exceptions import ValidationError
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.modules.warehouses.domain.value_objects import WarehouseType, TemperatureZone
from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.modules.positions.domain.entities.position import Position
from app.modules.positions.infrastructure.models.position import PositionModel
from app.modules.positions.infrastructure.repositories.position_repo import PositionRepo


class TestWarehousePhysicalAttributes:
    """Tests for Warehouse physical and operational attributes."""

    def test_warehouse_type_validation(self):
        """Verify warehouse_type validation, allowed values and defaults."""
        # Valid warehouse types
        for w_type in ("ambient", "cold", "frozen", "hazmat", "AMBIENT", "Cold"):
            wh = Warehouse(warehouse_id=1, location="Loc-A", warehouse_type=w_type)
            assert wh.warehouse_type == w_type.strip().lower()

        # Invalid warehouse type raises ValidationError
        with pytest.raises(ValidationError, match="warehouse_type must be one of"):
            Warehouse(warehouse_id=1, location="Loc-A", warehouse_type="underwater")

        with pytest.raises(ValidationError, match="warehouse_type must be one of"):
            WarehouseType("invalid_type")

        # Negative capacity_sqm raises ValidationError
        with pytest.raises(ValidationError, match="capacity_sqm must be non-negative"):
            Warehouse(warehouse_id=1, location="Loc-A", capacity_sqm=-10.5)

        # Valid capacity_sqm
        wh_cap = Warehouse(warehouse_id=1, location="Loc-A", capacity_sqm=1500.0)
        assert wh_cap.capacity_sqm == 1500.0

        # Verify defaults
        wh_default = Warehouse(warehouse_id=1, location="Loc-B")
        assert wh_default.warehouse_type == "ambient"
        assert wh_default.capacity_sqm is None
        assert wh_default.is_active is True
        assert wh_default.manager_id is None
        assert wh_default.timezone == "UTC"

    def test_warehouse_operational_fields(self):
        """Verify operational fields: is_active, manager_id, timezone."""
        wh = Warehouse(
            warehouse_id=1,
            location="Loc-Ops",
            warehouse_type="cold",
            capacity_sqm=5000.25,
            is_active=False,
            manager_id="MGR-999",
            timezone="Asia/Ho_Chi_Minh",
        )
        assert wh.warehouse_id == 1
        assert wh.location == "Loc-Ops"
        assert wh.warehouse_type == "cold"
        assert wh.capacity_sqm == 5000.25
        assert wh.is_active is False
        assert wh.manager_id == "MGR-999"
        assert wh.timezone == "Asia/Ho_Chi_Minh"


class TestPositionPhysicalAttributes:
    """Tests for Position 4D coordinates and physical attributes."""

    def test_position_full_address(self):
        """Verify 4D coordinates and full_address calculation."""
        # When coordinates are provided
        pos = Position(
            id=1,
            warehouse_id=1,
            code="POS-01",
            type="STORAGE",
            aisle="A",
            bay="01",
            level="02",
            bin="B",
        )
        assert pos.full_address == "A-01-02-B"

        # Partial coordinates
        pos_partial = Position(
            id=2,
            warehouse_id=1,
            code="POS-02",
            type="STORAGE",
            aisle="ZONE-A",
            bin="BIN-9",
        )
        assert pos_partial.full_address == "ZONE-A-BIN-9"

        # Empty coordinates fallback to code
        pos_empty = Position(
            id=3,
            warehouse_id=1,
            code="CODE-FALLBACK",
            type="STORAGE",
        )
        assert pos_empty.full_address == "CODE-FALLBACK"

    def test_position_temperature_zone_validation(self):
        """Verify temperature_zone validation."""
        for tz in ("ambient", "chilled", "frozen", "AMBIENT", "Chilled"):
            pos = Position(
                id=1,
                warehouse_id=1,
                code="P-01",
                type="STORAGE",
                temperature_zone=tz,
            )
            assert pos.temperature_zone == tz.strip().lower()

        with pytest.raises(ValidationError, match="temperature_zone must be one of"):
            Position(
                id=1,
                warehouse_id=1,
                code="P-01",
                type="STORAGE",
                temperature_zone="boiling",
            )

        with pytest.raises(ValidationError, match="temperature_zone must be one of"):
            TemperatureZone("volcano")

    def test_position_weight_and_hazmat(self):
        """Verify max_weight_kg validation and hazmat_class."""
        # Negative max_weight_kg raises ValidationError
        with pytest.raises(ValidationError, match="max_weight_kg must be non-negative"):
            Position(
                id=1,
                warehouse_id=1,
                code="P-01",
                type="STORAGE",
                max_weight_kg=-5.0,
            )

        # Valid max_weight_kg and hazmat_class
        pos = Position(
            id=1,
            warehouse_id=1,
            code="P-HAZ",
            type="STORAGE",
            max_weight_kg=1250.5,
            pick_sequence=15,
            hazmat_class="CLASS_3_FLAMMABLE",
        )
        assert pos.max_weight_kg == 1250.5
        assert pos.pick_sequence == 15
        assert pos.hazmat_class == "CLASS_3_FLAMMABLE"
        assert pos.temperature_zone == "ambient"


class TestWarehouseAndPositionRepositories:
    """Integration test with in-memory SQLite database for ORM repositories."""

    @pytest.fixture
    def db_session(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        session = session_factory()
        yield session
        session.close()

    def test_warehouse_repo_persistence(self, db_session):
        repo = WarehouseRepo(db_session)
        wh = Warehouse(
            warehouse_id=1,
            location="Hanoi Central",
            warehouse_type="cold",
            capacity_sqm=3500.0,
            is_active=True,
            manager_id="MGR-001",
            timezone="Asia/Bangkok",
        )
        repo.create_warehouse(wh)

        saved = repo.get(1)
        assert saved is not None
        assert saved.location == "Hanoi Central"
        assert saved.warehouse_type == "cold"
        assert saved.capacity_sqm == 3500.0
        assert saved.is_active is True
        assert saved.manager_id == "MGR-001"
        assert saved.timezone == "Asia/Bangkok"

    def test_position_repo_persistence_and_order(self, db_session):
        wh_repo = WarehouseRepo(db_session)
        wh = Warehouse(warehouse_id=10, location="WH-10")
        wh_repo.create_warehouse(wh)

        pos_repo = PositionRepo(db_session)
        # Create positions with out-of-order pick_sequence
        pos2 = pos_repo.create_position(
            warehouse_id=10,
            code="LOC-B",
            type="STORAGE",
            aisle="B",
            bay="02",
            level="01",
            bin="01",
            max_weight_kg=500.0,
            temperature_zone="chilled",
            pick_sequence=20,
            hazmat_class="CLASS_8",
        )
        pos1 = pos_repo.create_position(
            warehouse_id=10,
            code="LOC-A",
            type="STORAGE",
            aisle="A",
            bay="01",
            level="01",
            bin="01",
            max_weight_kg=1000.0,
            temperature_zone="ambient",
            pick_sequence=10,
        )

        assert pos1.full_address == "A-01-01-01"
        assert pos2.full_address == "B-02-01-01"
        assert pos2.temperature_zone == "chilled"
        assert pos2.hazmat_class == "CLASS_8"

        # Check list_positions ordering by pick_sequence
        listed = pos_repo.list_positions(10)
        assert len(listed) >= 2
        # Default positions might be created if ensure_default_positions triggered,
        # but loc-a (10) and loc-b (20) should have pick_sequence in ascending order
        indexed_items = [p for p in listed if p.code in ("LOC-A", "LOC-B")]
        assert [p.code for p in indexed_items] == ["LOC-A", "LOC-B"]
        assert indexed_items[0].pick_sequence == 10
        assert indexed_items[1].pick_sequence == 20
