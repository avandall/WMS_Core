"""
Comprehensive Unit Tests for InventoryRepo
Covers all InventoryRepo methods, validation, edge cases, and database operations
"""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from sqlalchemy.orm import Session
from typing import List

from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.shared.domain.business_exceptions import InvalidQuantityError, InsufficientStockError
# Use mock models to avoid SQLAlchemy dependency issues
try:
    from app.infrastructure.persistence.models import InventoryModel
    REAL_MODELS_AVAILABLE = True
except ImportError:
    from tests.mocks.models import MockInventoryModel as InventoryModel
    REAL_MODELS_AVAILABLE = False



class TestInventoryRepo:
    """Test Inventory Repository Implementation"""

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
        session.execute = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session

    @pytest.fixture
    def inventory_repo(self, mock_session):
        """InventoryRepo instance with mocked session"""
        return InventoryRepo(session=mock_session)

    @pytest.fixture
    def sample_inventory_item(self):
        """Sample inventory item for testing"""
        return InventoryItem(product_id=1, quantity=50)

    @pytest.fixture
    def sample_inventory_model(self):
        """Sample InventoryModel for testing"""
        return InventoryModel(product_id=1, quantity=50)

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_inventory_repo_initialization(self, mock_session):
        """Test InventoryRepo initialization"""
        repo = InventoryRepo(session=mock_session)
        
        assert repo.session == mock_session
        assert repo._auto_commit is False

    # ============================================================================
    # SAVE TESTS
    # ============================================================================

    def test_save_new_inventory_item(self, inventory_repo, mock_session, sample_inventory_item):
        """Test save method with new inventory item"""
        # Mock session.get to return None (item doesn't exist)
        mock_session.get.return_value = None
        
        inventory_repo.save(sample_inventory_item)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify session.add was called (new item)
        mock_session.add.assert_called_once()
        
        # Verify commit was not called (auto_commit=False)
        mock_session.commit.assert_not_called()

    def test_save_existing_inventory_item(self, inventory_repo, mock_session, sample_inventory_item, sample_inventory_model):
        """Test save method with existing inventory item"""
        # Mock session.get to return existing item
        mock_session.get.return_value = sample_inventory_model
        
        inventory_repo.save(sample_inventory_item)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify session.add was not called (existing item)
        mock_session.add.assert_not_called()
        
        # Verify existing model was updated
        assert sample_inventory_model.quantity == 50

    def test_save_inventory_item_zero_quantity(self, inventory_repo, mock_session):
        """Test save method with zero quantity"""
        item = InventoryItem(product_id=1, quantity=0)
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        inventory_repo.save(item)
        
        # Verify session.add was called
        mock_session.add.assert_called_once()
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.quantity == 0

    def test_save_inventory_item_large_quantity(self, inventory_repo, mock_session):
        """Test save method with large quantity"""
        item = InventoryItem(product_id=1, quantity=1000000)
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        inventory_repo.save(item)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.quantity == 1000000

    # ============================================================================
    # ADD QUANTITY TESTS
    # ============================================================================

    def test_add_quantity_new_item(self, inventory_repo, mock_session):
        """Test add_quantity method with new item"""
        # Mock session.get to return None (item doesn't exist)
        mock_session.get.return_value = None
        
        inventory_repo.add_quantity(product_id=1, quantity=10)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify session.add was called (new item)
        mock_session.add.assert_called_once()
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.product_id == 1
        assert added_model.quantity == 10

    def test_add_quantity_existing_item(self, inventory_repo, mock_session, sample_inventory_model):
        """Test add_quantity method with existing item"""
        # Mock session.get to return existing item
        mock_session.get.return_value = sample_inventory_model
        
        inventory_repo.add_quantity(product_id=1, quantity=10)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify session.add was not called (existing item)
        mock_session.add.assert_not_called()
        
        # Verify existing model was updated
        assert sample_inventory_model.quantity == 60  # 50 + 10

    def test_add_quantity_zero(self, inventory_repo, mock_session, sample_inventory_model):
        """Test add_quantity method with zero quantity"""
        # Mock session.get to return existing item
        mock_session.get.return_value = sample_inventory_model
        
        inventory_repo.add_quantity(product_id=1, quantity=0)
        
        # Verify existing model quantity unchanged
        assert sample_inventory_model.quantity == 50

    def test_add_quantity_negative_existing_item(self, inventory_repo, mock_session, sample_inventory_model):
        """Test add_quantity method with negative quantity on existing item"""
        # Mock session.get to return existing item
        mock_session.get.return_value = sample_inventory_model
        
        with pytest.raises(InvalidQuantityError, match="Cannot add negative quantity"):
            inventory_repo.add_quantity(product_id=1, quantity=-5)

    def test_add_quantity_negative_new_item(self, inventory_repo, mock_session):
        """Test add_quantity method with negative quantity on new item"""
        # Mock session.get to return None (item doesn't exist)
        mock_session.get.return_value = None
        
        with pytest.raises(InvalidQuantityError, match="Cannot start with negative inventory for 1"):
            inventory_repo.add_quantity(product_id=1, quantity=-5)

    def test_add_quantity_large_amount(self, inventory_repo, mock_session, sample_inventory_model):
        """Test add_quantity method with large amount"""
        # Mock session.get to return existing item
        mock_session.get.return_value = sample_inventory_model
        
        inventory_repo.add_quantity(product_id=1, quantity=1000000)
        
        # Verify existing model was updated
        assert sample_inventory_model.quantity == 1000050  # 50 + 1000000

    # ============================================================================
    # GET QUANTITY TESTS
    # ============================================================================

    def test_get_quantity_found(self, inventory_repo, mock_session, sample_inventory_model):
        """Test get_quantity method when item is found"""
        # Mock session.get to return inventory model
        mock_session.get.return_value = sample_inventory_model
        
        result = inventory_repo.get_quantity(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify result
        assert result == 50

    def test_get_quantity_not_found(self, inventory_repo, mock_session):
        """Test get_quantity method when item is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        result = inventory_repo.get_quantity(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify result
        assert result == 0

    def test_get_quantity_zero_quantity(self, inventory_repo, mock_session):
        """Test get_quantity method when item has zero quantity"""
        # Create model with zero quantity
        inventory_model = InventoryModel(product_id=1, quantity=0)
        
        # Mock session.get to return inventory model
        mock_session.get.return_value = inventory_model
        
        result = inventory_repo.get_quantity(1)
        
        # Verify result
        assert result == 0

    # ============================================================================
    # GET ALL TESTS
    # ============================================================================

    def test_get_all_success(self, inventory_repo, mock_session):
        """Test get_all method successful retrieval"""
        # Create sample models
        inventory_model1 = InventoryModel(product_id=1, quantity=10)
        inventory_model2 = InventoryModel(product_id=2, quantity=20)
        
        # Mock session.execute to return models
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [inventory_model1, inventory_model2]
        mock_session.execute.return_value = mock_result
        
        result = inventory_repo.get_all()
        
        # Verify session.execute was called
        mock_session.execute.assert_called_once()
        
        # Verify result
        assert len(result) == 2
        assert result[0].product_id == 1
        assert result[0].quantity == 10
        assert result[1].product_id == 2
        assert result[1].quantity == 20

    def test_get_all_empty(self, inventory_repo, mock_session):
        """Test get_all method with no inventory items"""
        # Mock session.execute to return empty list
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = inventory_repo.get_all()
        
        # Verify result
        assert result == []

    def test_get_all_with_zero_quantities(self, inventory_repo, mock_session):
        """Test get_all method with items having zero quantities"""
        # Create models with zero quantities
        inventory_model1 = InventoryModel(product_id=1, quantity=0)
        inventory_model2 = InventoryModel(product_id=2, quantity=0)
        
        # Mock session.execute to return models
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [inventory_model1, inventory_model2]
        mock_session.execute.return_value = mock_result
        
        result = inventory_repo.get_all()
        
        # Verify result
        assert len(result) == 2
        assert result[0].quantity == 0
        assert result[1].quantity == 0

    # ============================================================================
    # DELETE TESTS
    # ============================================================================

    def test_delete_item_found_zero_quantity(self, inventory_repo, mock_session):
        """Test delete method when item is found with zero quantity"""
        # Create model with zero quantity
        inventory_model = InventoryModel(product_id=1, quantity=0)
        
        # Mock session.get to return inventory model
        mock_session.get.return_value = inventory_model
        
        inventory_repo.delete(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify session.delete was called
        mock_session.delete.assert_called_once_with(inventory_model)

    def test_delete_item_not_found(self, inventory_repo, mock_session):
        """Test delete method when item is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        inventory_repo.delete(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify session.delete was not called
        mock_session.delete.assert_not_called()

    def test_delete_item_non_zero_quantity(self, inventory_repo, mock_session, sample_inventory_model):
        """Test delete method when item has non-zero quantity"""
        # Mock session.get to return inventory model
        mock_session.get.return_value = sample_inventory_model
        
        with pytest.raises(InvalidQuantityError, match="Cannot delete item with non-zero quantity"):
            inventory_repo.delete(1)

    # ============================================================================
    # REMOVE QUANTITY TESTS
    # ============================================================================

    def test_remove_quantity_success(self, inventory_repo, mock_session, sample_inventory_model):
        """Test remove_quantity method successful removal"""
        # Mock session.get to return inventory model
        mock_session.get.return_value = sample_inventory_model
        
        inventory_repo.remove_quantity(product_id=1, quantity=10)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(InventoryModel, 1)
        
        # Verify existing model was updated
        assert sample_inventory_model.quantity == 40  # 50 - 10

    def test_remove_quantity_exact_amount(self, inventory_repo, mock_session, sample_inventory_model):
        """Test remove_quantity method removing exact available amount"""
        # Mock session.get to return inventory model
        mock_session.get.return_value = sample_inventory_model
        
        inventory_repo.remove_quantity(product_id=1, quantity=50)
        
        # Verify existing model was updated
        assert sample_inventory_model.quantity == 0  # 50 - 50

    def test_remove_quantity_item_not_found(self, inventory_repo, mock_session):
        """Test remove_quantity method when item is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        with pytest.raises(KeyError, match="Product 1 not found in inventory"):
            inventory_repo.remove_quantity(product_id=1, quantity=10)

    def test_remove_quantity_negative_amount(self, inventory_repo, mock_session, sample_inventory_model):
        """Test remove_quantity method with negative amount"""
        # Mock session.get to return inventory model
        mock_session.get.return_value = sample_inventory_model
        
        with pytest.raises(InvalidQuantityError, match="Cannot remove negative quantity"):
            inventory_repo.remove_quantity(product_id=1, quantity=-5)

    def test_remove_quantity_insufficient_stock(self, inventory_repo, mock_session, sample_inventory_model):
        """Test remove_quantity method with insufficient stock"""
        # Mock session.get to return inventory model
        mock_session.get.return_value = sample_inventory_model
        
        with pytest.raises(InsufficientStockError, match="Insufficient stock. Available: 50, Requested: 60"):
            inventory_repo.remove_quantity(product_id=1, quantity=60)

    def test_remove_quantity_zero_amount(self, inventory_repo, mock_session, sample_inventory_model):
        """Test remove_quantity method with zero amount"""
        # Mock session.get to return inventory model
        mock_session.get.return_value = sample_inventory_model
        
        inventory_repo.remove_quantity(product_id=1, quantity=0)
        
        # Verify existing model quantity unchanged
        assert sample_inventory_model.quantity == 50

    def test_remove_quantity_large_amount(self, inventory_repo, mock_session):
        """Test remove_quantity method with large amount"""
        # Create model with large quantity
        inventory_model = InventoryModel(product_id=1, quantity=1000000)
        
        # Mock session.get to return inventory model
        mock_session.get.return_value = inventory_model
        
        inventory_repo.remove_quantity(product_id=1, quantity=500000)
        
        # Verify existing model was updated
        assert inventory_model.quantity == 500000  # 1000000 - 500000

    # ============================================================================
    # TO DOMAIN TESTS
    # ============================================================================

    def test_to_domain_conversion(self):
        """Test _to_domain static method"""
        # Create inventory model
        inventory_model = InventoryModel(product_id=1, quantity=50)
        
        result = InventoryRepo._to_domain(inventory_model)
        
        # Verify conversion
        assert result.product_id == 1
        assert result.quantity == 50
        assert isinstance(result, InventoryItem)

    def test_to_domain_conversion_zero_quantity(self):
        """Test _to_domain static method with zero quantity"""
        # Create inventory model with zero quantity
        inventory_model = InventoryModel(product_id=1, quantity=0)
        
        result = InventoryRepo._to_domain(inventory_model)
        
        # Verify conversion
        assert result.quantity == 0

    def test_to_domain_conversion_large_quantity(self):
        """Test _to_domain static method with large quantity"""
        # Create inventory model with large quantity
        inventory_model = InventoryModel(product_id=1, quantity=1000000)
        
        result = InventoryRepo._to_domain(inventory_model)
        
        # Verify conversion
        assert result.quantity == 1000000

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    def test_save_then_get_integration(self, inventory_repo, mock_session, sample_inventory_item):
        """Test integration between save and get methods"""
        # Mock session.get to return None first, then inventory model
        inventory_model = InventoryModel(product_id=1, quantity=50)
        mock_session.get.side_effect = [None, inventory_model]
        
        # Save inventory item
        inventory_repo.save(sample_inventory_item)
        
        # Get quantity
        result = inventory_repo.get_quantity(1)
        
        # Verify result
        assert result == 50

    def test_add_then_remove_integration(self, inventory_repo, mock_session, sample_inventory_model):
        """Test integration between add and remove methods"""
        # Mock session.get to return existing model
        mock_session.get.return_value = sample_inventory_model
        
        # Add quantity
        inventory_repo.add_quantity(product_id=1, quantity=25)
        assert sample_inventory_model.quantity == 75  # 50 + 25
        
        # Remove quantity
        inventory_repo.remove_quantity(product_id=1, quantity=30)
        
        # Verify final quantity
        assert sample_inventory_model.quantity == 45  # 75 - 30

    def test_save_then_get_all_integration(self, inventory_repo, mock_session, sample_inventory_item):
        """Test integration between save and get_all methods"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        # Mock session.execute for get_all
        inventory_model = InventoryModel(product_id=1, quantity=50)
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [inventory_model]
        mock_session.execute.return_value = mock_result
        
        # Save inventory item
        inventory_repo.save(sample_inventory_item)
        
        # Get all items
        result = inventory_repo.get_all()
        
        # Verify result
        assert len(result) == 1
        assert result[0].product_id == 1
        assert result[0].quantity == 50

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_operations_with_large_product_id(self, inventory_repo, mock_session):
        """Test operations with large product ID"""
        large_product_id = 2147483647  # Max int
        
        # Create inventory item with large ID
        item = InventoryItem(product_id=large_product_id, quantity=50)
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        # Save item
        inventory_repo.save(item)
        
        # Check the added model
        added_model = mock_session.add.call_args[0][0]
        assert added_model.product_id == large_product_id

    def test_operations_with_boundary_quantities(self, inventory_repo, mock_session, sample_inventory_model):
        """Test operations with boundary quantities"""
        # Mock session.get to return existing model
        mock_session.get.return_value = sample_inventory_model
        
        # Add zero quantity
        inventory_repo.add_quantity(product_id=1, quantity=0)
        assert sample_inventory_model.quantity == 50
        
        # Remove zero quantity
        inventory_repo.remove_quantity(product_id=1, quantity=0)
        assert sample_inventory_model.quantity == 50
        
        # Remove exact amount
        inventory_repo.remove_quantity(product_id=1, quantity=50)
        assert sample_inventory_model.quantity == 0

    def test_operations_with_negative_boundary_conditions(self, inventory_repo, mock_session):
        """Test operations with negative boundary conditions"""
        # Test add_quantity with -1
        mock_session.get.return_value = None
        with pytest.raises(InvalidQuantityError, match="Cannot start with negative inventory for 1"):
            inventory_repo.add_quantity(product_id=1, quantity=-1)
        
        # Test remove_quantity with -1
        inventory_model = InventoryModel(product_id=1, quantity=10)
        mock_session.get.return_value = inventory_model
        with pytest.raises(InvalidQuantityError, match="Cannot remove negative quantity"):
            inventory_repo.remove_quantity(product_id=1, quantity=-1)

    def test_multiple_operations_sequence(self, inventory_repo, mock_session, sample_inventory_model):
        """Test sequence of multiple operations"""
        # Mock session.get to return existing model
        mock_session.get.return_value = sample_inventory_model
        
        # Sequence of operations
        inventory_repo.add_quantity(product_id=1, quantity=10)  # 60
        inventory_repo.remove_quantity(product_id=1, quantity=5)   # 55
        inventory_repo.add_quantity(product_id=1, quantity=15)  # 70
        inventory_repo.remove_quantity(product_id=1, quantity=20)  # 50
        
        # Verify final quantity
        assert sample_inventory_model.quantity == 50

    def test_concurrent_operations_simulation(self, inventory_repo, mock_session):
        """Test simulation of concurrent operations"""
        # Create initial model
        inventory_model = InventoryModel(product_id=1, quantity=100)
        mock_session.get.return_value = inventory_model
        
        # Simulate concurrent adds
        inventory_repo.add_quantity(product_id=1, quantity=10)  # 110
        inventory_repo.add_quantity(product_id=1, quantity=20)  # 130
        
        # Simulate concurrent removes
        inventory_repo.remove_quantity(product_id=1, quantity=30)  # 100
        inventory_repo.remove_quantity(product_id=1, quantity=50)  # 50
        
        # Verify final state
        assert inventory_model.quantity == 50

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_save_database_error_handling(self, inventory_repo, mock_session, sample_inventory_item):
        """Test save method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            inventory_repo.save(sample_inventory_item)

    def test_get_quantity_database_error_handling(self, inventory_repo, mock_session):
        """Test get_quantity method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            inventory_repo.get_quantity(1)

    def test_get_all_database_error_handling(self, inventory_repo, mock_session):
        """Test get_all method handles database errors gracefully"""
        # Mock session.execute to raise exception
        mock_session.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            inventory_repo.get_all()

    def test_delete_database_error_handling(self, inventory_repo, mock_session):
        """Test delete method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            inventory_repo.delete(1)

    def test_remove_quantity_database_error_handling(self, inventory_repo, mock_session):
        """Test remove_quantity method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            inventory_repo.remove_quantity(product_id=1, quantity=10)

    def test_add_quantity_database_error_handling(self, inventory_repo, mock_session):
        """Test add_quantity method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            inventory_repo.add_quantity(product_id=1, quantity=10)
