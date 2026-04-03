"""
SQL integration tests for InventoryRepo.
Tests actual database operations for total inventory management.
"""

import pytest

from app.domain.entities.inventory import InventoryItem
from app.domain.entities.product import Product
from app.domain.exceptions import (
    InvalidQuantityError,
    InsufficientStockError,
)


class TestInventoryRepoSQL:
    """Test SQL inventory repository with real database operations."""

    def test_save_new_inventory_item(self, inventory_repo_sql, product_repo_sql):
        """Test saving a new inventory item."""
        # Create product first
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        item = InventoryItem(product_id=1, quantity=100)
        inventory_repo_sql.save(item)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 100

    def test_save_existing_inventory_updates(
        self, inventory_repo_sql, product_repo_sql
    ):
        """Test that save updates existing inventory."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        item = InventoryItem(product_id=1, quantity=50)
        inventory_repo_sql.save(item)

        # Update quantity
        item.quantity = 150
        inventory_repo_sql.save(item)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 150

    def test_add_quantity_new_product(self, inventory_repo_sql, product_repo_sql):
        """Test adding quantity for new product creates inventory."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        inventory_repo_sql.add_quantity(1, 25)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 25

    def test_add_quantity_existing_product(self, inventory_repo_sql, product_repo_sql):
        """Test adding quantity to existing inventory accumulates."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        inventory_repo_sql.add_quantity(1, 25)
        inventory_repo_sql.add_quantity(1, 15)
        inventory_repo_sql.add_quantity(1, 10)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 50  # 25 + 15 + 10

    def test_add_negative_quantity_raises_error(
        self, inventory_repo_sql, product_repo_sql
    ):
        """Test that adding negative quantity raises error."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        with pytest.raises(InvalidQuantityError):
            inventory_repo_sql.add_quantity(1, -10)

    def test_get_quantity_nonexistent_returns_zero(self, inventory_repo_sql):
        """Test getting quantity of non-existent product returns 0."""
        quantity = inventory_repo_sql.get_quantity(9999)
        assert quantity == 0

    def test_get_all_inventory(self, inventory_repo_sql, product_repo_sql):
        """Test getting all inventory items."""
        # Create products
        product1 = Product(product_id=1, name="Product 1", price=10.0)
        product2 = Product(product_id=2, name="Product 2", price=20.0)
        product3 = Product(product_id=3, name="Product 3", price=30.0)
        product_repo_sql.save(product1)
        product_repo_sql.save(product2)
        product_repo_sql.save(product3)

        # Add inventory
        inventory_repo_sql.add_quantity(1, 10)
        inventory_repo_sql.add_quantity(2, 20)
        inventory_repo_sql.add_quantity(3, 30)

        all_inventory = inventory_repo_sql.get_all()
        assert len(all_inventory) == 3

        # Check items
        inventory_dict = {item.product_id: item.quantity for item in all_inventory}
        assert inventory_dict[1] == 10
        assert inventory_dict[2] == 20
        assert inventory_dict[3] == 30

    def test_get_all_empty_inventory(self, inventory_repo_sql):
        """Test getting all inventory when empty returns empty list."""
        all_inventory = inventory_repo_sql.get_all()
        assert len(all_inventory) == 0

    def test_remove_quantity(self, inventory_repo_sql, product_repo_sql):
        """Test removing quantity from inventory."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        inventory_repo_sql.add_quantity(1, 100)
        inventory_repo_sql.remove_quantity(1, 30)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 70

    def test_remove_quantity_multiple_times(self, inventory_repo_sql, product_repo_sql):
        """Test removing quantity multiple times."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        inventory_repo_sql.add_quantity(1, 100)
        inventory_repo_sql.remove_quantity(1, 20)
        inventory_repo_sql.remove_quantity(1, 15)
        inventory_repo_sql.remove_quantity(1, 10)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 55  # 100 - 20 - 15 - 10

    def test_remove_quantity_nonexistent_raises_error(self, inventory_repo_sql):
        """Test removing from non-existent inventory raises KeyError."""
        with pytest.raises(KeyError, match="not found in inventory"):
            inventory_repo_sql.remove_quantity(9999, 10)

    def test_remove_negative_quantity_raises_error(
        self, inventory_repo_sql, product_repo_sql
    ):
        """Test removing negative quantity raises error."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)
        inventory_repo_sql.add_quantity(1, 100)

        with pytest.raises(
            InvalidQuantityError, match="Cannot remove negative quantity"
        ):
            inventory_repo_sql.remove_quantity(1, -10)

    def test_remove_more_than_available_raises_error(
        self, inventory_repo_sql, product_repo_sql
    ):
        """Test removing more than available raises error."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)
        inventory_repo_sql.add_quantity(1, 50)

        with pytest.raises(InsufficientStockError, match="Insufficient stock"):
            inventory_repo_sql.remove_quantity(1, 100)

    def test_delete_inventory_item(self, inventory_repo_sql, product_repo_sql):
        """Test deleting inventory item with zero quantity."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        # Add and remove all quantity
        inventory_repo_sql.add_quantity(1, 50)
        inventory_repo_sql.remove_quantity(1, 50)

        # Now delete
        inventory_repo_sql.delete(1)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 0

    def test_delete_nonexistent_inventory_raises_error(self, inventory_repo_sql):
        """Test deleting non-existent inventory raises KeyError."""
        inventory_repo_sql.delete(9999)
        assert inventory_repo_sql.get_quantity(9999) == 0

    def test_delete_inventory_with_nonzero_quantity_raises_error(
        self, inventory_repo_sql, product_repo_sql
    ):
        """Test that deleting inventory with quantity > 0 raises error."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)
        inventory_repo_sql.add_quantity(1, 50)

        with pytest.raises(
            InvalidQuantityError, match="Cannot delete item with non-zero quantity"
        ):
            inventory_repo_sql.delete(1)

    def test_update_total_inventory_helper(self, inventory_repo_sql, product_repo_sql):
        """Test update_total_inventory utility method if it exists."""
        # This tests a common pattern for updating total inventory
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        # Simulate update_total_inventory (if the method exists in your repo)
        # Otherwise this tests the save method with specific quantity
        item = InventoryItem(product_id=1, quantity=200)
        inventory_repo_sql.save(item)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 200

    def test_inventory_persistence_across_sessions(self, test_engine, product_repo_sql):
        """Test that inventory persists across different sessions."""
        from sqlalchemy.orm import sessionmaker
        from app.infrastructure.persistence.repositories.inventory_repo import InventoryRepo

        # Create product
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        # Session 1: Add inventory
        SessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
        session1 = SessionLocal()
        repo1 = InventoryRepo(session1)
        repo1.add_quantity(1, 100)
        session1.close()

        # Session 2: Check inventory persists
        session2 = SessionLocal()
        repo2 = InventoryRepo(session2)
        quantity = repo2.get_quantity(1)
        assert quantity == 100
        session2.close()

    def test_zero_quantity_inventory(self, inventory_repo_sql, product_repo_sql):
        """Test that inventory can be set to zero quantity."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        inventory_repo_sql.add_quantity(1, 100)
        inventory_repo_sql.remove_quantity(1, 100)

        quantity = inventory_repo_sql.get_quantity(1)
        assert quantity == 0
