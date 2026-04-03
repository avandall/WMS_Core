"""
Unit tests for ProductRepo.
"""

import pytest
from app.infrastructure.persistence.repositories.product_repo import ProductRepo
from app.domain.entities.product import Product


class TestProductRepo:
    """Test cases for ProductRepo."""

    @pytest.fixture(autouse=True)
    def setup(self, test_session):
        """Set up test fixtures with SQL session."""
        self.repo = ProductRepo(test_session)

    def test_save_and_get_product(self):
        """Test saving and retrieving a product."""
        product = Product(
            product_id=1,
            name="Test Product",
            price=10.0,
            description="Test description",
        )

        self.repo.save(product)
        retrieved = self.repo.get(1)

        assert retrieved is not None
        assert retrieved.product_id == 1
        assert retrieved.name == "Test Product"
        assert retrieved.price == 10.0

    def test_get_nonexistent_product(self):
        """Test getting a nonexistent product returns None."""
        result = self.repo.get(999)
        assert result is None

    def test_get_price_existing_product(self):
        """Test getting price of existing product."""
        product = Product(product_id=1, name="Test Product", price=15.0)
        self.repo.save(product)

        price = self.repo.get_price(1)
        assert price == 15.0

    def test_get_price_nonexistent_product(self):
        """Test getting price of nonexistent product raises KeyError."""
        with pytest.raises(KeyError, match="Product not found"):
            self.repo.get_price(999)

    def test_delete_existing_product(self):
        """Test deleting an existing product."""
        product = Product(product_id=1, name="Test Product", price=10.0)
        self.repo.save(product)

        self.repo.delete(1)
        assert self.repo.get(1) is None

    def test_delete_nonexistent_product(self):
        """Test deleting a nonexistent product raises KeyError."""
        with pytest.raises(KeyError, match="Product not found"):
            self.repo.delete(999)

    def test_get_product_details_existing(self):
        """Test getting product details for existing product."""
        product = Product(
            product_id=1, name="Test Product", price=10.0, description="Test desc"
        )
        self.repo.save(product)

        retrieved = self.repo.get(1)
        assert retrieved.product_id == 1
        assert retrieved.name == "Test Product"

    def test_get_product_details_nonexistent(self):
        """Test getting product details for nonexistent product returns None."""
        result = self.repo.get(999)
        assert result is None
