"""
Comprehensive Unit Tests for PositionRepo
Covers all PositionRepo methods, validation, edge cases, and database operations
"""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from app.modules.positions.infrastructure.repositories.position_repo import PositionRepo
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    InsufficientStockError,
    ValidationError,
    WarehouseNotFoundError,
)
# Use mock models to avoid SQLAlchemy dependency issues
try:
    # Import all models using the centralized import function to avoid SQLAlchemy mapper errors
    from app.shared.core.database import import_all_models
    import_all_models()
    from app.modules.positions.infrastructure.models.position import PositionModel
    from app.modules.inventory.infrastructure.models.position_inventory import PositionInventoryModel
    from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel
    REAL_MODELS_AVAILABLE = True
except ImportError:
    from tests.mocks.models import MockPositionModel as PositionModel
    from tests.mocks.models import MockPositionInventoryModel as PositionInventoryModel
    from tests.mocks.models import MockWarehouseModel as WarehouseModel
    REAL_MODELS_AVAILABLE = False


class TestPositionRepo:
    """Test Position Repository Implementation"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        session = Mock(spec=Session)
        session.get = Mock()
        session.add = Mock()
        session.execute = Mock()
        session.commit = Mock()
        session.flush = Mock()
        session.new = []
        session.dirty = []
        return session

    @pytest.fixture
    def position_repo(self, mock_session):
        """PositionRepo with mocked session"""
        return PositionRepo(session=mock_session)

    @pytest.fixture
    def sample_warehouse_model(self):
        """Sample WarehouseModel for testing"""
        return WarehouseModel(
            warehouse_id=1,
            location="Test Warehouse"
        )

    @pytest.fixture
    def sample_position_model(self):
        """Sample PositionModel for testing"""
        return PositionModel(
            id=1,
            warehouse_id=1,
            code="STORAGE",
            type="STORAGE",
            description="Main storage",
            is_active=1
        )

    # ============================================================================
    # ENSURE DEFAULT POSITIONS TESTS
    # ============================================================================

    def test_ensure_default_positions_creates_missing(self, position_repo, mock_session, sample_warehouse_model):
        """Test ensure_default_positions creates missing positions"""
        mock_session.get.return_value = sample_warehouse_model
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        
        position_repo.ensure_default_positions(1)
        
        assert mock_session.add.call_count == 4  # 4 default positions
        mock_session.flush.assert_called()

    def test_ensure_default_positions_skips_existing(self, position_repo, mock_session, sample_warehouse_model, sample_position_model):
        """Test ensure_default_positions skips existing positions"""
        mock_session.get.return_value = sample_warehouse_model
        # Mock all 4 default positions as existing
        positions = []
        for code, pos_type, desc in [("RECEIVING", "RECEIVING", None), ("STORAGE", "STORAGE", None), ("SHIPPING", "SHIPPING", None), ("UNASSIGNED", "SYSTEM", None)]:
            pos = PositionModel(warehouse_id=1, code=code, type=pos_type, description=desc, is_active=1)
            positions.append(pos)
        mock_session.execute.return_value.scalars.return_value.all.return_value = positions
        # Also add to session.new to simulate pending objects
        mock_session.new = positions
        mock_session.dirty = positions
        
        position_repo.ensure_default_positions(1)
        
        # Should not add any new positions since all exist
        assert mock_session.add.call_count == 0

    def test_ensure_default_positions_warehouse_not_found(self, position_repo, mock_session):
        """Test ensure_default_positions when warehouse not found"""
        mock_session.get.return_value = None
        
        with pytest.raises(WarehouseNotFoundError):
            position_repo.ensure_default_positions(999)

    # ============================================================================
    # CREATE POSITION TESTS
    # ============================================================================

    def test_create_position_success(self, position_repo, mock_session, sample_warehouse_model):
        """Test creating a new position"""
        mock_session.get.return_value = sample_warehouse_model
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = position_repo.create_position(
            warehouse_id=1,
            code="CUSTOM",
            type="STORAGE",
            description="Custom position"
        )
        
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.code == "CUSTOM"
        assert result.warehouse_id == 1

    def test_create_position_already_exists(self, position_repo, mock_session, sample_warehouse_model, sample_position_model):
        """Test creating position that already exists"""
        mock_session.get.return_value = sample_warehouse_model
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_position_model
        
        with pytest.raises(EntityAlreadyExistsError):
            position_repo.create_position(warehouse_id=1, code="STORAGE")

    def test_create_position_warehouse_not_found(self, position_repo, mock_session):
        """Test creating position when warehouse not found"""
        mock_session.get.return_value = None
        
        with pytest.raises(WarehouseNotFoundError):
            position_repo.create_position(warehouse_id=999, code="STORAGE")

    # ============================================================================
    # LIST POSITIONS TESTS
    # ============================================================================

    def test_list_positions_active_only(self, position_repo, mock_session, sample_position_model):
        """Test listing active positions only"""
        mock_session.execute.return_value.scalars.return_value.all.return_value = [sample_position_model]
        
        result = position_repo.list_positions(1, include_inactive=False)
        
        assert len(result) == 1
        assert result[0].code == "STORAGE"

    def test_list_positions_include_inactive(self, position_repo, mock_session, sample_position_model):
        """Test listing positions including inactive"""
        mock_session.execute.return_value.scalars.return_value.all.return_value = [sample_position_model]
        
        result = position_repo.list_positions(1, include_inactive=True)
        
        assert len(result) == 1

    def test_list_positions_empty(self, position_repo, mock_session):
        """Test listing positions when none exist"""
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        
        result = position_repo.list_positions(1)
        
        assert len(result) == 0

    # ============================================================================
    # GET POSITION TESTS
    # ============================================================================

    def test_get_position_found(self, position_repo, mock_session, sample_position_model):
        """Test getting a position by code when found"""
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_position_model
        
        result = position_repo.get_position(1, "STORAGE")
        
        assert result.code == "STORAGE"
        assert result.warehouse_id == 1

    def test_get_position_not_found(self, position_repo, mock_session):
        """Test getting a position when not found"""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        with pytest.raises(EntityNotFoundError):
            position_repo.get_position(1, "NONEXISTENT")

    # ============================================================================
    # LIST POSITION INVENTORY TESTS
    # ============================================================================

    def test_list_position_inventory(self, position_repo, mock_session, sample_position_model):
        """Test listing inventory for a position"""
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_position_model
        mock_inv_item = Mock()
        mock_inv_item.product_id = 100
        mock_inv_item.quantity = 50
        mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_inv_item]
        
        result = position_repo.list_position_inventory(1, "STORAGE")
        
        assert len(result) == 1
        assert result[0].product_id == 100
        assert result[0].quantity == 50

    def test_list_position_inventory_empty(self, position_repo, mock_session, sample_position_model):
        """Test listing inventory when position has no inventory"""
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_position_model
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        
        result = position_repo.list_position_inventory(1, "STORAGE")
        
        assert len(result) == 0

    # ============================================================================
    # GET TOTAL QUANTITY TESTS
    # ============================================================================

    def test_get_total_quantity_for_product(self, position_repo, mock_session):
        """Test getting total quantity for a product across all positions"""
        mock_session.execute.return_value.scalar_one.return_value = 100
        
        result = position_repo.get_total_quantity_for_product(1, 100)
        
        assert result == 100

    def test_get_total_quantity_for_product_zero(self, position_repo, mock_session):
        """Test getting total quantity when product has no stock"""
        mock_session.execute.return_value.scalar_one.return_value = 0
        
        result = position_repo.get_total_quantity_for_product(1, 999)
        
        assert result == 0

    # ============================================================================
    # ADJUST POSITION STOCK TESTS
    # ============================================================================

    def test_adjust_position_stock_add(self, position_repo, mock_session):
        """Test adding stock to a position"""
        # Mock the internal methods
        position_repo._add_to_position = Mock()
        
        position_repo.adjust_position_stock(position_id=1, product_id=100, delta=50)
        
        position_repo._add_to_position.assert_called_once_with(position_id=1, product_id=100, quantity=50)

    def test_adjust_position_stock_remove(self, position_repo, mock_session):
        """Test removing stock from a position"""
        position_repo._remove_from_position = Mock()
        
        position_repo.adjust_position_stock(position_id=1, product_id=100, delta=-50)
        
        position_repo._remove_from_position.assert_called_once_with(position_id=1, product_id=100, quantity=50)

    def test_adjust_position_stock_zero_delta(self, position_repo, mock_session):
        """Test adjusting stock with zero delta (should do nothing)"""
        position_repo._add_to_position = Mock()
        position_repo._remove_from_position = Mock()
        
        position_repo.adjust_position_stock(position_id=1, product_id=100, delta=0)
        
        position_repo._add_to_position.assert_not_called()
        position_repo._remove_from_position.assert_not_called()

    # ============================================================================
    # ALLOCATE AND REMOVE TESTS
    # ============================================================================

    def test_allocate_and_remove_success(self, position_repo, mock_session, sample_position_model):
        """Test allocating and removing stock across positions"""
        mock_session.execute.return_value.scalars.return_value.all.return_value = [sample_position_model]
        position_repo._get_position_product_quantity = Mock(return_value=100)
        position_repo._remove_from_position = Mock()
        
        result = position_repo.allocate_and_remove(
            warehouse_id=1,
            product_id=100,
            quantity=50
        )
        
        assert len(result) == 1
        position_repo._remove_from_position.assert_called_once()

    def test_allocate_and_remove_insufficient_stock(self, position_repo, mock_session, sample_position_model):
        """Test allocate and remove with insufficient stock"""
        mock_session.execute.return_value.scalars.return_value.all.return_value = [sample_position_model]
        position_repo._get_position_product_quantity = Mock(return_value=10)
        # Mock the row returned by _remove_from_position with insufficient quantity
        mock_row = Mock()
        mock_row.quantity = 5  # Less than the 50 we're trying to remove
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_row
        
        with pytest.raises(InsufficientStockError):
            position_repo.allocate_and_remove(
                warehouse_id=1,
                product_id=100,
                quantity=50
            )

    def test_allocate_and_remove_invalid_quantity(self, position_repo, mock_session):
        """Test allocate and remove with invalid quantity"""
        with pytest.raises(ValidationError):
            position_repo.allocate_and_remove(
                warehouse_id=1,
                product_id=100,
                quantity=0
            )

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_create_position_code_normalization(self, position_repo, mock_session, sample_warehouse_model):
        """Test position code is normalized to uppercase"""
        mock_session.get.return_value = sample_warehouse_model
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = position_repo.create_position(warehouse_id=1, code="storage")
        
        assert result.code == "STORAGE"

    def test_create_position_type_normalization(self, position_repo, mock_session, sample_warehouse_model):
        """Test position type is normalized to uppercase"""
        mock_session.get.return_value = sample_warehouse_model
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = position_repo.create_position(warehouse_id=1, code="STORAGE", type="storage")
        
        assert result.type == "STORAGE"

    def test_get_position_code_normalization(self, position_repo, mock_session, sample_position_model):
        """Test get_position normalizes code"""
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_position_model
        
        result = position_repo.get_position(1, "storage")
        
        assert result.code == "STORAGE"

    # ============================================================================
    # TO DOMAIN TESTS
    # ============================================================================

    def test_to_domain_conversion(self, position_repo, sample_position_model):
        """Test _to_domain conversion"""
        result = position_repo._to_domain(sample_position_model)
        
        assert result.id == 1
        assert result.warehouse_id == 1
        assert result.code == "STORAGE"
        assert result.type == "STORAGE"
        assert result.description == "Main storage"
        assert result.is_active is True
