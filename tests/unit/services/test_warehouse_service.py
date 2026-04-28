"""
Comprehensive Unit Tests for WarehouseService
Covers all WarehouseService methods, validation, edge cases, and business logic
"""

import pytest
from unittest.mock import Mock, MagicMock, call
from typing import Dict, List, Any

from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.modules.products.domain.entities.product import Product
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    InsufficientStockError,
    InvalidQuantityError,
    ProductNotFoundError,
    ValidationError,
    WarehouseNotFoundError,
)
from app.shared.domain.inventory_repo import IInventoryRepo
from app.shared.domain.product_repo import IProductRepo
from app.shared.domain.warehouse_repo import IWarehouseRepo


class TestWarehouseService:
    """Test WarehouseService Application Service"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_warehouse_repo(self):
        """Mock warehouse repository"""
        return Mock(spec=IWarehouseRepo)

    @pytest.fixture
    def mock_product_repo(self):
        """Mock product repository"""
        return Mock(spec=IProductRepo)

    @pytest.fixture
    def mock_inventory_repo(self):
        """Mock inventory repository"""
        return Mock(spec=IInventoryRepo)

    @pytest.fixture
    def mock_id_generator(self):
        """Mock ID generator"""
        return Mock(return_value=1)

    @pytest.fixture
    def warehouse_service(self, mock_warehouse_repo, mock_product_repo, mock_inventory_repo, mock_id_generator):
        """WarehouseService instance with mocked dependencies"""
        return WarehouseService(
            warehouse_repo=mock_warehouse_repo,
            product_repo=mock_product_repo,
            inventory_repo=mock_inventory_repo,
            id_generator=mock_id_generator
        )

    @pytest.fixture
    def sample_product(self):
        """Sample product for testing"""
        return Product(product_id=1, name="Test Product", price=99.99)

    @pytest.fixture
    def sample_warehouse(self):
        """Sample warehouse for testing"""
        return Warehouse(warehouse_id=1, location="Test Warehouse")

    @pytest.fixture
    def sample_inventory_item(self):
        """Sample inventory item for testing"""
        return InventoryItem(product_id=1, quantity=50)

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_warehouse_service_initialization(self, mock_warehouse_repo, mock_product_repo, mock_inventory_repo):
        """Test WarehouseService initialization"""
        service = WarehouseService(mock_warehouse_repo, mock_product_repo, mock_inventory_repo)
        
        assert service.warehouse_repo == mock_warehouse_repo
        assert service.product_repo == mock_product_repo
        assert service.inventory_repo == mock_inventory_repo
        assert service._warehouse_id_generator is not None

    def test_warehouse_service_initialization_with_id_generator(self, mock_warehouse_repo, mock_product_repo, mock_inventory_repo, mock_id_generator):
        """Test WarehouseService initialization with custom ID generator"""
        service = WarehouseService(
            warehouse_repo=mock_warehouse_repo,
            product_repo=mock_product_repo,
            inventory_repo=mock_inventory_repo,
            id_generator=mock_id_generator
        )
        
        assert service._warehouse_id_generator == mock_id_generator

    # ============================================================================
    # CREATE WAREHOUSE TESTS
    # ============================================================================

    def test_create_warehouse_success(self, warehouse_service, mock_id_generator):
        """Test create_warehouse successful creation"""
        # Mock dependencies
        mock_id_generator.return_value = 123
        warehouse_service.warehouse_repo.create_warehouse = Mock()
        
        result = warehouse_service.create_warehouse("Test Location")
        
        assert result.warehouse_id == 123
        assert result.location == "Test Location"
        mock_id_generator.assert_called_once()
        warehouse_service.warehouse_repo.create_warehouse.assert_called_once()

    def test_create_warehouse_with_empty_location(self, warehouse_service):
        """Test create_warehouse with empty location"""
        # Mock dependencies
        warehouse_service.warehouse_repo.create_warehouse = Mock()
        
        # Should raise ValidationError for empty location
        with pytest.raises(ValidationError, match="location must be a non-empty string"):
            warehouse_service.create_warehouse("")

    def test_create_warehouse_with_unicode_location(self, warehouse_service):
        """Test create_warehouse with Unicode location"""
        # Mock dependencies
        warehouse_service.warehouse_repo.create_warehouse = Mock()
        
        unicode_location = "Tëst Wäréhøüse Løçátïøn"
        result = warehouse_service.create_warehouse(unicode_location)
        
        assert result.location == unicode_location

    # ============================================================================
    # CREATE WAREHOUSE WITH ID TESTS
    # ============================================================================

    def test_create_warehouse_with_id_success(self, warehouse_service, sample_warehouse):
        """Test create_warehouse_with_id successful creation"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=None)
        warehouse_service.warehouse_repo.create_warehouse = Mock()
        
        warehouse_service.create_warehouse_with_id(sample_warehouse)
        
        warehouse_service.warehouse_repo.get.assert_called_once_with(1)
        warehouse_service.warehouse_repo.create_warehouse.assert_called_once_with(sample_warehouse)

    def test_create_warehouse_with_id_already_exists(self, warehouse_service, sample_warehouse):
        """Test create_warehouse_with_id when warehouse already exists"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        
        with pytest.raises(EntityAlreadyExistsError, match="Warehouse with ID 1 already exists"):
            warehouse_service.create_warehouse_with_id(sample_warehouse)

    # ============================================================================
    # GET WAREHOUSE TESTS
    # ============================================================================

    def test_get_warehouse_success(self, warehouse_service, sample_warehouse):
        """Test get_warehouse successful retrieval"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        
        result = warehouse_service.get_warehouse(1)
        
        assert result == sample_warehouse
        warehouse_service.warehouse_repo.get.assert_called_once_with(1)

    def test_get_warehouse_not_found(self, warehouse_service):
        """Test get_warehouse when warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=None)
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_service.get_warehouse(1)

    # ============================================================================
    # ADD PRODUCT TO WAREHOUSE TESTS
    # ============================================================================

    def test_add_product_to_warehouse_success(self, warehouse_service, sample_warehouse, sample_product):
        """Test add_product_to_warehouse successful addition"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service.warehouse_repo.add_product_to_warehouse = Mock()
        
        warehouse_service.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=10)
        
        warehouse_service.warehouse_repo.get.assert_called_once_with(1)
        warehouse_service.product_repo.get.assert_called_once_with(1)
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_called_once_with(1, 1, 10)

    def test_add_product_to_warehouse_negative_quantity(self, warehouse_service):
        """Test add_product_to_warehouse with negative quantity"""
        with pytest.raises(InvalidQuantityError, match="Quantity must be positive"):
            warehouse_service.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=-5)

    def test_add_product_to_warehouse_zero_quantity(self, warehouse_service):
        """Test add_product_to_warehouse with zero quantity"""
        with pytest.raises(InvalidQuantityError, match="Quantity must be positive"):
            warehouse_service.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=0)

    def test_add_product_to_warehouse_warehouse_not_found(self, warehouse_service):
        """Test add_product_to_warehouse when warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=None)
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_service.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=10)

    def test_add_product_to_warehouse_product_not_found(self, warehouse_service, sample_warehouse):
        """Test add_product_to_warehouse when product not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=None)
        
        with pytest.raises(ProductNotFoundError, match="Product 1 not found"):
            warehouse_service.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=10)

    def test_add_product_to_warehouse_large_quantity(self, warehouse_service, sample_warehouse, sample_product):
        """Test add_product_to_warehouse with large quantity"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service.warehouse_repo.add_product_to_warehouse = Mock()
        
        warehouse_service.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=1000000)
        
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_called_once_with(1, 1, 1000000)

    # ============================================================================
    # REMOVE PRODUCT FROM WAREHOUSE TESTS
    # ============================================================================

    def test_remove_product_from_warehouse_success(self, warehouse_service, sample_warehouse, sample_product):
        """Test remove_product_from_warehouse successful removal"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=50)
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        
        warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=10)
        
        warehouse_service.warehouse_repo.get.assert_called_once_with(1)
        warehouse_service.product_repo.get.assert_called_once_with(1)
        warehouse_service._get_warehouse_product_quantity.assert_called_once_with(1, 1)
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_called_once_with(1, 1, 10)

    def test_remove_product_from_warehouse_negative_quantity(self, warehouse_service):
        """Test remove_product_from_warehouse with negative quantity"""
        with pytest.raises(InvalidQuantityError, match="Quantity must be positive"):
            warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=-5)

    def test_remove_product_from_warehouse_zero_quantity(self, warehouse_service):
        """Test remove_product_from_warehouse with zero quantity"""
        with pytest.raises(InvalidQuantityError, match="Quantity must be positive"):
            warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=0)

    def test_remove_product_from_warehouse_warehouse_not_found(self, warehouse_service):
        """Test remove_product_from_warehouse when warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=None)
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=10)

    def test_remove_product_from_warehouse_product_not_found(self, warehouse_service, sample_warehouse):
        """Test remove_product_from_warehouse when product not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=None)
        
        with pytest.raises(ProductNotFoundError, match="Product 1 not found"):
            warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=10)

    def test_remove_product_from_warehouse_insufficient_stock(self, warehouse_service, sample_warehouse, sample_product):
        """Test remove_product_from_warehouse with insufficient stock"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=5)
        
        with pytest.raises(InsufficientStockError, match="Insufficient stock in warehouse: only 5 items available"):
            warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=10)

    def test_remove_product_from_warehouse_exact_stock(self, warehouse_service, sample_warehouse, sample_product):
        """Test remove_product_from_warehouse with exact available stock"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=10)
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        
        warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=10)
        
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_called_once_with(1, 1, 10)

    # ============================================================================
    # GET WAREHOUSE INVENTORY TESTS
    # ============================================================================

    def test_get_warehouse_inventory_success(self, warehouse_service, sample_warehouse, sample_inventory_item):
        """Test get_warehouse_inventory successful retrieval"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[sample_inventory_item])
        
        result = warehouse_service.get_warehouse_inventory(1)
        
        assert result == [sample_inventory_item]
        warehouse_service.warehouse_repo.get.assert_called_once_with(1)
        warehouse_service.warehouse_repo.get_warehouse_inventory.assert_called_once_with(1)

    def test_get_warehouse_inventory_warehouse_not_found(self, warehouse_service):
        """Test get_warehouse_inventory when warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=None)
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_service.get_warehouse_inventory(1)

    def test_get_warehouse_inventory_empty(self, warehouse_service, sample_warehouse):
        """Test get_warehouse_inventory with empty inventory"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[])
        
        result = warehouse_service.get_warehouse_inventory(1)
        
        assert result == []

    # ============================================================================
    # TRANSFER PRODUCT TESTS
    # ============================================================================

    def test_transfer_product_success(self, warehouse_service, sample_warehouse, sample_product):
        """Test transfer_product successful transfer"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=50)
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        warehouse_service.warehouse_repo.add_product_to_warehouse = Mock()
        
        warehouse_service.transfer_product(
            from_warehouse_id=1,
            to_warehouse_id=2,
            product_id=1,
            quantity=10
        )
        
        # Verify calls
        assert warehouse_service.warehouse_repo.get.call_count == 2  # Called for both warehouses
        warehouse_service.product_repo.get.assert_called_once_with(1)
        warehouse_service._get_warehouse_product_quantity.assert_called_once_with(1, 1)
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_called_once_with(1, 1, 10)
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_called_once_with(2, 1, 10)

    def test_transfer_product_negative_quantity(self, warehouse_service):
        """Test transfer_product with negative quantity"""
        with pytest.raises(InvalidQuantityError, match="Transfer quantity must be positive"):
            warehouse_service.transfer_product(from_warehouse_id=1, to_warehouse_id=2, product_id=1, quantity=-5)

    def test_transfer_product_zero_quantity(self, warehouse_service):
        """Test transfer_product with zero quantity"""
        with pytest.raises(InvalidQuantityError, match="Transfer quantity must be positive"):
            warehouse_service.transfer_product(from_warehouse_id=1, to_warehouse_id=2, product_id=1, quantity=0)

    def test_transfer_product_same_warehouse(self, warehouse_service):
        """Test transfer_product to same warehouse"""
        with pytest.raises(ValidationError, match="Cannot transfer to the same warehouse"):
            warehouse_service.transfer_product(from_warehouse_id=1, to_warehouse_id=1, product_id=1, quantity=10)

    def test_transfer_product_from_warehouse_not_found(self, warehouse_service):
        """Test transfer_product when source warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(side_effect=[None, None])
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_service.transfer_product(from_warehouse_id=1, to_warehouse_id=2, product_id=1, quantity=10)

    def test_transfer_product_to_warehouse_not_found(self, warehouse_service, sample_warehouse):
        """Test transfer_product when destination warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(side_effect=[sample_warehouse, None])
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 2 not found"):
            warehouse_service.transfer_product(from_warehouse_id=1, to_warehouse_id=2, product_id=1, quantity=10)

    def test_transfer_product_product_not_found(self, warehouse_service, sample_warehouse):
        """Test transfer_product when product not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=None)
        
        with pytest.raises(ProductNotFoundError, match="Product 1 not found"):
            warehouse_service.transfer_product(from_warehouse_id=1, to_warehouse_id=2, product_id=1, quantity=10)

    def test_transfer_product_insufficient_stock(self, warehouse_service, sample_warehouse, sample_product):
        """Test transfer_product with insufficient stock"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=5)
        
        with pytest.raises(InsufficientStockError, match="Source warehouse only has 5 items"):
            warehouse_service.transfer_product(from_warehouse_id=1, to_warehouse_id=2, product_id=1, quantity=10)

    def test_transfer_product_large_quantity(self, warehouse_service, sample_warehouse, sample_product):
        """Test transfer_product with large quantity"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=1000000)
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        warehouse_service.warehouse_repo.add_product_to_warehouse = Mock()
        
        warehouse_service.transfer_product(
            from_warehouse_id=1,
            to_warehouse_id=2,
            product_id=1,
            quantity=500000
        )
        
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_called_once_with(1, 1, 500000)
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_called_once_with(2, 1, 500000)

    # ============================================================================
    # GET ALL WAREHOUSES WITH INVENTORY SUMMARY TESTS
    # ============================================================================

    def test_get_all_warehouses_with_inventory_summary_success(self, warehouse_service, sample_warehouse, sample_inventory_item):
        """Test get_all_warehouses_with_inventory_summary successful retrieval"""
        # Mock dependencies
        warehouses_dict = {1: sample_warehouse}
        warehouse_service.warehouse_repo.get_all = Mock(return_value=warehouses_dict)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[sample_inventory_item])
        
        result = warehouse_service.get_all_warehouses_with_inventory_summary()
        
        assert len(result) == 1
        assert result[0]["warehouse"] == sample_warehouse
        assert result[0]["inventory_summary"]["total_items"] == 50
        assert result[0]["inventory_summary"]["unique_products"] == 1
        assert result[0]["inventory_summary"]["inventory_details"] == [sample_inventory_item]

    def test_get_all_warehouses_with_inventory_summary_empty(self, warehouse_service):
        """Test get_all_warehouses_with_inventory_summary with no warehouses"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get_all = Mock(return_value={})
        
        result = warehouse_service.get_all_warehouses_with_inventory_summary()
        
        assert result == []

    def test_get_all_warehouses_with_inventory_summary_empty_inventory(self, warehouse_service, sample_warehouse):
        """Test get_all_warehouses_with_inventory_summary with empty inventory"""
        # Mock dependencies
        warehouses_dict = {1: sample_warehouse}
        warehouse_service.warehouse_repo.get_all = Mock(return_value=warehouses_dict)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[])
        
        result = warehouse_service.get_all_warehouses_with_inventory_summary()
        
        assert len(result) == 1
        assert result[0]["inventory_summary"]["total_items"] == 0
        assert result[0]["inventory_summary"]["unique_products"] == 0
        assert result[0]["inventory_summary"]["inventory_details"] == []

    def test_get_all_warehouses_with_inventory_summary_multiple_warehouses(self, warehouse_service):
        """Test get_all_warehouses_with_inventory_summary with multiple warehouses"""
        # Mock dependencies
        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse 1")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse 2")
        warehouses_dict = {1: warehouse1, 2: warehouse2}
        
        inventory_item1 = InventoryItem(product_id=1, quantity=10)
        inventory_item2 = InventoryItem(product_id=2, quantity=20)
        
        warehouse_service.warehouse_repo.get_all = Mock(return_value=warehouses_dict)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(side_effect=[[inventory_item1], [inventory_item2]])
        
        result = warehouse_service.get_all_warehouses_with_inventory_summary()
        
        assert len(result) == 2
        assert result[0]["warehouse"] == warehouse1
        assert result[0]["inventory_summary"]["total_items"] == 10
        assert result[1]["warehouse"] == warehouse2
        assert result[1]["inventory_summary"]["total_items"] == 20

    # ============================================================================
    # GET ALL WAREHOUSES TESTS
    # ============================================================================

    def test_get_all_warehouses_success(self, warehouse_service, sample_warehouse):
        """Test get_all_warehouses successful retrieval"""
        # Mock dependencies
        warehouses_dict = {1: sample_warehouse}
        warehouse_service.warehouse_repo.get_all = Mock(return_value=warehouses_dict)
        
        result = warehouse_service.get_all_warehouses()
        
        assert len(result) == 1
        assert result[0] == sample_warehouse

    def test_get_all_warehouses_empty(self, warehouse_service):
        """Test get_all_warehouses with no warehouses"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get_all = Mock(return_value={})
        
        result = warehouse_service.get_all_warehouses()
        
        assert result == []

    # ============================================================================
    # TRANSFER ALL INVENTORY TESTS
    # ============================================================================

    def test_transfer_all_inventory_success(self, warehouse_service, sample_warehouse):
        """Test transfer_all_inventory successful transfer"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        
        inventory_item1 = InventoryItem(product_id=1, quantity=10)
        inventory_item2 = InventoryItem(product_id=2, quantity=20)
        source_inventory = [inventory_item1, inventory_item2]
        
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=source_inventory)
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        warehouse_service.warehouse_repo.add_product_to_warehouse = Mock()
        
        result = warehouse_service.transfer_all_inventory(from_warehouse_id=1, to_warehouse_id=2)
        
        assert result == source_inventory
        assert warehouse_service.warehouse_repo.remove_product_from_warehouse.call_count == 2
        assert warehouse_service.warehouse_repo.add_product_to_warehouse.call_count == 2
        
        # Verify specific calls
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_any_call(1, 1, 10)
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_any_call(1, 2, 20)
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_any_call(2, 1, 10)
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_any_call(2, 2, 20)

    def test_transfer_all_inventory_same_warehouse(self, warehouse_service):
        """Test transfer_all_inventory to same warehouse"""
        with pytest.raises(ValidationError, match="Cannot transfer to the same warehouse"):
            warehouse_service.transfer_all_inventory(from_warehouse_id=1, to_warehouse_id=1)

    def test_transfer_all_inventory_from_warehouse_not_found(self, warehouse_service):
        """Test transfer_all_inventory when source warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=None)
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_service.transfer_all_inventory(from_warehouse_id=1, to_warehouse_id=2)

    def test_transfer_all_inventory_to_warehouse_not_found(self, warehouse_service, sample_warehouse):
        """Test transfer_all_inventory when destination warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(side_effect=[sample_warehouse, None])
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 2 not found"):
            warehouse_service.transfer_all_inventory(from_warehouse_id=1, to_warehouse_id=2)

    def test_transfer_all_inventory_empty_inventory(self, warehouse_service, sample_warehouse):
        """Test transfer_all_inventory with empty inventory"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[])
        
        result = warehouse_service.transfer_all_inventory(from_warehouse_id=1, to_warehouse_id=2)
        
        assert result == []
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_not_called()
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_not_called()

    # ============================================================================
    # DELETE WAREHOUSE TESTS
    # ============================================================================

    def test_delete_warehouse_success(self, warehouse_service, sample_warehouse):
        """Test delete_warehouse successful deletion"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[])
        warehouse_service.warehouse_repo.delete = Mock()
        
        warehouse_service.delete_warehouse(1)
        
        warehouse_service.warehouse_repo.get.assert_called_once_with(1)
        warehouse_service.warehouse_repo.get_warehouse_inventory.assert_called_once_with(1)
        warehouse_service.warehouse_repo.delete.assert_called_once_with(1)

    def test_delete_warehouse_not_found(self, warehouse_service):
        """Test delete_warehouse when warehouse not found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=None)
        
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            warehouse_service.delete_warehouse(1)

    def test_delete_warehouse_with_inventory(self, warehouse_service, sample_warehouse, sample_inventory_item):
        """Test delete_warehouse when warehouse has inventory"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[sample_inventory_item])
        
        with pytest.raises(ValidationError, match="Cannot delete warehouse 1: warehouse still has 50 items"):
            warehouse_service.delete_warehouse(1)

    def test_delete_warehouse_with_multiple_products(self, warehouse_service, sample_warehouse):
        """Test delete_warehouse when warehouse has multiple products"""
        # Mock dependencies
        inventory_item1 = InventoryItem(product_id=1, quantity=10)
        inventory_item2 = InventoryItem(product_id=2, quantity=20)
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[inventory_item1, inventory_item2])
        
        with pytest.raises(ValidationError, match="Cannot delete warehouse 1: warehouse still has 30 items \\(2 unique products\\)"):
            warehouse_service.delete_warehouse(1)

    # ============================================================================
    # PRIVATE METHOD TESTS
    # ============================================================================

    def test_get_warehouse_product_quantity_found(self, warehouse_service, sample_inventory_item):
        """Test _get_warehouse_product_quantity when product is found"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[sample_inventory_item])
        
        result = warehouse_service._get_warehouse_product_quantity(warehouse_id=1, product_id=1)
        
        assert result == 50

    def test_get_warehouse_product_quantity_not_found(self, warehouse_service):
        """Test _get_warehouse_product_quantity when product is not found"""
        # Mock dependencies
        inventory_item = InventoryItem(product_id=2, quantity=30)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[inventory_item])
        
        result = warehouse_service._get_warehouse_product_quantity(warehouse_id=1, product_id=1)
        
        assert result == 0

    def test_get_warehouse_product_quantity_empty_inventory(self, warehouse_service):
        """Test _get_warehouse_product_quantity with empty inventory"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[])
        
        result = warehouse_service._get_warehouse_product_quantity(warehouse_id=1, product_id=1)
        
        assert result == 0

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    def test_service_integration_add_remove_cycle(self, warehouse_service, sample_warehouse, sample_product):
        """Test integration between add and remove methods"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=50)
        warehouse_service.warehouse_repo.add_product_to_warehouse = Mock()
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        
        # Add product
        warehouse_service.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=25)
        
        # Remove product
        warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=15)
        
        # Verify calls
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_called_once_with(1, 1, 25)
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_called_once_with(1, 1, 15)

    def test_service_integration_transfer_and_summary(self, warehouse_service, sample_warehouse, sample_product):
        """Test integration between transfer and summary methods"""
        # Mock dependencies
        warehouses_dict = {1: sample_warehouse, 2: sample_warehouse}
        warehouse_service.warehouse_repo.get_all = Mock(return_value=warehouses_dict)
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=50)
        warehouse_service.warehouse_repo.get_warehouse_inventory = Mock(return_value=[])
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        warehouse_service.warehouse_repo.add_product_to_warehouse = Mock()
        
        # Transfer product
        warehouse_service.transfer_product(from_warehouse_id=1, to_warehouse_id=2, product_id=1, quantity=10)
        
        # Get summary
        summary = warehouse_service.get_all_warehouses_with_inventory_summary()
        
        # Verify integration
        assert len(summary) == 2
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_called_once_with(1, 1, 10)
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_called_once_with(2, 1, 10)

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_service_with_large_quantities(self, warehouse_service, sample_warehouse, sample_product):
        """Test service methods with large quantities"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=1000000)
        warehouse_service.warehouse_repo.add_product_to_warehouse = Mock()
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        
        # Add large quantity
        warehouse_service.add_product_to_warehouse(warehouse_id=1, product_id=1, quantity=1000000)
        
        # Remove large quantity
        warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=500000)
        
        # Verify calls
        warehouse_service.warehouse_repo.add_product_to_warehouse.assert_called_once_with(1, 1, 1000000)
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_called_once_with(1, 1, 500000)

    def test_service_with_boundary_conditions(self, warehouse_service, sample_warehouse, sample_product):
        """Test service methods with boundary conditions"""
        # Mock dependencies
        warehouse_service.warehouse_repo.get = Mock(return_value=sample_warehouse)
        warehouse_service.product_repo.get = Mock(return_value=sample_product)
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=1)
        warehouse_service.warehouse_repo.remove_product_from_warehouse = Mock()
        
        # Remove exactly available quantity
        warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=1)
        
        # Verify call
        warehouse_service.warehouse_repo.remove_product_from_warehouse.assert_called_once_with(1, 1, 1)
        
        # Try to remove more than available
        warehouse_service._get_warehouse_product_quantity = Mock(return_value=1)
        
        with pytest.raises(InsufficientStockError, match="Insufficient stock in warehouse: only 1 items available"):
            warehouse_service.remove_product_from_warehouse(warehouse_id=1, product_id=1, quantity=2)

    def test_service_with_unicode_data(self, warehouse_service):
        """Test service methods with Unicode data"""
        # Mock dependencies
        unicode_location = "Tëst Wäréhøüse"
        unicode_warehouse = Warehouse(warehouse_id=1, location=unicode_location)
        warehouse_service.warehouse_repo.create_warehouse = Mock()
        
        # Create warehouse with Unicode location
        result = warehouse_service.create_warehouse(unicode_location)
        
        assert result.location == unicode_location

    def test_service_with_special_characters(self, warehouse_service):
        """Test service methods with special characters"""
        # Mock dependencies
        special_location = "Warehouse-123_@#$%"
        warehouse_service.warehouse_repo.create_warehouse = Mock()
        
        # Create warehouse with special characters
        result = warehouse_service.create_warehouse(special_location)
        
        assert result.location == special_location
