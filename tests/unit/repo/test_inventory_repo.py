"""
Unit tests for InventoryRepo.
"""

import pytest
from app.infrastructure.persistence.repositories.inventory_repo import InventoryRepo
from app.domain.entities.inventory import InventoryItem
from app.domain.exceptions import (
    InvalidQuantityError,
    InsufficientStockError,
)


class TestInventoryRepo:
    """Test cases for InventoryRepo."""

    @pytest.fixture(autouse=True)
    def setup(self, test_session):
        """Set up test fixtures."""
        self.repo = InventoryRepo(test_session)

    def test_save_and_get_quantity(self):
        """Test saving and getting quantity of an inventory item."""
        item = InventoryItem(product_id=1, quantity=10)
        self.repo.save(item)

        quantity = self.repo.get_quantity(1)
        assert quantity == 10

    def test_get_quantity_nonexistent_product(self):
        """Test getting quantity of nonexistent product returns 0."""
        quantity = self.repo.get_quantity(999)
        assert quantity == 0

    def test_add_quantity_new_product(self):
        """Test adding quantity for a new product."""
        self.repo.add_quantity(1, 5)

        assert self.repo.get_quantity(1) == 5

    def test_add_quantity_existing_product(self):
        """Test adding quantity to existing product."""
        self.repo.add_quantity(1, 5)
        self.repo.add_quantity(1, 3)

        assert self.repo.get_quantity(1) == 8

    def test_add_quantity_negative_to_new_product(self):
        """Test adding negative quantity to new product raises InvalidQuantityError."""
        with pytest.raises(
            InvalidQuantityError, match="Cannot start with negative inventory for 1"
        ):
            self.repo.add_quantity(1, -5)

    def test_add_quantity_zero_to_new_product(self):
        """Test adding zero quantity to new product creates item with zero quantity."""
        self.repo.add_quantity(1, 0)

        assert self.repo.get_quantity(1) == 0

    def test_add_quantity_negative_to_existing_product(self):
        """Test adding negative quantity to existing product raises InvalidQuantityError."""
        self.repo.add_quantity(1, 10)

        with pytest.raises(InvalidQuantityError, match="Cannot add negative quantity"):
            self.repo.add_quantity(1, -3)

    def test_get_all_inventory_items(self):
        """Test getting all inventory items."""
        self.repo.add_quantity(1, 10)
        self.repo.add_quantity(2, 20)
        self.repo.add_quantity(3, 5)

        items = self.repo.get_all()
        assert len(items) == 3

        # Check items are returned
        product_ids = [item.product_id for item in items]
        assert 1 in product_ids
        assert 2 in product_ids
        assert 3 in product_ids

    def test_get_all_empty_inventory(self):
        """Test getting all items when inventory is empty."""
        items = self.repo.get_all()
        assert items == []

    def test_delete_existing_empty_item(self):
        """Test deleting an existing item with zero quantity."""
        self.repo.add_quantity(1, 0)

        self.repo.delete(1)
        assert self.repo.get_quantity(1) == 0

    def test_delete_existing_nonempty_item(self):
        """Test deleting an item with non-zero quantity raises InvalidQuantityError."""
        self.repo.add_quantity(1, 10)

        with pytest.raises(
            InvalidQuantityError, match="Cannot delete item with non-zero quantity"
        ):
            self.repo.delete(1)

    def test_delete_nonexistent_item(self):
        """Test deleting nonexistent item is a no-op."""
        # Should not raise an exception
        self.repo.delete(999)

    def test_remove_quantity_existing_product(self):
        """Test removing quantity from existing product."""
        self.repo.add_quantity(1, 10)
        self.repo.remove_quantity(1, 3)

        assert self.repo.get_quantity(1) == 7

    def test_remove_quantity_nonexistent_product(self):
        """Test removing quantity from nonexistent product raises KeyError."""
        with pytest.raises(KeyError, match="Product 999 not found in inventory"):
            self.repo.remove_quantity(999, 5)

    def test_remove_quantity_more_than_available(self):
        """Test removing more quantity than available raises InsufficientStockError."""
        self.repo.add_quantity(1, 5)

        with pytest.raises(
            InsufficientStockError,
            match="Insufficient stock. Available: 5, Requested: 10",
        ):
            self.repo.remove_quantity(1, 10)

    def test_remove_quantity_zero(self):
        """Test removing zero quantity."""
        self.repo.add_quantity(1, 10)
        self.repo.remove_quantity(1, 0)

        assert self.repo.get_quantity(1) == 10

    def test_inventory_item_operations(self):
        """Test that inventory operations properly use InventoryItem methods."""  # Add initial quantity
        self.repo.add_quantity(1, 10)

        # Get the item and verify quantity
        quantity = self.repo.get_quantity(1)
        assert quantity == 10

        # Add more quantity
        self.repo.add_quantity(1, 5)
        assert self.repo.get_quantity(1) == 15

    def test_multiple_products_operations(self):
        """Test operations with multiple products."""
        # Add multiple products
        self.repo.add_quantity(1, 10)
        self.repo.add_quantity(2, 20)
        self.repo.add_quantity(3, 30)

        assert self.repo.get_quantity(1) == 10
        assert self.repo.get_quantity(2) == 20
        assert self.repo.get_quantity(3) == 30

        # Modify quantities
        self.repo.add_quantity(1, 5)
        self.repo.remove_quantity(2, 5)
        # Cannot add negative quantity, so we remove instead
        self.repo.remove_quantity(3, 10)

        assert self.repo.get_quantity(1) == 15
        assert self.repo.get_quantity(2) == 15
        assert self.repo.get_quantity(3) == 20

        # Delete one product
        self.repo.remove_quantity(1, 15)  # Make it zero
        self.repo.delete(1)

        assert self.repo.get_quantity(1) == 0
        assert self.repo.get_quantity(2) == 15
        assert self.repo.get_quantity(3) == 20
