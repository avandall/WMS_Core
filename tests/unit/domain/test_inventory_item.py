"""
Unit tests for InventoryItem domain entity.
"""

import pytest
from app.domain.entities.inventory import InventoryItem
from app.domain.exceptions import (
    ValidationError,
    InvalidQuantityError,
    InvalidIDError,
    InsufficientStockError,
)


class TestInventoryItem:
    """Test cases for InventoryItem domain entity."""

    def test_inventory_item_creation_valid(self):
        """Test creating an inventory item with valid data."""
        item = InventoryItem(product_id=1, quantity=10)

        assert item.product_id == 1
        assert item.quantity == 10

    def test_inventory_item_creation_zero_quantity(self):
        """Test creating an inventory item with zero quantity."""
        item = InventoryItem(product_id=2, quantity=0)

        assert item.product_id == 2
        assert item.quantity == 0

    @pytest.mark.parametrize("invalid_id", [0, -1, "1", None, 1.5])
    def test_inventory_item_invalid_product_id(self, invalid_id):
        """Test creating inventory item with invalid product ID."""
        with pytest.raises(
            InvalidIDError, match="product_id must be a positive integer"
        ):
            InventoryItem(product_id=invalid_id, quantity=5)

    @pytest.mark.parametrize("invalid_quantity", [-1, -5, "10", None, 1.5])
    def test_inventory_item_invalid_quantity(self, invalid_quantity):
        """Test creating inventory item with invalid quantity."""
        with pytest.raises(
            InvalidQuantityError, match="quantity must be a non-negative integer"
        ):
            InventoryItem(product_id=1, quantity=invalid_quantity)

    def test_add_quantity_valid(self):
        """Test adding quantity to inventory item."""
        item = InventoryItem(product_id=1, quantity=10)
        item.add_quantity(5)

        assert item.quantity == 15

    def test_add_quantity_zero(self):
        """Test adding zero quantity."""
        item = InventoryItem(product_id=1, quantity=10)
        item.add_quantity(0)

        assert item.quantity == 10

    def test_add_quantity_invalid(self):
        """Test adding invalid quantity."""
        item = InventoryItem(product_id=1, quantity=10)

        with pytest.raises(InvalidQuantityError, match="amount must be non-negative"):
            item.add_quantity(-5)

    def test_remove_quantity_valid(self):
        """Test removing quantity from inventory item."""
        item = InventoryItem(product_id=1, quantity=10)
        item.remove_quantity(3)

        assert item.quantity == 7

    def test_remove_quantity_all(self):
        """Test removing all quantity."""
        item = InventoryItem(product_id=1, quantity=5)
        item.remove_quantity(5)

        assert item.quantity == 0

    def test_remove_quantity_insufficient_stock(self):
        """Test removing more quantity than available."""
        item = InventoryItem(product_id=1, quantity=5)

        with pytest.raises(InsufficientStockError, match="Insufficient stock"):
            item.remove_quantity(10)

    def test_remove_quantity_invalid(self):
        """Test removing invalid quantity."""
        item = InventoryItem(product_id=1, quantity=10)

        with pytest.raises(InvalidQuantityError, match="amount must be non-negative"):
            item.remove_quantity(-3)

    def test_has_sufficient_stock(self):
        """Test checking sufficient stock."""
        item = InventoryItem(product_id=1, quantity=10)

        assert item.has_sufficient_stock(5) is True
        assert item.has_sufficient_stock(10) is True
        assert item.has_sufficient_stock(15) is False
        assert item.has_sufficient_stock(0) is True

    def test_is_empty(self):
        """Test checking if inventory item is empty."""
        empty_item = InventoryItem(product_id=1, quantity=0)
        non_empty_item = InventoryItem(product_id=2, quantity=5)

        assert empty_item.is_empty() is True
        assert non_empty_item.is_empty() is False

    def test_string_representation(self):
        """Test string representation of inventory item."""
        item = InventoryItem(product_id=1, quantity=10)

        expected = "InventoryItem(product_id=1, quantity=10)"
        assert str(item) == expected
        assert repr(item) == expected

    def test_equality(self):
        """Test inventory item equality based on product ID."""
        item1 = InventoryItem(product_id=1, quantity=10)
        item2 = InventoryItem(product_id=1, quantity=20)
        item3 = InventoryItem(product_id=2, quantity=10)

        assert item1 == item2
        assert item1 != item3
        assert item1 != "not an item"

    def test_hash(self):
        """Test inventory item hash based on product ID."""
        item1 = InventoryItem(product_id=1, quantity=10)
        item2 = InventoryItem(product_id=1, quantity=20)
        item3 = InventoryItem(product_id=2, quantity=10)

        assert hash(item1) == hash(item2)
        assert hash(item1) != hash(item3)

        # Test that equal items have equal hashes
        assert hash(item1) == hash(item2)
