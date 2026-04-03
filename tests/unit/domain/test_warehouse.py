"""
Unit tests for Warehouse domain entity.
"""

import pytest
from app.domain.entities.warehouse import Warehouse, WarehouseManager
from app.domain.entities.inventory import InventoryItem
from app.domain.exceptions import (
    ValidationError,
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    InvalidQuantityError,
    WarehouseNotFoundError,
    ProductNotFoundError,
    InsufficientStockError,
    InvalidIDError,
)


class TestWarehouse:
    """Test cases for Warehouse domain entity."""

    def test_warehouse_creation_valid(self):
        """Test creating a warehouse with valid data."""
        warehouse = Warehouse(warehouse_id=1, location="Main Warehouse")

        assert warehouse.warehouse_id == 1
        assert warehouse.location == "Main Warehouse"
        assert warehouse.inventory == []

    def test_warehouse_creation_with_inventory(self):
        """Test creating a warehouse with initial inventory."""
        inventory = [
            InventoryItem(product_id=1, quantity=10),
            InventoryItem(product_id=2, quantity=5),
        ]
        warehouse = Warehouse(
            warehouse_id=1, location="Main Warehouse", inventory=inventory
        )

        assert warehouse.warehouse_id == 1
        assert warehouse.location == "Main Warehouse"
        assert len(warehouse.inventory) == 2
        assert warehouse.inventory[0].product_id == 1
        assert warehouse.inventory[0].quantity == 10

    @pytest.mark.parametrize("invalid_id", [0, -1, "1", None, 1.5])
    def test_warehouse_invalid_id(self, invalid_id):
        """Test creating warehouse with invalid ID."""
        with pytest.raises(
            InvalidIDError, match="warehouse_id must be a positive integer"
        ):
            Warehouse(warehouse_id=invalid_id, location="Test")

    @pytest.mark.parametrize("invalid_location", ["", "   ", None, "x" * 201])
    def test_warehouse_invalid_location(self, invalid_location):
        """Test creating warehouse with invalid location."""
        with pytest.raises(ValidationError):
            Warehouse(warehouse_id=1, location=invalid_location)

    def test_add_product_new(self):
        """Test adding a new product to warehouse."""
        warehouse = Warehouse(warehouse_id=1, location="Test")

        warehouse.add_product(product_id=1, quantity=10)

        assert len(warehouse.inventory) == 1
        assert warehouse.inventory[0].product_id == 1
        assert warehouse.inventory[0].quantity == 10

    def test_add_product_existing(self):
        """Test adding quantity to existing product."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=10)

        warehouse.add_product(product_id=1, quantity=5)

        assert len(warehouse.inventory) == 1
        assert warehouse.inventory[0].product_id == 1
        assert warehouse.inventory[0].quantity == 15

    def test_add_product_invalid_quantity(self):
        """Test adding product with invalid quantity."""
        warehouse = Warehouse(warehouse_id=1, location="Test")

        with pytest.raises(
            InvalidQuantityError, match="quantity must be a positive integer"
        ):
            warehouse.add_product(product_id=1, quantity=0)

        with pytest.raises(
            InvalidQuantityError, match="quantity must be a positive integer"
        ):
            warehouse.add_product(product_id=1, quantity=-5)

    def test_remove_product_existing(self):
        """Test removing product from warehouse."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=10)

        warehouse.remove_product(product_id=1, quantity=3)

        assert len(warehouse.inventory) == 1
        assert warehouse.inventory[0].quantity == 7

    def test_remove_product_all_quantity(self):
        """Test removing all quantity of a product."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=5)

        warehouse.remove_product(product_id=1, quantity=5)

        assert len(warehouse.inventory) == 0

    def test_remove_product_not_found(self):
        """Test removing product that doesn't exist."""
        warehouse = Warehouse(warehouse_id=1, location="Test")

        with pytest.raises(
            EntityNotFoundError, match="Product 1 not found in warehouse 1"
        ):
            warehouse.remove_product(product_id=1, quantity=5)

    def test_remove_product_insufficient_stock(self):
        """Test removing more quantity than available."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=5)

        with pytest.raises(InsufficientStockError, match="Insufficient stock"):
            warehouse.remove_product(product_id=1, quantity=10)

    def test_remove_product_invalid_quantity(self):
        """Test removing product with invalid quantity."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=10)

        with pytest.raises(
            InvalidQuantityError, match="quantity must be a positive integer"
        ):
            warehouse.remove_product(product_id=1, quantity=0)

    def test_get_product_quantity(self):
        """Test getting product quantity."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=10)
        warehouse.add_product(product_id=2, quantity=5)

        assert warehouse.get_product_quantity(product_id=1) == 10
        assert warehouse.get_product_quantity(product_id=2) == 5
        assert warehouse.get_product_quantity(product_id=3) == 0

    def test_has_product(self):
        """Test checking if warehouse has product."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=10)

        assert warehouse.has_product(product_id=1) is True
        assert warehouse.has_product(product_id=2) is False

    def test_get_inventory_value(self):
        """Test calculating inventory value."""
        from app.domain.entities.product import Product

        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=2)
        warehouse.add_product(product_id=2, quantity=3)

        products = {
            1: Product(product_id=1, name="Product 1", price=10.0),
            2: Product(product_id=2, name="Product 2", price=5.0),
        }

        total_value = warehouse.get_inventory_value(products)
        assert total_value == 35.0  # (2*10) + (3*5)

    def test_get_inventory_summary(self):
        """Test getting inventory summary."""
        warehouse = Warehouse(warehouse_id=1, location="Test Warehouse")
        warehouse.add_product(product_id=1, quantity=10)
        warehouse.add_product(product_id=2, quantity=5)

        summary = warehouse.get_inventory_summary()

        assert summary["warehouse_id"] == 1
        assert summary["location"] == "Test Warehouse"
        assert summary["total_products"] == 2
        assert summary["total_items"] == 15

    def test_transfer_product_to(self):
        """Test transferring product to another warehouse."""
        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse 1")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse 2")

        warehouse1.add_product(product_id=1, quantity=10)
        warehouse1.transfer_product_to(warehouse2, product_id=1, quantity=3)

        assert warehouse1.get_product_quantity(product_id=1) == 7
        assert warehouse2.get_product_quantity(product_id=1) == 3

    def test_transfer_product_same_warehouse(self):
        """Test transferring product to the same warehouse."""
        warehouse = Warehouse(warehouse_id=1, location="Test")
        warehouse.add_product(product_id=1, quantity=10)

        with pytest.raises(
            BusinessRuleViolationError, match="Cannot transfer to the same warehouse"
        ):
            warehouse.transfer_product_to(warehouse, product_id=1, quantity=5)

    def test_transfer_product_insufficient_stock(self):
        """Test transferring more than available stock."""
        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse 1")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse 2")

        warehouse1.add_product(product_id=1, quantity=5)

        with pytest.raises(InsufficientStockError):
            warehouse1.transfer_product_to(warehouse2, product_id=1, quantity=10)

    def test_update_location_valid(self):
        """Test updating warehouse location."""
        warehouse = Warehouse(warehouse_id=1, location="Old Location")
        warehouse.update_location("New Location")

        assert warehouse.location == "New Location"

    def test_update_location_invalid(self):
        """Test updating warehouse location with invalid value."""
        warehouse = Warehouse(warehouse_id=1, location="Old Location")

        with pytest.raises(ValidationError):
            warehouse.update_location("")

    def test_string_representation(self):
        """Test string representation of warehouse."""
        warehouse = Warehouse(warehouse_id=1, location="Test Warehouse")
        warehouse.add_product(product_id=1, quantity=5)

        expected = "Warehouse(id=1, location='Test Warehouse', products=1)"
        assert str(warehouse) == expected
        assert repr(warehouse) == expected

    def test_equality(self):
        """Test warehouse equality based on ID."""
        warehouse1 = Warehouse(warehouse_id=1, location="Location A")
        warehouse2 = Warehouse(warehouse_id=1, location="Location B")
        warehouse3 = Warehouse(warehouse_id=2, location="Location A")

        assert warehouse1 == warehouse2
        assert warehouse1 != warehouse3
        assert warehouse1 != "not a warehouse"

    def test_hash(self):
        """Test warehouse hash based on ID."""
        warehouse1 = Warehouse(warehouse_id=1, location="Location A")
        warehouse2 = Warehouse(warehouse_id=1, location="Location B")
        warehouse3 = Warehouse(warehouse_id=2, location="Location A")

        assert hash(warehouse1) == hash(warehouse2)
        assert hash(warehouse1) != hash(warehouse3)


class TestWarehouseManager:
    """Test cases for WarehouseManager."""

    def test_add_warehouse(self):
        """Test adding a warehouse."""
        manager = WarehouseManager()
        warehouse = Warehouse(warehouse_id=1, location="Test")

        manager.add_warehouse(warehouse)

        assert len(manager) == 1
        assert manager.get_warehouse(1) == warehouse

    def test_add_duplicate_warehouse(self):
        """Test adding a warehouse that already exists."""
        manager = WarehouseManager()
        warehouse1 = Warehouse(warehouse_id=1, location="Test 1")
        warehouse2 = Warehouse(warehouse_id=1, location="Test 2")

        manager.add_warehouse(warehouse1)

        with pytest.raises(
            EntityAlreadyExistsError, match="Warehouse 1 already exists"
        ):
            manager.add_warehouse(warehouse2)

    def test_get_warehouse_not_found(self):
        """Test getting a warehouse that doesn't exist."""
        manager = WarehouseManager()

        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            manager.get_warehouse(1)

    def test_remove_warehouse(self):
        """Test removing a warehouse."""
        manager = WarehouseManager()
        warehouse = Warehouse(warehouse_id=1, location="Test")

        manager.add_warehouse(warehouse)
        assert len(manager) == 1

        manager.remove_warehouse(1)
        assert len(manager) == 0

        with pytest.raises(WarehouseNotFoundError):
            manager.get_warehouse(1)

    def test_remove_warehouse_not_found(self):
        """Test removing a warehouse that doesn't exist."""
        manager = WarehouseManager()

        with pytest.raises(WarehouseNotFoundError, match="Warehouse 1 not found"):
            manager.remove_warehouse(1)

    def test_get_all_warehouses(self):
        """Test getting all warehouses."""
        manager = WarehouseManager()
        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse 1")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse 2")

        manager.add_warehouse(warehouse1)
        manager.add_warehouse(warehouse2)

        all_warehouses = manager.get_all_warehouses()
        assert len(all_warehouses) == 2
        assert warehouse1 in all_warehouses
        assert warehouse2 in all_warehouses

    def test_find_warehouses_with_product(self):
        """Test finding warehouses that contain a product."""
        manager = WarehouseManager()
        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse 1")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse 2")

        warehouse1.add_product(product_id=1, quantity=10)
        warehouse2.add_product(product_id=1, quantity=5)
        warehouse2.add_product(product_id=2, quantity=3)

        manager.add_warehouse(warehouse1)
        manager.add_warehouse(warehouse2)

        warehouses_with_product_1 = manager.find_warehouses_with_product(product_id=1)
        warehouses_with_product_2 = manager.find_warehouses_with_product(product_id=2)
        warehouses_with_product_3 = manager.find_warehouses_with_product(product_id=3)

        assert len(warehouses_with_product_1) == 2
        assert len(warehouses_with_product_2) == 1
        assert len(warehouses_with_product_3) == 0

    def test_get_total_product_quantity(self):
        """Test getting total quantity of a product across all warehouses."""
        manager = WarehouseManager()
        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse 1")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse 2")

        warehouse1.add_product(product_id=1, quantity=10)
        warehouse2.add_product(product_id=1, quantity=5)
        warehouse2.add_product(product_id=2, quantity=3)

        manager.add_warehouse(warehouse1)
        manager.add_warehouse(warehouse2)

        assert manager.get_total_product_quantity(product_id=1) == 15
        assert manager.get_total_product_quantity(product_id=2) == 3
        assert manager.get_total_product_quantity(product_id=3) == 0

    def test_string_representation(self):
        """Test string representation of warehouse manager."""
        manager = WarehouseManager()
        manager.add_warehouse(Warehouse(warehouse_id=1, location="Test"))
        manager.add_warehouse(Warehouse(warehouse_id=2, location="Test"))

        expected = "WarehouseManager(warehouses=2)"
        assert str(manager) == expected
