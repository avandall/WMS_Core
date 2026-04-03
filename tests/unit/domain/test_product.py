"""
Unit tests for Product domain entity.
"""

import pytest
from app.domain.entities.product import Product
from app.domain.exceptions import (
    ValidationError,
    InvalidIDError,
    InvalidQuantityError,
)


class TestProduct:
    """Test cases for Product domain entity."""

    def test_product_creation_valid(self):
        """Test creating a product with valid data."""
        product = Product(
            product_id=1, name="Test Product", description="A test product", price=29.99
        )

        assert product.product_id == 1
        assert product.name == "Test Product"
        assert product.description == "A test product"
        assert product.price == 29.99

    def test_product_creation_minimal(self):
        """Test creating a product with minimal required data."""
        product = Product(product_id=2, name="Minimal Product")

        assert product.product_id == 2
        assert product.name == "Minimal Product"
        assert product.description is None
        assert product.price == 0.0

    @pytest.mark.parametrize("invalid_id", [0, -1, "1", None, 1.5])
    def test_product_invalid_id(self, invalid_id):
        """Test creating product with invalid ID."""
        with pytest.raises(
            InvalidIDError, match="product_id must be a positive integer"
        ):
            Product(product_id=invalid_id, name="Test")

    @pytest.mark.parametrize("invalid_name", ["", "   ", None, "x" * 101])
    def test_product_invalid_name(self, invalid_name):
        """Test creating product with invalid name."""
        with pytest.raises(ValidationError):
            Product(product_id=1, name=invalid_name)

    @pytest.mark.parametrize("invalid_price", [-1, -0.01, "10", None])
    def test_product_invalid_price(self, invalid_price):
        """Test creating product with invalid price."""
        with pytest.raises(
            InvalidQuantityError, match="price must be a non-negative number"
        ):
            Product(product_id=1, name="Test", price=invalid_price)

    def test_update_price_valid(self):
        """Test updating product price with valid value."""
        product = Product(product_id=1, name="Test", price=10.0)
        product.update_price(25.50)

        assert product.price == 25.50

    def test_update_price_invalid(self):
        """Test updating product price with invalid value."""
        product = Product(product_id=1, name="Test", price=10.0)

        with pytest.raises(InvalidQuantityError):
            product.update_price(-5.0)

    def test_update_name_valid(self):
        """Test updating product name with valid value."""
        product = Product(product_id=1, name="Old Name", price=10.0)
        product.update_name("New Name")

        assert product.name == "New Name"

    def test_update_name_invalid(self):
        """Test updating product name with invalid value."""
        product = Product(product_id=1, name="Old Name", price=10.0)

        with pytest.raises(ValidationError):
            product.update_name("")

    def test_update_description(self):
        """Test updating product description."""
        product = Product(product_id=1, name="Test", description="Old desc")
        product.update_description("New description")

        assert product.description == "New description"

    def test_update_description_none(self):
        """Test updating product description to None."""
        product = Product(product_id=1, name="Test", description="Old desc")
        product.update_description(None)

        assert product.description is None

    def test_calculate_total_value_valid(self):
        """Test calculating total value with valid quantity."""
        product = Product(product_id=1, name="Test", price=10.0)

        assert product.calculate_total_value(5) == 50.0
        assert product.calculate_total_value(0) == 0.0

    def test_calculate_total_value_invalid_quantity(self):
        """Test calculating total value with invalid quantity."""
        product = Product(product_id=1, name="Test", price=10.0)

        with pytest.raises(InvalidQuantityError, match="quantity must be a non-negative integer"):
            product.calculate_total_value(-1)

    def test_string_representation(self):
        """Test string representation of product."""
        product = Product(product_id=1, name="Test Product", price=29.99)

        expected = "Product(id=1, name='Test Product', price=29.99)"
        assert str(product) == expected
        assert repr(product) == expected

    def test_equality(self):
        """Test product equality based on ID."""
        product1 = Product(product_id=1, name="Product A", price=10.0)
        product2 = Product(product_id=1, name="Product B", price=20.0)
        product3 = Product(product_id=2, name="Product A", price=10.0)

        assert product1 == product2
        assert product1 != product3
        assert product1 != "not a product"

    def test_hash(self):
        """Test product hash based on ID."""
        product1 = Product(product_id=1, name="Product A", price=10.0)
        product2 = Product(product_id=1, name="Product B", price=20.0)
        product3 = Product(product_id=2, name="Product A", price=10.0)

        assert hash(product1) == hash(product2)
        assert hash(product1) != hash(product3)

        # Test that equal products have equal hashes
        assert hash(product1) == hash(product2)
