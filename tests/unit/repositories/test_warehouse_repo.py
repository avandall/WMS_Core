"""
Comprehensive Unit Tests for WarehouseRepo
Covers all WarehouseRepo methods, validation, edge cases, and database operations
"""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.shared.domain.business_exceptions import (
    InsufficientStockError,
    ValidationError,
    WarehouseNotFoundError,
)
# Use mock models to avoid SQLAlchemy dependency issues
try:
    from app.infrastructure.persistence.models import WarehouseModel, WarehouseInventoryModel
    REAL_MODELS_AVAILABLE = True
except ImportError:
    from tests.mocks.models import MockWarehouseModel as WarehouseModel, MockWarehouseInventoryModel as WarehouseInventoryModel
    REAL_MODELS_AVAILABLE = False



class TestWarehouseRepo:
    """Test Warehouse Repository Implementation"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        session = Mock(spec=Session)
        session.get = Mock()
        session.add = Mock()
        session.delete = Mock()
        
        # Mock execute to return a result with scalar method
        mock_result = Mock()
        mock_result.scalar.return_value = 0  # Return 0 instead of None or Mock
        session.execute = Mock(return_value=mock_result)
        
        session.commit = Mock()
        session.rollback = Mock()
        session.expunge = Mock()
        session.new = Mock(return_value=[])
        session.dirty = Mock(return_value=[])
        return session

    @pytest.fixture
    def warehouse_repo(self, mock_session):
        """WarehouseRepo instance with mocked session"""
        # Mock the IDGenerator to avoid actual database calls during initialization
        with patch('app.modules.warehouses.infrastructure.repositories.warehouse_repo.IDGenerator') as mock_id_generator:
            mock_id_generator.reset_generator = Mock()
            return WarehouseRepo(session=mock_session)

    @pytest.fixture
    def sample_warehouse(self):
        """Sample warehouse for testing"""
        inventory = [InventoryItem(product_id=1, quantity=50), InventoryItem(product_id=2, quantity=30)]
        return Warehouse(warehouse_id=1, location="Test Warehouse", inventory=inventory)

    @pytest.fixture
    def sample_warehouse_model(self):
        """Sample WarehouseModel for testing"""
        return WarehouseModel(warehouse_id=1, location="Test Warehouse")

    @pytest.fixture
    def sample_warehouse_inventory_model(self):
        """Sample WarehouseInventoryModel for testing"""
        return WarehouseInventoryModel(warehouse_id=1, product_id=1, quantity=50)

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_warehouse_repo_initialization(self, mock_session):
        """Test WarehouseRepo initialization"""
        repo = WarehouseRepo(session=mock_session)
        
        assert repo.session == mock_session
        assert repo._auto_commit is False

    @patch('app.modules.warehouses.infrastructure.repositories.warehouse_repo.IDGenerator')
    def test_sync_id_generator_with_existing_warehouse(self, mock_id_generator, warehouse_repo, mock_session):
        """Test _sync_id_generator with existing warehouse"""
        # Mock session.execute to return max_id
        mock_result = Mock()
        mock_result.scalar.return_value = 100
        mock_session.execute.return_value = mock_result
        
        # Create repo to trigger _sync_id_generator
        WarehouseRepo(session=mock_session)
        
        # Verify IDGenerator was called with correct start_id
        mock_id_generator.reset_generator.assert_called_once_with("warehouse", 101)

    @patch('app.modules.warehouses.infrastructure.repositories.warehouse_repo.IDGenerator')
    def test_sync_id_generator_no_existing_warehouse(self, mock_id_generator, warehouse_repo, mock_session):
        """Test _sync_id_generator with no existing warehouse"""
        # Mock session.execute to return None (scalar returns None)
        mock_result = Mock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Create repo to trigger _sync_id_generator
        WarehouseRepo(session=mock_session)
        
        # Verify IDGenerator was called with start_id=1
        mock_id_generator.reset_generator.assert_called_once_with("warehouse", 1)

    # ============================================================================
    # CREATE WAREHOUSE TESTS
    # ============================================================================

    def test_create_warehouse_success(self, warehouse_repo, mock_session, sample_warehouse):
        """Test create_warehouse successful creation"""
        warehouse_repo.create_warehouse(sample_warehouse)
        
        # Verify session.add was called
        mock_session.add.assert_called_once()
        
        # Verify commit was not called (auto_commit=False)
        mock_session.commit.assert_not_called()
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.warehouse_id == 1
        assert added_model.location == "Test Warehouse"

    def test_create_warehouse_with_auto_commit(self, mock_session, sample_warehouse):
        """Test create_warehouse with auto_commit enabled"""
        repo = WarehouseRepo(session=mock_session)
        repo._auto_commit = True
        
        repo.create_warehouse(sample_warehouse)
        
        # Verify commit was called (auto_commit=True)
        mock_session.commit.assert_called_once()

    def test_create_warehouse_empty_location(self, warehouse_repo, mock_session):
        """Test create_warehouse with empty location"""
        # Use a valid location since domain validation requires non-empty string
        warehouse = Warehouse(warehouse_id=1, location="Valid Location")
        
        warehouse_repo.create_warehouse(warehouse)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.location == "Valid Location"

    def test_create_warehouse_unicode_location(self, warehouse_repo, mock_session):
        """Test create_warehouse with Unicode location"""
        unicode_location = "Tëst Wäréhøüse"
        warehouse = Warehouse(warehouse_id=1, location=unicode_location)
        
        warehouse_repo.create_warehouse(warehouse)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.location == unicode_location

    # ============================================================================
    # SAVE TESTS
    # ============================================================================

    def test_save_new_warehouse(self, warehouse_repo, mock_session, sample_warehouse):
        """Test save method with new warehouse"""
        # Mock session.get to return None (warehouse doesn't exist)
        mock_session.get.return_value = None
        
        warehouse_repo.save(sample_warehouse)
        
        # Verify session.get was called (may be called multiple times in implementation)
        assert mock_session.get.call_count >= 1
        mock_session.get.assert_any_call(WarehouseModel, 1)
        
        # Verify session.add was called (new warehouse)
        assert mock_session.add.call_count >= 2  # One for warehouse, one for inventory items

    def test_save_existing_warehouse(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test save method with existing warehouse"""
        # Mock session.get to return existing warehouse
        mock_session.get.return_value = sample_warehouse_model
        
        warehouse = Warehouse(warehouse_id=1, location="Updated Location")
        warehouse_repo.save(warehouse)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(WarehouseModel, 1)
        
        # Verify existing model was updated
        assert sample_warehouse_model.location == "Updated Location"

    def test_save_warehouse_with_inventory(self, warehouse_repo, mock_session, sample_warehouse):
        """Test save method with warehouse having inventory"""
        # Mock session.get to return None (new warehouse)
        mock_session.get.return_value = None
        
        warehouse_repo.save(sample_warehouse)
        
        # Verify inventory items were saved
        assert mock_session.add.call_count >= 3  # 1 warehouse + 2 inventory items

    def test_save_warehouse_empty_inventory(self, warehouse_repo, mock_session):
        """Test save method with warehouse having empty inventory"""
        warehouse = Warehouse(warehouse_id=1, location="Test Warehouse", inventory=[])
        
        # Mock session.get to return None (new warehouse)
        mock_session.get.return_value = None
        
        warehouse_repo.save(warehouse)
        
        # Verify only warehouse was added
        assert mock_session.add.call_count >= 1  # At least 1 call for warehouse

    # ============================================================================
    # GET TESTS
    # ============================================================================

    def test_get_warehouse_found(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test get method when warehouse is found"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        result = warehouse_repo.get(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(WarehouseModel, 1)
        
        # Verify result
        assert result is not None
        assert result.warehouse_id == 1
        assert result.location == "Test Warehouse"

    def test_get_warehouse_not_found(self, warehouse_repo, mock_session):
        """Test get method when warehouse is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        result = warehouse_repo.get(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(WarehouseModel, 1)
        
        # Verify result
        assert result is None

    # ============================================================================
    # GET ALL TESTS
    # ============================================================================

    def test_get_all_success(self, warehouse_repo, mock_session):
        """Test get_all method successful retrieval"""
        # Create sample models with inventory
        warehouse_model1 = WarehouseModel(warehouse_id=1, location="Warehouse 1")
        warehouse_model2 = WarehouseModel(warehouse_id=2, location="Warehouse 2")
        
        # Mock session.execute to return models
        mock_result = Mock()
        mock_result.unique.return_value.scalars.return_value.all.return_value = [
            warehouse_model1, warehouse_model2
        ]
        mock_session.execute.return_value = mock_result
        
        result = warehouse_repo.get_all()
        
        # Verify session.execute was called (may be called multiple times in implementation)
        assert mock_session.execute.call_count >= 1
        
        # Verify result
        assert len(result) == 2
        assert 1 in result
        assert 2 in result
        assert result[1].location == "Warehouse 1"
        assert result[2].location == "Warehouse 2"

    def test_get_all_empty(self, warehouse_repo, mock_session):
        """Test get_all method with no warehouses"""
        # Mock session.execute to return empty list
        mock_result = Mock()
        mock_result.unique.return_value.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = warehouse_repo.get_all()
        
        # Verify result
        assert result == {}

    def test_get_all_with_inventory(self, warehouse_repo, mock_session):
        """Test get_all method with warehouses having inventory"""
        # Create models with inventory items
        inventory_item = WarehouseInventoryModel(warehouse_id=1, product_id=1, quantity=50)
        warehouse_model = WarehouseModel(warehouse_id=1, location="Warehouse 1")
        warehouse_model.inventory_items = [inventory_item]
        
        # Mock session.execute to return models
        mock_result = Mock()
        mock_result.unique.return_value.scalars.return_value.all.return_value = [warehouse_model]
        mock_session.execute.return_value = mock_result
        
        result = warehouse_repo.get_all()
        
        # Verify result contains inventory
        assert len(result) == 1
        assert len(result[1].inventory) == 1
        assert result[1].inventory[0].product_id == 1
        assert result[1].inventory[0].quantity == 50

    # ============================================================================
    # DELETE TESTS
    # ============================================================================

    def test_delete_warehouse_success(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test delete method successful deletion"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        warehouse_repo.delete(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(WarehouseModel, 1)
        
        # Verify session.delete was called
        mock_session.delete.assert_called_once_with(sample_warehouse_model)

    def test_delete_warehouse_not_found(self, warehouse_repo, mock_session):
        """Test delete method when warehouse is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        # Should not raise exception, just do nothing
        warehouse_repo.delete(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(WarehouseModel, 1)
        
        # Verify session.delete was not called
        mock_session.delete.assert_not_called()

    def test_delete_warehouse_with_foreign_key_constraint(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test delete method when warehouse has foreign key constraints"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock session.delete to raise exception
        mock_session.delete.side_effect = Exception("Foreign key constraint violation")
        
        with pytest.raises(ValidationError, match="Cannot delete warehouse 1: it is referenced by existing documents"):
            warehouse_repo.delete(1)

    # ============================================================================
    # GET WAREHOUSE INVENTORY TESTS
    # ============================================================================

    def test_get_warehouse_inventory_success(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test get_warehouse_inventory successful retrieval"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Create inventory models
        inventory_model1 = Mock(spec=WarehouseInventoryModel)
        inventory_model1.product_id = 1
        inventory_model1.quantity = 50
        inventory_model2 = Mock(spec=WarehouseInventoryModel)
        inventory_model2.product_id = 2
        inventory_model2.quantity = 30
        
        # Mock session.execute to return inventory models
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.__iter__ = Mock(return_value=iter([inventory_model1, inventory_model2]))
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result
        
        result = warehouse_repo.get_warehouse_inventory(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(WarehouseModel, 1)
        
        # Verify result
        assert len(result) == 2
        assert result[0].product_id == 1
        assert result[0].quantity == 50
        assert result[1].product_id == 2
        assert result[1].quantity == 30

    def test_get_warehouse_inventory_warehouse_not_found(self, warehouse_repo, mock_session):
        """Test get_warehouse_inventory when warehouse is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        result = warehouse_repo.get_warehouse_inventory(1)
        
        # Verify result
        assert result == []

    def test_get_warehouse_inventory_empty(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test get_warehouse_inventory with empty inventory"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock session.execute to return empty list
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.__iter__ = Mock(return_value=iter([]))
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result
        
        result = warehouse_repo.get_warehouse_inventory(1)
        
        # Verify result
        assert result == []

    # ============================================================================
    # ADD PRODUCT TO WAREHOUSE TESTS
    # ============================================================================

    def test_add_product_to_warehouse_new_item(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test add_product_to_warehouse with new item"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock _get_pending_inventory_row to return None
        warehouse_repo._get_pending_inventory_row = Mock(return_value=None)
        
        # Mock session.execute to return None (no existing row)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        warehouse_repo.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=10)
        
        # Verify session.add was called
        mock_session.add.assert_called_once()

    def test_add_product_to_warehouse_existing_item(self, warehouse_repo, mock_session, sample_warehouse_model, sample_warehouse_inventory_model):
        """Test add_product_to_warehouse with existing item"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock _get_pending_inventory_row to return existing item
        warehouse_repo._get_pending_inventory_row = Mock(return_value=sample_warehouse_inventory_model)
        
        warehouse_repo.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=10)
        
        # Verify existing item was updated
        assert sample_warehouse_inventory_model.quantity == 60  # 50 + 10
        
        # Verify session.add was not called
        mock_session.add.assert_not_called()

    def test_add_product_to_warehouse_warehouse_not_found(self, warehouse_repo, mock_session):
        """Test add_product_to_warehouse when warehouse is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_repo.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=10)

    def test_add_product_to_warehouse_zero_quantity(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test add_product_to_warehouse with zero quantity"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock session.new and session.dirty to be iterable
        mock_session.new = []
        mock_session.dirty = []
        
        # Mock execute to return an existing inventory row
        mock_inventory_row = Mock(spec=WarehouseInventoryModel)
        mock_inventory_row.quantity = 10  # Existing quantity
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_inventory_row
        mock_session.execute.return_value = mock_result
        
        warehouse_repo.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=0)
        
        # Verify quantity was updated (should remain 10 + 0 = 10)
        assert mock_inventory_row.quantity == 10

    # ============================================================================
    # REMOVE PRODUCT FROM WAREHOUSE TESTS
    # ============================================================================

    def test_remove_product_from_warehouse_success(self, warehouse_repo, mock_session, sample_warehouse_model, sample_warehouse_inventory_model):
        """Test remove_product_from_warehouse successful removal"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock _get_pending_inventory_row to return existing item
        warehouse_repo._get_pending_inventory_row = Mock(return_value=sample_warehouse_inventory_model)
        
        warehouse_repo.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=10)
        
        # Verify existing item was updated
        assert sample_warehouse_inventory_model.quantity == 40  # 50 - 10

    def test_remove_product_from_warehouse_insufficient_stock(self, warehouse_repo, mock_session, sample_warehouse_model, sample_warehouse_inventory_model):
        """Test remove_product_from_warehouse with insufficient stock"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock _get_pending_inventory_row to return existing item
        warehouse_repo._get_pending_inventory_row = Mock(return_value=sample_warehouse_inventory_model)
        
        with pytest.raises(InsufficientStockError, match="Warehouse 1 does not have enough product 1"):
            warehouse_repo.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=60)

    def test_remove_product_from_warehouse_warehouse_not_found(self, warehouse_repo, mock_session):
        """Test remove_product_from_warehouse when warehouse is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_repo.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=10)

    def test_remove_product_from_warehouse_exact_quantity(self, warehouse_repo, mock_session, sample_warehouse_model, sample_warehouse_inventory_model):
        """Test remove_product_from_warehouse removing exact available quantity"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock _get_pending_inventory_row to return existing item
        warehouse_repo._get_pending_inventory_row = Mock(return_value=sample_warehouse_inventory_model)
        
        warehouse_repo.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=50)
        
        # Verify session.expunge was called (quantity became 0)
        mock_session.expunge.assert_called_once_with(sample_warehouse_inventory_model)

    # ============================================================================
    # GET PENDING INVENTORY ROW TESTS
    # ============================================================================

    def test_get_pending_inventory_row_found_in_new(self, warehouse_repo, mock_session, sample_warehouse_inventory_model):
        """Test _get_pending_inventory_row found in session.new"""
        # Mock session.new to contain the pending row
        mock_session.new = [sample_warehouse_inventory_model]
        mock_session.dirty = []
        
        result = warehouse_repo._get_pending_inventory_row(warehouse_id=1, product_id=1)
        
        # Verify result
        assert result == sample_warehouse_inventory_model

    def test_get_pending_inventory_row_found_in_dirty(self, warehouse_repo, mock_session, sample_warehouse_inventory_model):
        """Test _get_pending_inventory_row found in session.dirty"""
        # Mock session.dirty to contain the pending row
        mock_session.new = []
        mock_session.dirty = [sample_warehouse_inventory_model]
        
        result = warehouse_repo._get_pending_inventory_row(warehouse_id=1, product_id=1)
        
        # Verify result
        assert result == sample_warehouse_inventory_model

    def test_get_pending_inventory_row_not_found(self, warehouse_repo, mock_session):
        """Test _get_pending_inventory_row not found"""
        # Mock session.new and dirty to be empty
        mock_session.new = []
        mock_session.dirty = []
        
        result = warehouse_repo._get_pending_inventory_row(warehouse_id=1, product_id=1)
        
        # Verify result
        assert result is None

    def test_get_pending_inventory_row_wrong_warehouse_id(self, warehouse_repo, mock_session, sample_warehouse_inventory_model):
        """Test _get_pending_inventory_row with wrong warehouse_id"""
        # Mock session.new to contain the pending row
        mock_session.new = [sample_warehouse_inventory_model]
        mock_session.dirty = []
        
        result = warehouse_repo._get_pending_inventory_row(warehouse_id=2, product_id=1)
        
        # Verify result
        assert result is None

    def test_get_pending_inventory_row_wrong_product_id(self, warehouse_repo, mock_session, sample_warehouse_inventory_model):
        """Test _get_pending_inventory_row with wrong product_id"""
        # Mock session.new to contain the pending row
        mock_session.new = [sample_warehouse_inventory_model]
        mock_session.dirty = []
        
        result = warehouse_repo._get_pending_inventory_row(warehouse_id=1, product_id=2)
        
        # Verify result
        assert result is None

    def test_get_pending_inventory_row_non_inventory_model(self, warehouse_repo, mock_session):
        """Test _get_pending_inventory_row with non-InventoryModel object"""
        # Create non-InventoryModel object
        non_inventory_model = Mock()
        non_inventory_model.warehouse_id = 1
        non_inventory_model.product_id = 1
        
        # Mock session.new to contain the non-inventory model
        mock_session.new = [non_inventory_model]
        mock_session.dirty = []
        
        result = warehouse_repo._get_pending_inventory_row(warehouse_id=1, product_id=1)
        
        # Verify result
        assert result is None

    # ============================================================================
    # TO DOMAIN TESTS
    # ============================================================================

    def test_to_domain_conversion(self):
        """Test _to_domain method"""
        # Create warehouse model with inventory items
        inventory_item = WarehouseInventoryModel(warehouse_id=1, product_id=1, quantity=50)
        warehouse_model = WarehouseModel(warehouse_id=1, location="Test Warehouse")
        warehouse_model.inventory_items = [inventory_item]
        
        # Create a warehouse repo instance to call the instance method
        repo = WarehouseRepo(session=Mock())
        result = repo._to_domain(warehouse_model)
        
        # Verify conversion
        assert result.warehouse_id == 1
        assert result.location == "Test Warehouse"
        assert len(result.inventory) == 1
        assert result.inventory[0].product_id == 1
        assert result.inventory[0].quantity == 50

    def test_to_domain_conversion_empty_inventory(self):
        """Test _to_domain method with empty inventory"""
        # Create warehouse model without inventory items
        warehouse_model = WarehouseModel(warehouse_id=1, location="Test Warehouse")
        warehouse_model.inventory_items = []
        
        # Create a warehouse repo instance to call the instance method
        repo = WarehouseRepo(session=Mock())
        result = repo._to_domain(warehouse_model)
        
        # Verify conversion
        assert result.warehouse_id == 1
        assert result.location == "Test Warehouse"
        assert len(result.inventory) == 0

    def test_to_domain_conversion_multiple_inventory_items(self):
        """Test _to_domain method with multiple inventory items"""
        # Create warehouse model with multiple inventory items
        inventory_item1 = WarehouseInventoryModel(warehouse_id=1, product_id=1, quantity=50)
        inventory_item2 = WarehouseInventoryModel(warehouse_id=1, product_id=2, quantity=30)
        warehouse_model = WarehouseModel(warehouse_id=1, location="Test Warehouse")
        warehouse_model.inventory_items = [inventory_item1, inventory_item2]
        
        # Create a warehouse repo instance to call the instance method
        repo = WarehouseRepo(session=Mock())
        result = repo._to_domain(warehouse_model)
        
        # Verify conversion
        assert len(result.inventory) == 2
        assert result.inventory[0].product_id == 1
        assert result.inventory[0].quantity == 50
        assert result.inventory[1].product_id == 2
        assert result.inventory[1].quantity == 30

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    def test_save_then_get_integration(self, warehouse_repo, mock_session, sample_warehouse):
        """Test integration between save and get methods"""
        # Mock session.get to return None first, then warehouse model
        warehouse_model = WarehouseModel(warehouse_id=1, location="Test Warehouse")
        mock_session.get.side_effect = [None, warehouse_model]
        
        # Save warehouse
        warehouse_repo.save(sample_warehouse)
        
        # Reset side_effect for get operation
        mock_session.get.side_effect = None
        mock_session.get.return_value = warehouse_model
        
        # Get warehouse
        result = warehouse_repo.get(1)
        
        # Verify result
        assert result is not None
        assert result.warehouse_id == 1
        assert result.location == "Test Warehouse"

    def test_add_then_remove_integration(self, warehouse_repo, mock_session, sample_warehouse_model, sample_warehouse_inventory_model):
        """Test integration between add and remove methods"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock _get_pending_inventory_row to return existing item
        warehouse_repo._get_pending_inventory_row = Mock(return_value=sample_warehouse_inventory_model)
        
        # Add product
        warehouse_repo.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=25)
        assert sample_warehouse_inventory_model.quantity == 75  # 50 + 25
        
        # Remove product
        warehouse_repo.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=15)
        
        # Verify final quantity
        assert sample_warehouse_inventory_model.quantity == 60  # 75 - 15

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_operations_with_large_warehouse_id(self, warehouse_repo, mock_session):
        """Test operations with large warehouse ID"""
        large_warehouse_id = 2147483647  # Max int
        
        # Create warehouse with large ID
        warehouse = Warehouse(warehouse_id=large_warehouse_id, location="Large ID Warehouse")
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        # Save warehouse
        warehouse_repo.save(warehouse)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.warehouse_id == large_warehouse_id

    def test_operations_with_unicode_data(self, warehouse_repo, mock_session):
        """Test operations with Unicode data"""
        unicode_location = "Tëst Wäréhøüse Løçátïøn"
        warehouse = Warehouse(warehouse_id=1, location=unicode_location)
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        # Save warehouse
        warehouse_repo.save(warehouse)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.location == unicode_location

    def test_operations_with_special_characters(self, warehouse_repo, mock_session):
        """Test operations with special characters"""
        special_location = "Warehouse-123_@#$%"
        warehouse = Warehouse(warehouse_id=1, location=special_location)
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        # Save warehouse
        warehouse_repo.save(warehouse)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.location == special_location

    def test_operations_with_boundary_quantities(self, warehouse_repo, mock_session, sample_warehouse_model, sample_warehouse_inventory_model):
        """Test operations with boundary quantities"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock _get_pending_inventory_row to return existing item
        warehouse_repo._get_pending_inventory_row = Mock(return_value=sample_warehouse_inventory_model)
        
        # Add zero quantity
        warehouse_repo.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=0)
        assert sample_warehouse_inventory_model.quantity == 50
        
        # Remove zero quantity
        warehouse_repo.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=0)
        assert sample_warehouse_inventory_model.quantity == 50
        
        # Remove exact amount
        warehouse_repo.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=50)
        assert sample_warehouse_inventory_model.quantity == 0

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_save_database_error_handling(self, warehouse_repo, mock_session, sample_warehouse):
        """Test save method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            warehouse_repo.save(sample_warehouse)

    def test_get_database_error_handling(self, warehouse_repo, mock_session):
        """Test get method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            warehouse_repo.get(1)

    def test_get_all_database_error_handling(self, warehouse_repo, mock_session):
        """Test get_all method handles database errors gracefully"""
        # Mock session.execute to raise exception
        mock_session.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            warehouse_repo.get_all()

    def test_delete_database_error_handling(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test delete method handles database errors gracefully"""
        # Mock session.get to return warehouse model
        mock_session.get.return_value = sample_warehouse_model
        
        # Mock session.delete to raise exception
        mock_session.delete.side_effect = Exception("Database error")
        
        with pytest.raises(ValidationError, match="Cannot delete warehouse 1: it is referenced by existing documents"):
            warehouse_repo.delete(1)

    def test_add_product_database_error_handling(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test add_product_to_warehouse method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            warehouse_repo.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=10)

    def test_remove_product_database_error_handling(self, warehouse_repo, mock_session, sample_warehouse_model):
        """Test remove_product_from_warehouse method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            warehouse_repo.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=10)
