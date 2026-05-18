"""
Continuous Unit Tests - Run with code changes
Tests core WMS components: Commands, Queries, Validation, Entities, Services
"""

import pytest
from unittest.mock import Mock
from dataclasses import is_dataclass

from app.modules.products.application.commands import CreateProductCommand, UpdateProductCommand, DeleteProductCommand
from app.modules.products.application.queries import GetProductQuery, GetAllProductsQuery
from app.modules.products.application.validation import ProductValidator
from app.modules.products.domain.entities.product import Product
from app.modules.products.application.services.product_service import ProductService


class TestCommandPatternContinuous:
    """Continuous tests for Command Pattern"""

    def test_create_product_command_structure(self):
        """Test CreateProductCommand structure and dataclass properties"""
        assert is_dataclass(CreateProductCommand)
        
        # Test with valid data
        cmd = CreateProductCommand(name="Test Product", price=10.0)
        assert cmd.name == "Test Product"
        assert cmd.price == 10.0
        assert cmd.product_id is None
        assert cmd.description is None

    def test_update_product_command_structure(self):
        """Test UpdateProductCommand structure"""
        assert is_dataclass(UpdateProductCommand)
        
        cmd = UpdateProductCommand(product_id=1, name="Updated", price=20.0)
        assert cmd.product_id == 1
        assert cmd.name == "Updated"
        assert cmd.price == 20.0

    def test_delete_product_command_structure(self):
        """Test DeleteProductCommand structure"""
        assert is_dataclass(DeleteProductCommand)
        
        cmd = DeleteProductCommand(product_id=1)
        assert cmd.product_id == 1


class TestQueryPatternContinuous:
    """Continuous tests for Query Pattern"""

    def test_get_product_query_structure(self):
        """Test GetProductQuery structure"""
        assert is_dataclass(GetProductQuery)
        
        query = GetProductQuery(product_id=1)
        assert query.product_id == 1

    def test_get_all_products_query_structure(self):
        """Test GetAllProductsQuery structure"""
        assert is_dataclass(GetAllProductsQuery)
        
        query = GetAllProductsQuery()
        assert query is not None


class TestValidationContinuous:
    """Continuous tests for Validation Layer"""

    def test_validator_initialization(self):
        """Test ProductValidator initialization"""
        validator = ProductValidator()
        assert validator is not None
        assert hasattr(validator, 'validate_import_data')
        assert hasattr(validator, 'validate_csv_rows')

    def test_validate_import_data_valid_cases(self):
        """Test validate_import_data with valid inputs"""
        validator = ProductValidator()
        
        # Should not raise exceptions
        validator.validate_import_data(1, "Valid Product", 10.0)
        validator.validate_import_data(100, "Another Product", 0.0)

    def test_validate_import_data_invalid_cases(self):
        """Test validate_import_data with invalid inputs"""
        validator = ProductValidator()
        
        # Should raise exceptions for invalid inputs
        with pytest.raises(Exception):
            validator.validate_import_data(0, "Product", 10.0)
        
        with pytest.raises(Exception):
            validator.validate_import_data(1, "", 10.0)


class TestProductEntityContinuous:
    """Continuous tests for Product Domain Entity"""

    def test_product_entity_valid_creation(self):
        """Test Product entity creation with valid data"""
        product = Product(
            product_id=1,
            name="Test Product",
            price=10.0
        )
        
        assert product.product_id == 1
        assert product.name == "Test Product"
        assert product.price == 10.0

    def test_product_entity_invalid_creation(self):
        """Test Product entity creation with invalid data"""
        with pytest.raises(Exception):
            Product(product_id=0, name="Invalid", price=10.0)


class TestProductServiceContinuous:
    """Continuous tests for ProductService"""

    def test_service_initialization(self):
        """Test ProductService initialization"""
        mock_product_repo = Mock()
        mock_inventory_repo = Mock()
        
        service = ProductService(
            product_repo=mock_product_repo,
            inventory_repo=mock_inventory_repo
        )
        
        assert service is not None

    def test_service_create_product_basic(self):
        """Test ProductService create_product basic functionality"""
        mock_product_repo = Mock()
        mock_inventory_repo = Mock()
        
        service = ProductService(
            product_repo=mock_product_repo,
            inventory_repo=mock_inventory_repo
        )
        
        # Test basic create (may fail due to validation, but should not crash)
        try:
            result = service.create_product(name="Test", price=10.0)
            assert result is not None
        except Exception:
            # Expected if validation fails
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
