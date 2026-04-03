"""
Unit tests for WarehouseRepo.
"""

import pytest
from app.infrastructure.persistence.repositories.warehouse_repo import WarehouseRepo
from app.domain.entities.warehouse import Warehouse
from app.domain.entities.inventory import InventoryItem


class TestWarehouseRepo:
    """Test cases for WarehouseRepo."""

    @pytest.fixture(autouse=True)
    def setup(self, test_session):
        """Set up test fixtures."""
        self.repo = WarehouseRepo(test_session)

    def test_create_and_save_warehouse(self):
        """Test creating and saving a warehouse."""
        warehouse = Warehouse(warehouse_id=1, location="Test Location")

        self.repo.create_warehouse(warehouse)
        retrieved = self.repo.get(1)

        assert retrieved is not None
        assert retrieved.warehouse_id == 1
        assert retrieved.location == "Test Location"

    def test_save_warehouse(self):
        """Test saving a warehouse."""
        warehouse = Warehouse(warehouse_id=1, location="Test Location")
        self.repo.save(warehouse)

        retrieved = self.repo.get(1)
        assert retrieved is not None
        assert retrieved.warehouse_id == 1
        assert retrieved.location == "Test Location"

    def test_get_nonexistent_warehouse(self):
        """Test getting a nonexistent warehouse returns None."""
        result = self.repo.get(999)
        assert result is None

    def test_delete_existing_warehouse(self):
        """Test deleting an existing warehouse."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        self.repo.save(warehouse)

        self.repo.delete(1)
        assert self.repo.get(1) is None

    def test_delete_nonexistent_warehouse(self):
        """Test deleting a nonexistent warehouse does nothing."""
        # Should not raise an exception
        self.repo.delete(999)

    def test_get_warehouse_inventory_existing_warehouse(self):
        """Test getting inventory for existing warehouse."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.inventory.append(InventoryItem(product_id=100, quantity=10))
        warehouse.inventory.append(InventoryItem(product_id=200, quantity=5))
        self.repo.save(warehouse)

        inventory = self.repo.get_warehouse_inventory(1)
        assert len(inventory) == 2
        assert inventory[0].product_id == 100
        assert inventory[0].quantity == 10
        assert inventory[1].product_id == 200
        assert inventory[1].quantity == 5

    def test_get_warehouse_inventory_empty_warehouse(self):
        """Test getting inventory for warehouse with no products."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        self.repo.save(warehouse)

        inventory = self.repo.get_warehouse_inventory(1)
        assert len(inventory) == 0

    def test_get_warehouse_inventory_nonexistent_warehouse(self):
        """Test getting inventory for nonexistent warehouse returns empty list."""
        inventory = self.repo.get_warehouse_inventory(999)
        assert inventory == []
