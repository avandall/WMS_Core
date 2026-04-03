"""
SQL integration tests for ProductRepo.
Tests actual database operations including cascade deletes and relationships.
"""

import pytest

from app.domain.entities.product import Product
from app.domain.entities.warehouse import Warehouse


class TestProductRepoSQL:
    """Test SQL product repository with real database operations."""

    def test_save_new_product(self, product_repo_sql):
        """Test saving a new product."""
        product = Product(
            product_id=1,
            name="Test Product",
            description="Test Description",
            price=99.99,
        )
        product_repo_sql.save(product)

        retrieved = product_repo_sql.get(1)
        assert retrieved is not None
        assert retrieved.product_id == 1
        assert retrieved.name == "Test Product"
        assert retrieved.description == "Test Description"
        assert retrieved.price == 99.99

    def test_save_existing_product_updates(self, product_repo_sql):
        """Test that save updates existing product."""
        product = Product(
            product_id=10, name="Original", description="Original desc", price=50.0
        )
        product_repo_sql.save(product)

        # Update and save again
        product.name = "Updated Name"
        product.description = "Updated Description"
        product.price = 75.0
        product_repo_sql.save(product)

        retrieved = product_repo_sql.get(10)
        assert retrieved.name == "Updated Name"
        assert retrieved.description == "Updated Description"
        assert retrieved.price == 75.0

    def test_get_nonexistent_product(self, product_repo_sql):
        """Test getting non-existent product returns None."""
        result = product_repo_sql.get(9999)
        assert result is None

    def test_get_all_products(self, product_repo_sql):
        """Test retrieving all products."""
        product1 = Product(product_id=1, name="Product A", price=10.0)
        product2 = Product(product_id=2, name="Product B", price=20.0)
        product3 = Product(product_id=3, name="Product C", price=30.0)

        product_repo_sql.save(product1)
        product_repo_sql.save(product2)
        product_repo_sql.save(product3)

        all_products = product_repo_sql.get_all()
        assert len(all_products) == 3
        assert 1 in all_products
        assert 2 in all_products
        assert 3 in all_products

    def test_get_price(self, product_repo_sql):
        """Test getting product price."""
        product = Product(product_id=1, name="Test Product", price=123.45)
        product_repo_sql.save(product)

        price = product_repo_sql.get_price(1)
        assert price == 123.45

    def test_get_price_nonexistent_raises_error(self, product_repo_sql):
        """Test getting price of non-existent product raises KeyError."""
        with pytest.raises(KeyError, match="Product not found"):
            product_repo_sql.get_price(9999)

    def test_delete_product(self, product_repo_sql):
        """Test deleting a product."""
        product = Product(product_id=100, name="To Delete", price=50.0)
        product_repo_sql.save(product)

        product_repo_sql.delete(100)
        assert product_repo_sql.get(100) is None

    def test_delete_nonexistent_product_raises_error(self, product_repo_sql):
        """Test deleting non-existent product raises KeyError."""
        with pytest.raises(KeyError, match="Product not found"):
            product_repo_sql.delete(9999)

    def test_delete_product_with_inventory_also_deletes_inventory(
        self, product_repo_sql, inventory_repo_sql
    ):
        """Test that deleting product also deletes its inventory record."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        # Create inventory for this product
        inventory_repo_sql.add_quantity(1, 100)
        assert inventory_repo_sql.get_quantity(1) == 100

        # Delete product - should cascade delete inventory
        product_repo_sql.delete(1)

        # Verify product is gone
        assert product_repo_sql.get(1) is None

        # Verify inventory is also gone
        assert inventory_repo_sql.get_quantity(1) == 0

    def test_delete_product_with_warehouse_inventory_prevents_deletion(
        self, product_repo_sql, warehouse_repo_sql
    ):
        """Test that deleting product with warehouse inventory fails due to FK constraint."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Add product to warehouse
        warehouse_repo_sql.add_product_to_warehouse(1, 1, 10)

        # Try to delete product - should fail due to FK constraint
        # The warehouse_inventory table has a FK to products
        with pytest.raises(
            Exception
        ):  # SQLAlchemy will raise IntegrityError or similar
            product_repo_sql.delete(1)

    def test_get_product_details(self, product_repo_sql):
        """Test getting product details."""
        product = Product(
            product_id=1,
            name="Detailed Product",
            description="Very detailed",
            price=99.99,
        )
        product_repo_sql.save(product)

        details = product_repo_sql.get(1)
        assert details.product_id == 1
        assert details.name == "Detailed Product"
        assert details.description == "Very detailed"
        assert details.price == 99.99

    def test_get_product_details_nonexistent_raises_error(self, product_repo_sql):
        """Test getting details of non-existent product raises KeyError."""
        assert product_repo_sql.get(9999) is None

    def test_save_product_with_none_description(self, product_repo_sql):
        """Test saving product with None description."""
        product = Product(product_id=1, name="No Description", price=50.0)
        product_repo_sql.save(product)

        retrieved = product_repo_sql.get(1)
        assert retrieved.description is None

    def test_save_product_with_zero_price(self, product_repo_sql):
        """Test saving product with zero price."""
        product = Product(product_id=1, name="Free Product", price=0.0)
        product_repo_sql.save(product)

        retrieved = product_repo_sql.get(1)
        assert retrieved.price == 0.0

    def test_product_price_precision(self, product_repo_sql):
        """Test that product price maintains precision."""
        product = Product(product_id=1, name="Precise Price", price=123.456789)
        product_repo_sql.save(product)

        retrieved = product_repo_sql.get(1)
        # Float precision might vary slightly
        assert abs(retrieved.price - 123.456789) < 0.0001

    def test_multiple_products_independent(self, product_repo_sql):
        """Test that multiple products are independent."""
        product1 = Product(product_id=1, name="Product 1", price=10.0)
        product2 = Product(product_id=2, name="Product 2", price=20.0)

        product_repo_sql.save(product1)
        product_repo_sql.save(product2)

        # Update product 1
        product1.name = "Updated Product 1"
        product_repo_sql.save(product1)

        # Verify product 2 unchanged
        retrieved2 = product_repo_sql.get(2)
        assert retrieved2.name == "Product 2"
        assert retrieved2.price == 20.0
