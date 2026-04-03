"""
SQL integration tests for WarehouseRepo.
Tests actual database operations including cascade deletes, constraints, and relationships.
"""

import pytest

from app.domain.entities.warehouse import Warehouse
from app.domain.entities.product import Product
from app.domain.exceptions import (
    WarehouseNotFoundError,
    InsufficientStockError,
)


class TestWarehouseRepoSQL:
    """Test SQL warehouse repository with real database operations."""

    def test_create_warehouse(self, warehouse_repo_sql):
        """Test creating a warehouse in database."""
        warehouse = Warehouse(warehouse_id=1, location="SQL Test Warehouse")
        warehouse_repo_sql.create_warehouse(warehouse)

        retrieved = warehouse_repo_sql.get(1)
        assert retrieved is not None
        assert retrieved.warehouse_id == 1
        assert retrieved.location == "SQL Test Warehouse"

    def test_save_new_warehouse(self, warehouse_repo_sql):
        """Test saving a new warehouse."""
        warehouse = Warehouse(warehouse_id=10, location="New Warehouse")
        warehouse_repo_sql.save(warehouse)

        retrieved = warehouse_repo_sql.get(10)
        assert retrieved.warehouse_id == 10
        assert retrieved.location == "New Warehouse"

    def test_save_existing_warehouse_updates(self, warehouse_repo_sql):
        """Test that save updates existing warehouse."""
        # Create initial
        warehouse = Warehouse(warehouse_id=20, location="Original Location")
        warehouse_repo_sql.save(warehouse)

        # Update location
        warehouse.location = "Updated Location"
        warehouse_repo_sql.save(warehouse)

        retrieved = warehouse_repo_sql.get(20)
        assert retrieved.location == "Updated Location"

    def test_get_nonexistent_warehouse(self, warehouse_repo_sql):
        """Test getting non-existent warehouse returns None."""
        result = warehouse_repo_sql.get(9999)
        assert result is None

    def test_get_all_warehouses(self, warehouse_repo_sql):
        """Test retrieving all warehouses."""
        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse B")
        warehouse3 = Warehouse(warehouse_id=3, location="Warehouse C")

        warehouse_repo_sql.save(warehouse1)
        warehouse_repo_sql.save(warehouse2)
        warehouse_repo_sql.save(warehouse3)

        all_warehouses = warehouse_repo_sql.get_all()
        assert len(all_warehouses) == 3
        assert 1 in all_warehouses
        assert 2 in all_warehouses
        assert 3 in all_warehouses

    def test_delete_warehouse(self, warehouse_repo_sql):
        """Test deleting a warehouse."""
        warehouse = Warehouse(warehouse_id=100, location="To Delete")
        warehouse_repo_sql.save(warehouse)

        warehouse_repo_sql.delete(100)
        assert warehouse_repo_sql.get(100) is None

    def test_delete_nonexistent_warehouse(self, warehouse_repo_sql):
        """Test deleting non-existent warehouse doesn't raise error."""
        warehouse_repo_sql.delete(9999)  # Should not raise

    def test_delete_warehouse_with_inventory_cascades(
        self, warehouse_repo_sql, product_repo_sql
    ):
        """Test that deleting warehouse with inventory CASCADE DELETES the inventory."""
        # Create product first
        product = Product(product_id=1, name="Test Product", price=100.0)
        product_repo_sql.save(product)

        # Create warehouse
        warehouse = Warehouse(warehouse_id=5, location="Test Warehouse")
        warehouse_repo_sql.save(warehouse)

        # Add inventory to warehouse
        warehouse_repo_sql.add_product_to_warehouse(5, 1, 10)

        # Verify inventory exists
        inventory = warehouse_repo_sql.get_warehouse_inventory(5)
        assert len(inventory) == 1
        assert inventory[0].quantity == 10

        # Delete warehouse - should CASCADE DELETE inventory
        warehouse_repo_sql.delete(5)

        # Verify warehouse is gone
        assert warehouse_repo_sql.get(5) is None

        # Verify inventory is also deleted (no orphans)
        # Since warehouse doesn't exist, inventory should return empty
        inventory_after = warehouse_repo_sql.get_warehouse_inventory(5)
        assert len(inventory_after) == 0

    def test_add_product_to_warehouse(self, warehouse_repo_sql, product_repo_sql):
        """Test adding product to warehouse."""
        # Create product and warehouse
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Add product to warehouse
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 5)

        inventory = warehouse_repo_sql.get_warehouse_inventory(1)
        assert len(inventory) == 1
        assert inventory[0].product_id == 1
        assert inventory[0].quantity == 5

    def test_add_product_to_warehouse_multiple_times(
        self, warehouse_repo_sql, product_repo_sql
    ):
        """Test adding same product multiple times accumulates quantity."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Add product multiple times
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 5)
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 3)
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 2)

        inventory = warehouse_repo_sql.get_warehouse_inventory(1)
        assert len(inventory) == 1
        assert inventory[0].quantity == 10  # 5 + 3 + 2

    def test_add_product_to_nonexistent_warehouse_raises_error(
        self, warehouse_repo_sql, product_repo_sql
    ):
        """Test adding product to non-existent warehouse raises error."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        with pytest.raises(WarehouseNotFoundError):
            warehouse_repo_sql.add_product_to_warehouse(9999, 1, 5)

    def test_remove_product_from_warehouse(self, warehouse_repo_sql, product_repo_sql):
        """Test removing product from warehouse."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Add then remove
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 10)
        warehouse_repo_sql.remove_product_from_warehouse(1, 1, 3)

        inventory = warehouse_repo_sql.get_warehouse_inventory(1)
        assert len(inventory) == 1
        assert inventory[0].quantity == 7

    def test_remove_all_product_deletes_inventory_row(
        self, warehouse_repo_sql, product_repo_sql
    ):
        """Test that removing all quantity deletes the inventory row."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Add and remove all
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 5)
        warehouse_repo_sql.remove_product_from_warehouse(1, 1, 5)

        inventory = warehouse_repo_sql.get_warehouse_inventory(1)
        assert len(inventory) == 0

    def test_remove_product_insufficient_stock_raises_error(
        self, warehouse_repo_sql, product_repo_sql
    ):
        """Test removing more than available raises error."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        warehouse_repo_sql.add_product_to_warehouse(1, 1, 5)

        with pytest.raises(InsufficientStockError):
            warehouse_repo_sql.remove_product_from_warehouse(1, 1, 10)

    def test_remove_product_from_nonexistent_warehouse_raises_error(
        self, warehouse_repo_sql, product_repo_sql
    ):
        """Test removing product from non-existent warehouse raises error."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        with pytest.raises(WarehouseNotFoundError):
            warehouse_repo_sql.remove_product_from_warehouse(9999, 1, 5)

    def test_get_warehouse_inventory_empty(self, warehouse_repo_sql):
        """Test getting inventory for warehouse with no products."""
        warehouse = Warehouse(warehouse_id=1, location="Empty Warehouse")
        warehouse_repo_sql.save(warehouse)

        inventory = warehouse_repo_sql.get_warehouse_inventory(1)
        assert len(inventory) == 0

    def test_get_warehouse_inventory_multiple_products(
        self, warehouse_repo_sql, product_repo_sql
    ):
        """Test getting inventory with multiple products."""
        # Create products
        product1 = Product(product_id=1, name="Product 1", price=10.0)
        product2 = Product(product_id=2, name="Product 2", price=20.0)
        product3 = Product(product_id=3, name="Product 3", price=30.0)
        product_repo_sql.save(product1)
        product_repo_sql.save(product2)
        product_repo_sql.save(product3)

        # Create warehouse
        warehouse = Warehouse(warehouse_id=1, location="Multi-Product Warehouse")
        warehouse_repo_sql.save(warehouse)

        # Add multiple products
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 5)
        warehouse_repo_sql.add_product_to_warehouse(1, 2, 10)
        warehouse_repo_sql.add_product_to_warehouse(1, 3, 15)

        inventory = warehouse_repo_sql.get_warehouse_inventory(1)
        assert len(inventory) == 3

        # Check quantities
        quantities = {item.product_id: item.quantity for item in inventory}
        assert quantities[1] == 5
        assert quantities[2] == 10
        assert quantities[3] == 15

    def test_get_warehouse_inventory_nonexistent_warehouse(self, warehouse_repo_sql):
        """Test getting inventory for non-existent warehouse returns empty list."""
        inventory = warehouse_repo_sql.get_warehouse_inventory(9999)
        assert inventory == []

    def test_unique_constraint_warehouse_product(
        self, warehouse_repo_sql, product_repo_sql, test_session
    ):
        """Test that warehouse_id + product_id is unique (can't insert duplicate)."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Add product to warehouse using the repository method (which handles updates)
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 5)

        # Adding again should update, not fail with constraint error
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 3)

        inventory = warehouse_repo_sql.get_warehouse_inventory(1)
        assert len(inventory) == 1
        assert inventory[0].quantity == 8  # Should be accumulated
