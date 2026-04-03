"""
Unit tests for ProductService.
"""

import pytest
from unittest.mock import Mock
from app.application.services.product_service import ProductService
from app.domain.entities.product import Product
from app.domain.exceptions import ValidationError, EntityNotFoundError


class TestProductService:
    """Test cases for ProductService."""

    @pytest.fixture
    def mock_product_repo(self):
        """Mock product repository."""
        return Mock()

    @pytest.fixture
    def mock_inventory_repo(self):
        """Mock inventory repository."""
        return Mock()

    @pytest.fixture
    def product_service(self, mock_product_repo, mock_inventory_repo):
        """Product service with mocked repositories."""
        return ProductService(
            product_repo=mock_product_repo, inventory_repo=mock_inventory_repo
        )

    @pytest.fixture
    def sample_product(self):
        """Sample product for testing."""
        return Product(
            product_id=1, name="Test Product", description="A test product", price=29.99
        )

    def test_create_product_success(
        self, product_service, mock_product_repo, mock_inventory_repo, sample_product
    ):
        """Test creating a product successfully."""
        # Arrange
        mock_product_repo.get.return_value = None  # Product doesn't exist
        mock_product_repo.save.return_value = None
        mock_inventory_repo.add_quantity.return_value = None

        # Act
        result = product_service.create_product(
            1, "Test Product", 29.99, "A test product"
        )

        # Assert
        assert result.product_id == 1
        assert result.name == "Test Product"
        assert result.price == 29.99
        assert result.description == "A test product"
        mock_product_repo.get.assert_called_once_with(1)
        mock_product_repo.save.assert_called_once()
        mock_inventory_repo.add_quantity.assert_called_once_with(1, 0)

    def test_create_product_minimal(
        self, product_service, mock_product_repo, mock_inventory_repo
    ):
        """Test creating a product with minimal data."""
        # Arrange
        mock_product_repo.get.return_value = None  # Product doesn't exist
        mock_product_repo.save.return_value = None
        mock_inventory_repo.add_quantity.return_value = None

        # Act
        result = product_service.create_product(2, "Minimal Product", 19.99)

        # Assert
        assert result.product_id == 2
        assert result.name == "Minimal Product"
        assert result.price == 19.99
        assert result.description is None

    def test_create_product_validation_error(
        self, product_service, mock_product_repo, mock_inventory_repo
    ):
        """Test creating a product with validation error."""
        # Arrange
        mock_product_repo.get.return_value = None

        # Act & Assert
        with pytest.raises(ValidationError):
            product_service.create_product(1, "", 29.99)  # Empty name

    def test_get_product_details_success(
        self, product_service, mock_product_repo, sample_product
    ):
        """Test getting product details successfully."""
        # Arrange
        mock_product_repo.get.return_value = sample_product

        # Act
        result = product_service.get_product_details(1)

        # Assert
        assert result == sample_product
        mock_product_repo.get.assert_called_once_with(1)

    def test_get_product_details_not_found(self, product_service, mock_product_repo):
        """Test getting product details for non-existent product."""
        # Arrange
        mock_product_repo.get.return_value = None

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            product_service.get_product_details(999)

    def test_update_product_success(
        self, product_service, mock_product_repo, sample_product
    ):
        """Test updating a product successfully."""
        # Arrange
        mock_product_repo.get.return_value = sample_product
        mock_product_repo.save.return_value = None

        # Act
        result = product_service.update_product(1, name="Updated Product", price=39.99)

        # Assert
        assert result.name == "Updated Product"
        assert result.price == 39.99
        mock_product_repo.save.assert_called_once()

    def test_update_product_partial(
        self, product_service, mock_product_repo, sample_product
    ):
        """Test updating a product with partial data."""
        # Arrange
        mock_product_repo.get.return_value = sample_product
        mock_product_repo.save.return_value = None

        # Act
        result = product_service.update_product(1, price=34.99)

        # Assert
        assert result.name == "Test Product"  # Unchanged
        assert result.price == 34.99  # Updated

    def test_update_product_not_found(self, product_service, mock_product_repo):
        """Test updating a non-existent product."""
        # Arrange
        mock_product_repo.get.return_value = None

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            product_service.update_product(999, name="New Name")

    def test_delete_product_success(
        self, product_service, mock_product_repo, mock_inventory_repo
    ):
        """Test deleting a product successfully."""
        # Arrange
        sample_product = Product(product_id=1, name="Test", price=10.0)
        mock_product_repo.get.return_value = sample_product
        mock_inventory_repo.get_quantity.return_value = 0  # No inventory

        # Act
        product_service.delete_product(1)

        # Assert
        mock_product_repo.delete.assert_called_once_with(1)
        mock_inventory_repo.delete.assert_called_once_with(1)

    def test_delete_product_not_found(self, product_service, mock_product_repo):
        """Test deleting a non-existent product."""
        # Arrange
        mock_product_repo.get.return_value = None

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            product_service.delete_product(999)
