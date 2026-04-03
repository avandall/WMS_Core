"""
Unit tests for InventoryService.
"""

import pytest
from unittest.mock import Mock
from app.application.services.inventory_service import InventoryService
from app.domain.exceptions import EntityNotFoundError, InvalidQuantityError


class TestInventoryService:
    """Test cases for InventoryService."""

    @pytest.fixture
    def mock_inventory_repo(self):
        """Mock inventory repository."""
        return Mock()

    @pytest.fixture
    def mock_product_repo(self):
        """Mock product repository."""
        return Mock()

    @pytest.fixture
    def mock_warehouse_repo(self):
        """Mock warehouse repository."""
        return Mock()

    @pytest.fixture
    def inventory_service(
        self, mock_inventory_repo, mock_product_repo, mock_warehouse_repo
    ):
        """Inventory service with mocked repositories."""
        return InventoryService(
            mock_inventory_repo, mock_product_repo, mock_warehouse_repo
        )

    def test_add_to_total_success(self, inventory_service, mock_inventory_repo):
        """Test adding quantity to total inventory successfully."""
        # Act
        inventory_service.add_to_total_inventory(1, 10)

        # Assert
        mock_inventory_repo.add_quantity.assert_called_once_with(1, 10)

    def test_add_to_total_validation_error(
        self, inventory_service, mock_inventory_repo
    ):
        """Test adding quantity with validation error."""
        # Act & Assert
        with pytest.raises(
            InvalidQuantityError, match="Cannot add negative quantity to inventory"
        ):
            inventory_service.add_to_total_inventory(1, -5)

    def test_get_total_quantity_success(self, inventory_service, mock_inventory_repo):
        """Test getting total quantity successfully."""
        # Arrange
        mock_inventory_repo.get_quantity.return_value = 25

        # Act
        result = inventory_service.get_total_quantity(1)

        # Assert
        assert result == 25
        mock_inventory_repo.get_quantity.assert_called_once_with(1)

    def test_get_total_quantity_not_found(self, inventory_service, mock_inventory_repo):
        """Test getting total quantity for non-existent product."""
        # Arrange
        mock_inventory_repo.get_quantity.side_effect = EntityNotFoundError(
            "Product not found"
        )

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="Product not found"):
            inventory_service.get_total_quantity(999)

        mock_inventory_repo.get_quantity.assert_called_once_with(999)

    def test_get_all_inventory_success(
        self,
        inventory_service,
        mock_inventory_repo,
        mock_product_repo,
        mock_warehouse_repo,
    ):
        """Test getting all inventory successfully."""
        # Arrange
        from app.domain.entities.inventory import InventoryItem
        from app.domain.entities.warehouse import Warehouse

        mock_items = [
            InventoryItem(product_id=1, quantity=10),
            InventoryItem(product_id=2, quantity=5),
        ]
        mock_inventory_repo.get_all.return_value = mock_items
        mock_inventory_repo.get_quantity.side_effect = lambda pid: 10 if pid == 1 else 5

        # Mock product repo to return products
        mock_product1 = Mock()
        mock_product1.product_id = 1
        mock_product1.name = "Product 1"
        mock_product1.price = 10.0

        mock_product2 = Mock()
        mock_product2.product_id = 2
        mock_product2.name = "Product 2"
        mock_product2.price = 20.0

        mock_product_repo.get.side_effect = (
            lambda pid: mock_product1 if pid == 1 else mock_product2
        )

        # Mock warehouse repo
        mock_warehouse = Warehouse(warehouse_id=1, location="Test Warehouse")
        mock_warehouse_repo.get_all.return_value = {1: mock_warehouse}
        mock_warehouse_repo.get_warehouse_inventory.return_value = []

        # Act
        result = inventory_service.get_all_inventory_with_details()

        # Assert
        assert len(result) == 2
        mock_inventory_repo.get_all.assert_called_once()
