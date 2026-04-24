"""
Comprehensive Unit Tests for ProductService
Covers all ProductService methods, validation, edge cases, and business logic
"""

import pytest
from unittest.mock import Mock, MagicMock, call
from typing import Dict, List

from app.application.services.product_service import ProductService
from app.domain.entities.product import Product
from app.domain.exceptions import ValidationError, EntityNotFoundError
from app.domain.interfaces import IProductRepo, IInventoryRepo


class TestProductService:
    """Test ProductService Application Service"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_product_repo(self):
        """Mock product repository"""
        return Mock(spec=IProductRepo)

    @pytest.fixture
    def mock_inventory_repo(self):
        """Mock inventory repository"""
        return Mock(spec=IInventoryRepo)

    @pytest.fixture
    def product_service(self, mock_product_repo, mock_inventory_repo):
        """ProductService instance with mocked dependencies"""
        service = ProductService(mock_product_repo, mock_inventory_repo)
        
        # Ensure command handler methods are properly mocked
        service._command_handler.handle_create = Mock()
        service._command_handler.handle_update = Mock()
        service._validator.validate_csv_rows = Mock()
        service._validator.validate_import_data = Mock()
        
        return service

    @pytest.fixture
    def sample_product(self):
        """Sample product for testing"""
        return Product(product_id=1, name="Test Product", price=99.99, description="Test Description")

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_product_service_initialization(self, mock_product_repo, mock_inventory_repo):
        """Test ProductService initialization"""
        service = ProductService(mock_product_repo, mock_inventory_repo)
        
        assert service._command_handler is not None
        assert service._query_handler is not None
        assert service._validator is not None

    # ============================================================================
    # CREATE PRODUCT TESTS
    # ============================================================================

    def test_create_product_valid_data(self, product_service, sample_product):
        """Test create_product with valid data"""
        # Mock the command handler
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        
        result = product_service.create_product(
            product_id=1,
            name="Test Product",
            price=99.99,
            description="Test Description"
        )
        
        assert result == sample_product
        product_service._command_handler.handle_create.assert_called_once()

    def test_create_product_minimal_data(self, product_service, sample_product):
        """Test create_product with minimal data"""
        # Mock the command handler
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        
        result = product_service.create_product(
            name="Test Product",
            price=99.99
        )
        
        assert result == sample_product
        product_service._command_handler.handle_create.assert_called_once()

    def test_create_product_legacy_arguments(self, product_service, sample_product):
        """Test create_product with legacy positional arguments"""
        # Mock the command handler
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        
        # Legacy call: name, price, description, product_id
        result = product_service.create_product("Test Product", 99.99, "Test Description", 1)
        
        assert result == sample_product
        product_service._command_handler.handle_create.assert_called_once()

    def test_create_product_legacy_mixed_arguments(self, product_service, sample_product):
        """Test create_product with mixed legacy and new arguments"""
        # Mock the command handler
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        
        # Legacy call with string name, numeric price, but no product_id
        result = product_service.create_product("Test Product", 99.99)
        
        assert result == sample_product
        product_service._command_handler.handle_create.assert_called_once()

    def test_create_product_command_handler_exception(self, product_service):
        """Test create_product when command handler raises exception"""
        # Mock the command handler to raise exception
        product_service._command_handler.handle_create = Mock(side_effect=ValidationError("Invalid data"))
        
        with pytest.raises(ValidationError, match="Invalid data"):
            product_service.create_product(name="Test Product", price=99.99)

    # ============================================================================
    # GET PRODUCT DETAILS TESTS
    # ============================================================================

    def test_get_product_details_success(self, product_service, sample_product):
        """Test get_product_details successful retrieval"""
        # Mock the query handler
        product_service._query_handler.handle_get = Mock(return_value=sample_product)
        
        result = product_service.get_product_details(1)
        
        assert result == sample_product
        product_service._query_handler.handle_get.assert_called_once()

    def test_get_product_details_not_found(self, product_service):
        """Test get_product_details when product not found"""
        # Mock the query handler to raise exception
        product_service._query_handler.handle_get = Mock(side_effect=EntityNotFoundError("Product not found"))
        
        with pytest.raises(EntityNotFoundError, match="Product not found"):
            product_service.get_product_details(1)

    # ============================================================================
    # UPDATE PRODUCT TESTS
    # ============================================================================

    def test_update_product_success(self, product_service, sample_product):
        """Test update_product successful update"""
        # Mock the command handler
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        
        result = product_service.update_product(
            product_id=1,
            name="Updated Product",
            price=149.99,
            description="Updated Description"
        )
        
        assert result == sample_product
        product_service._command_handler.handle_update.assert_called_once()

    def test_update_product_partial_update(self, product_service, sample_product):
        """Test update_product with partial data"""
        # Mock the command handler
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        
        result = product_service.update_product(
            product_id=1,
            name="Updated Product"
        )
        
        assert result == sample_product
        product_service._command_handler.handle_update.assert_called_once()

    def test_update_product_not_found(self, product_service):
        """Test update_product when product not found"""
        # Mock the command handler to raise exception
        product_service._command_handler.handle_update = Mock(side_effect=EntityNotFoundError("Product not found"))
        
        with pytest.raises(EntityNotFoundError, match="Product not found"):
            product_service.update_product(product_id=1, name="Updated Product")

    # ============================================================================
    # DELETE PRODUCT TESTS
    # ============================================================================

    def test_delete_product_success(self, product_service):
        """Test delete_product successful deletion"""
        # Mock the command handler
        product_service._command_handler.handle_delete = Mock(return_value=None)
        
        result = product_service.delete_product(1)
        
        assert result is None
        product_service._command_handler.handle_delete.assert_called_once()

    def test_delete_product_not_found(self, product_service):
        """Test delete_product when product not found"""
        # Mock the command handler to raise exception
        product_service._command_handler.handle_delete = Mock(side_effect=EntityNotFoundError("Product not found"))
        
        with pytest.raises(EntityNotFoundError, match="Product not found"):
            product_service.delete_product(1)

    # ============================================================================
    # GET PRODUCT WITH INVENTORY TESTS
    # ============================================================================

    def test_get_product_with_inventory_success(self, product_service, sample_product):
        """Test get_product_with_inventory successful retrieval"""
        # Mock dependencies
        product_service._query_handler.handle_get = Mock(return_value=sample_product)
        product_service._command_handler.inventory_repo.get_quantity = Mock(return_value=50)
        
        result = product_service.get_product_with_inventory(1)
        
        expected = {"product": sample_product, "current_inventory": 50}
        assert result == expected
        product_service._query_handler.handle_get.assert_called_once()
        product_service._command_handler.inventory_repo.get_quantity.assert_called_once_with(1)

    def test_get_product_with_inventory_product_not_found(self, product_service):
        """Test get_product_with_inventory when product not found"""
        # Mock dependencies
        product_service._query_handler.handle_get = Mock(side_effect=EntityNotFoundError("Product not found"))
        
        with pytest.raises(EntityNotFoundError, match="Product not found"):
            product_service.get_product_with_inventory(1)

    def test_get_product_with_inventory_zero_quantity(self, product_service, sample_product):
        """Test get_product_with_inventory with zero inventory"""
        # Mock dependencies
        product_service._query_handler.handle_get = Mock(return_value=sample_product)
        product_service._command_handler.inventory_repo.get_quantity = Mock(return_value=0)
        
        result = product_service.get_product_with_inventory(1)
        
        expected = {"product": sample_product, "current_inventory": 0}
        assert result == expected

    # ============================================================================
    # LIST PRODUCTS WITH INVENTORY TESTS
    # ============================================================================

    def test_list_products_with_inventory_success(self, product_service, sample_product):
        """Test list_products_with_inventory successful retrieval"""
        # Mock dependencies
        products_dict = {1: sample_product}
        product_service._query_handler.product_repo.get_all = Mock(return_value=products_dict)
        product_service._command_handler.inventory_repo.get_quantity = Mock(return_value=25)
        
        result = product_service.list_products_with_inventory()
        
        expected = [{"product": sample_product, "current_inventory": 25}]
        assert result == expected
        product_service._query_handler.product_repo.get_all.assert_called_once()
        product_service._command_handler.inventory_repo.get_quantity.assert_called_once_with(1)

    def test_list_products_with_inventory_empty(self, product_service):
        """Test list_products_with_inventory with no products"""
        # Mock dependencies
        product_service._query_handler.product_repo.get_all = Mock(return_value={})
        
        result = product_service.list_products_with_inventory()
        
        assert result == []
        product_service._query_handler.product_repo.get_all.assert_called_once()

    def test_list_products_with_inventory_multiple_products(self, product_service):
        """Test list_products_with_inventory with multiple products"""
        # Create sample products
        product1 = Product(product_id=1, name="Product 1", price=10.0)
        product2 = Product(product_id=2, name="Product 2", price=20.0)
        products_dict = {1: product1, 2: product2}
        
        # Mock dependencies
        product_service._query_handler.product_repo.get_all = Mock(return_value=products_dict)
        product_service._command_handler.inventory_repo.get_quantity = Mock(side_effect=[15, 25])
        
        result = product_service.list_products_with_inventory()
        
        expected = [
            {"product": product1, "current_inventory": 15},
            {"product": product2, "current_inventory": 25}
        ]
        assert result == expected

    # ============================================================================
    # GET ALL PRODUCTS TESTS
    # ============================================================================

    def test_get_all_products_success(self, product_service, sample_product):
        """Test get_all_products successful retrieval"""
        # Mock the query handler
        products_list = [sample_product]
        product_service._query_handler.handle_get_all = Mock(return_value=products_list)
        
        result = product_service.get_all_products()
        
        assert result == products_list
        product_service._query_handler.handle_get_all.assert_called_once()

    def test_get_all_products_empty(self, product_service):
        """Test get_all_products with no products"""
        # Mock the query handler
        product_service._query_handler.handle_get_all = Mock(return_value=[])
        
        result = product_service.get_all_products()
        
        assert result == []

    # ============================================================================
    # IMPORT PRODUCTS TESTS
    # ============================================================================

    def test_import_products_new_products(self, product_service, sample_product):
        """Test import_products with new products only"""
        # Mock dependencies
        rows = [
            {"product_id": 1, "name": "Product 1", "price": 10.0, "description": "Description 1"},
            {"product_id": 2, "name": "Product 2", "price": 20.0}
        ]
        
        product_service._validator.validate_csv_rows = Mock()
        product_service._validator.validate_import_data = Mock()
        product_service._query_handler.product_repo.get = Mock(side_effect=[None, None])  # Both products don't exist
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        
        result = product_service.import_products(rows)
        
        expected = {"created": 2, "updated": 0}
        assert result == expected
        assert product_service._validator.validate_csv_rows.call_count == 1
        assert product_service._validator.validate_import_data.call_count == 2
        assert product_service._command_handler.handle_create.call_count == 2
        assert product_service._command_handler.handle_update.call_count == 0

    def test_import_products_existing_products(self, product_service, sample_product):
        """Test import_products with existing products only"""
        # Mock dependencies
        rows = [
            {"product_id": 1, "name": "Updated Product 1", "price": 15.0, "description": "Updated Description 1"},
            {"product_id": 2, "name": "Updated Product 2", "price": 25.0}
        ]
        
        product_service._validator.validate_csv_rows = Mock()
        product_service._validator.validate_import_data = Mock()
        product_service._query_handler.product_repo.get = Mock(side_effect=[sample_product, sample_product])  # Both products exist
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        
        result = product_service.import_products(rows)
        
        expected = {"created": 0, "updated": 2}
        assert result == expected
        assert product_service._validator.validate_csv_rows.call_count == 1
        assert product_service._validator.validate_import_data.call_count == 2
        assert product_service._command_handler.handle_create.call_count == 0
        assert product_service._command_handler.handle_update.call_count == 2

    def test_import_products_mixed_new_and_existing(self, product_service, sample_product):
        """Test import_products with mix of new and existing products"""
        # Mock dependencies
        rows = [
            {"product_id": 1, "name": "Product 1", "price": 10.0},
            {"product_id": 2, "name": "Product 2", "price": 20.0},
            {"product_id": 3, "name": "Product 3", "price": 30.0}
        ]
        
        product_service._validator.validate_csv_rows = Mock()
        product_service._validator.validate_import_data = Mock()
        product_service._query_handler.product_repo.get = Mock(side_effect=[None, sample_product, None])  # 1 and 3 don't exist, 2 exists
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        
        result = product_service.import_products(rows)
        
        expected = {"created": 2, "updated": 1}
        assert result == expected
        assert product_service._command_handler.handle_create.call_count == 2
        assert product_service._command_handler.handle_update.call_count == 1

    def test_import_products_validation_error(self, product_service):
        """Test import_products with validation error"""
        # Mock dependencies
        rows = [{"product_id": 1, "name": "Product 1", "price": 10.0}]
        
        product_service._validator.validate_csv_rows = Mock(side_effect=ValidationError("Invalid CSV format"))
        
        with pytest.raises(ValidationError, match="Invalid CSV format"):
            product_service.import_products(rows)

    def test_import_products_individual_validation_error(self, product_service):
        """Test import_products with individual row validation error"""
        # Mock dependencies
        rows = [
            {"product_id": 1, "name": "Product 1", "price": 10.0},
            {"product_id": 2, "name": "Product 2", "price": 20.0}
        ]
        
        product_service._validator.validate_csv_rows = Mock()
        product_service._validator.validate_import_data = Mock(side_effect=ValidationError("Invalid product data"))
        
        with pytest.raises(ValidationError, match="Invalid product data"):
            product_service.import_products(rows)

    def test_import_products_empty_rows(self, product_service):
        """Test import_products with empty rows"""
        # Mock dependencies
        product_service._validator.validate_csv_rows = Mock()
        
        result = product_service.import_products([])
        
        expected = {"created": 0, "updated": 0}
        assert result == expected
        product_service._validator.validate_csv_rows.assert_called_once_with([])

    def test_import_products_missing_optional_fields(self, product_service, sample_product):
        """Test import_products with missing optional fields"""
        # Mock dependencies
        rows = [
            {"product_id": 1, "name": "Product 1"},  # Missing price and description
            {"product_id": 2, "name": "Product 2", "price": 20.0}  # Missing description
        ]
        
        product_service._validator.validate_csv_rows = Mock()
        product_service._validator.validate_import_data = Mock()
        product_service._query_handler.product_repo.get = Mock(side_effect=[None, None])
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        
        result = product_service.import_products(rows)
        
        expected = {"created": 2, "updated": 0}
        assert result == expected

    def test_import_products_default_price_handling(self, product_service, sample_product):
        """Test import_products handles default price correctly"""
        # Mock dependencies
        rows = [
            {"product_id": 1, "name": "Product 1"},  # No price field
            {"product_id": 2, "name": "Product 2", "price": 0}  # Explicit zero price
        ]
        
        product_service._validator.validate_csv_rows = Mock()
        product_service._validator.validate_import_data = Mock()
        product_service._query_handler.product_repo.get = Mock(side_effect=[None, None])
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        
        result = product_service.import_products(rows)
        
        expected = {"created": 2, "updated": 0}
        assert result == expected
        
        # Verify that default price (0) is used when price is missing
        calls = product_service._command_handler.handle_create.call_args_list
        first_call_kwargs = calls[0][1] if len(calls[0]) > 1 else {}
        assert first_call_kwargs.get('price', 0.0) == 0.0  # First call should have default price
        second_call_kwargs = calls[1][1] if len(calls[1]) > 1 else {}
        assert second_call_kwargs.get('price', 0) == 0  # Second call should have explicit zero price

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    def test_service_integration_create_and_get(self, product_service, sample_product):
        """Test integration between create and get methods"""
        # Mock dependencies
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        product_service._query_handler.handle_get = Mock(return_value=sample_product)
        
        # Create product
        created = product_service.create_product(
            product_id=1,
            name="Test Product",
            price=99.99
        )
        
        # Get product
        retrieved = product_service.get_product_details(1)
        
        assert created == retrieved == sample_product

    def test_service_integration_update_and_get_with_inventory(self, product_service, sample_product):
        """Test integration between update and get with inventory methods"""
        # Mock dependencies
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        product_service._query_handler.handle_get = Mock(return_value=sample_product)
        product_service._command_handler.inventory_repo.get_quantity = Mock(return_value=75)
        
        # Update product
        updated = product_service.update_product(
            product_id=1,
            name="Updated Product",
            price=149.99
        )
        
        # Get product with inventory
        with_inventory = product_service.get_product_with_inventory(1)
        
        assert updated == sample_product
        assert with_inventory["product"] == sample_product
        assert with_inventory["current_inventory"] == 75

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_service_with_none_values(self, product_service, sample_product):
        """Test service methods with None values"""
        # Mock dependencies
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        
        # Create with None description
        result1 = product_service.create_product(
            product_id=1,
            name="Test Product",
            price=99.99,
            description=None
        )
        
        # Update with None values
        result2 = product_service.update_product(
            product_id=1,
            name=None,
            price=None,
            description=None
        )
        
        assert result1 == result2 == sample_product

    def test_service_with_large_data(self, product_service, sample_product):
        """Test service methods with large data"""
        # Mock dependencies
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        
        long_name = "A" * 100
        long_description = "B" * 1000
        
        # Create with long data
        result1 = product_service.create_product(
            product_id=1,
            name=long_name,
            price=999999.99,
            description=long_description
        )
        
        # Update with long data
        result2 = product_service.update_product(
            product_id=1,
            name=long_name,
            price=999999.99,
            description=long_description
        )
        
        assert result1 == result2 == sample_product

    def test_service_with_special_characters(self, product_service, sample_product):
        """Test service methods with special characters"""
        # Mock dependencies
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        
        special_name = "Product-123_@#$%"
        special_description = "Special chars: !@#$%^&*(){}[]|\\:;\"'<>?,./"
        
        # Create with special characters
        result1 = product_service.create_product(
            product_id=1,
            name=special_name,
            price=99.99,
            description=special_description
        )
        
        # Update with special characters
        result2 = product_service.update_product(
            product_id=1,
            name=special_name,
            price=99.99,
            description=special_description
        )
        
        assert result1 == result2 == sample_product

    def test_service_with_unicode_characters(self, product_service, sample_product):
        """Test service methods with Unicode characters"""
        # Mock dependencies
        product_service._command_handler.handle_create = Mock(return_value=sample_product)
        product_service._command_handler.handle_update = Mock(return_value=sample_product)
        
        unicode_name = "Üñïçødé Prödüçt"
        unicode_description = "Üñïçødé dëscrïptïøn wïth spécïål chárs"
        
        # Create with Unicode
        result1 = product_service.create_product(
            product_id=1,
            name=unicode_name,
            price=99.99,
            description=unicode_description
        )
        
        # Update with Unicode
        result2 = product_service.update_product(
            product_id=1,
            name=unicode_name,
            price=99.99,
            description=unicode_description
        )
        
        assert result1 == result2 == sample_product
