"""
Integration tests for warehouse inventory transfer feature.
Tests the new transfer_all_inventory functionality and delete protection.
"""

import pytest

from app.domain.entities.product import Product
from app.application.services.warehouse_service import WarehouseService
from app.domain.exceptions import ValidationError, WarehouseNotFoundError


@pytest.fixture
def warehouse_service_sql(warehouse_repo_sql, product_repo_sql, inventory_repo_sql):
    """Fixture for warehouse service with SQL repos."""
    return WarehouseService(
        warehouse_repo=warehouse_repo_sql,
        product_repo=product_repo_sql,
        inventory_repo=inventory_repo_sql,
    )


class TestWarehouseTransferIntegration:
    """Test warehouse inventory transfer and deletion protection."""

    def test_transfer_all_inventory_single_product(
        self, warehouse_service_sql, product_repo_sql
    ):
        """Test transferring all inventory with single product."""
        # Create products
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        # Create warehouses
        warehouse1 = warehouse_service_sql.create_warehouse("Warehouse 1")
        warehouse2 = warehouse_service_sql.create_warehouse("Warehouse 2")

        # Add inventory to warehouse 1
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            warehouse1.warehouse_id, 1, 10
        )

        # Transfer all inventory
        transferred = warehouse_service_sql.transfer_all_inventory(
            warehouse1.warehouse_id, warehouse2.warehouse_id
        )

        # Verify transfer
        assert len(transferred) == 1
        assert transferred[0].product_id == 1
        assert transferred[0].quantity == 10

        # Verify source is empty
        source_inventory = warehouse_service_sql.get_warehouse_inventory(
            warehouse1.warehouse_id
        )
        assert len(source_inventory) == 0

        # Verify destination has inventory
        dest_inventory = warehouse_service_sql.get_warehouse_inventory(
            warehouse2.warehouse_id
        )
        assert len(dest_inventory) == 1
        assert dest_inventory[0].product_id == 1
        assert dest_inventory[0].quantity == 10

    def test_transfer_all_inventory_multiple_products(
        self, warehouse_service_sql, product_repo_sql
    ):
        """Test transferring all inventory with multiple products."""
        # Create products
        for i in range(1, 4):
            product = Product(product_id=i, name=f"Product {i}", price=i * 10.0)
            product_repo_sql.save(product)

        # Create warehouses
        warehouse1 = warehouse_service_sql.create_warehouse("Source Warehouse")
        warehouse2 = warehouse_service_sql.create_warehouse("Destination Warehouse")

        # Add inventory to warehouse 1
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            warehouse1.warehouse_id, 1, 5
        )
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            warehouse1.warehouse_id, 2, 10
        )
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            warehouse1.warehouse_id, 3, 15
        )

        # Transfer all
        transferred = warehouse_service_sql.transfer_all_inventory(
            warehouse1.warehouse_id, warehouse2.warehouse_id
        )

        # Verify all products transferred
        assert len(transferred) == 3
        transferred_dict = {item.product_id: item.quantity for item in transferred}
        assert transferred_dict[1] == 5
        assert transferred_dict[2] == 10
        assert transferred_dict[3] == 15

        # Verify source is empty
        source_inventory = warehouse_service_sql.get_warehouse_inventory(
            warehouse1.warehouse_id
        )
        assert len(source_inventory) == 0

    def test_transfer_all_inventory_empty_source(self, warehouse_service_sql):
        """Test transferring from empty warehouse returns empty list."""
        warehouse1 = warehouse_service_sql.create_warehouse("Empty Warehouse")
        warehouse2 = warehouse_service_sql.create_warehouse("Destination Warehouse")

        transferred = warehouse_service_sql.transfer_all_inventory(
            warehouse1.warehouse_id, warehouse2.warehouse_id
        )

        assert len(transferred) == 0

    def test_transfer_all_inventory_same_warehouse_raises_error(
        self, warehouse_service_sql
    ):
        """Test transferring to same warehouse raises error."""
        warehouse = warehouse_service_sql.create_warehouse("Test Warehouse")

        with pytest.raises(
            ValidationError, match="Cannot transfer to the same warehouse"
        ):
            warehouse_service_sql.transfer_all_inventory(
                warehouse.warehouse_id, warehouse.warehouse_id
            )

    def test_transfer_all_inventory_nonexistent_source_raises_error(
        self, warehouse_service_sql
    ):
        """Test transferring from non-existent warehouse raises error."""
        warehouse2 = warehouse_service_sql.create_warehouse("Destination")

        with pytest.raises(WarehouseNotFoundError):
            warehouse_service_sql.transfer_all_inventory(9999, warehouse2.warehouse_id)

    def test_transfer_all_inventory_nonexistent_destination_raises_error(
        self, warehouse_service_sql
    ):
        """Test transferring to non-existent warehouse raises error."""
        warehouse1 = warehouse_service_sql.create_warehouse("Source")

        with pytest.raises(WarehouseNotFoundError):
            warehouse_service_sql.transfer_all_inventory(warehouse1.warehouse_id, 9999)

    def test_transfer_to_warehouse_with_existing_inventory_accumulates(
        self, warehouse_service_sql, product_repo_sql
    ):
        """Test transferring to warehouse that already has inventory accumulates quantities."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse1 = warehouse_service_sql.create_warehouse("Warehouse 1")
        warehouse2 = warehouse_service_sql.create_warehouse("Warehouse 2")

        # Add inventory to both warehouses
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            warehouse1.warehouse_id, 1, 10
        )
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            warehouse2.warehouse_id, 1, 5
        )

        # Transfer all from warehouse 1 to warehouse 2
        warehouse_service_sql.transfer_all_inventory(
            warehouse1.warehouse_id, warehouse2.warehouse_id
        )

        # Verify destination has accumulated quantity
        dest_inventory = warehouse_service_sql.get_warehouse_inventory(
            warehouse2.warehouse_id
        )
        assert len(dest_inventory) == 1
        assert dest_inventory[0].quantity == 15  # 5 + 10

    def test_delete_warehouse_with_inventory_raises_error(
        self, warehouse_service_sql, product_repo_sql
    ):
        """Test that deleting warehouse with inventory raises helpful error."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = warehouse_service_sql.create_warehouse("Test Warehouse")
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            warehouse.warehouse_id, 1, 10
        )

        with pytest.raises(
            ValidationError,
            match="Cannot delete warehouse.*still has.*items.*Use the transfer endpoint",
        ):
            warehouse_service_sql.delete_warehouse(warehouse.warehouse_id)

    def test_delete_warehouse_after_transfer_succeeds(
        self, warehouse_service_sql, product_repo_sql
    ):
        """Test that warehouse can be deleted after transferring all inventory."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse1 = warehouse_service_sql.create_warehouse("To Delete")
        warehouse2 = warehouse_service_sql.create_warehouse("Keep")

        # Add inventory
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            warehouse1.warehouse_id, 1, 10
        )

        # Transfer all inventory
        warehouse_service_sql.transfer_all_inventory(
            warehouse1.warehouse_id, warehouse2.warehouse_id
        )

        # Now delete should succeed
        warehouse_service_sql.delete_warehouse(warehouse1.warehouse_id)

        # Verify warehouse is deleted
        with pytest.raises(WarehouseNotFoundError):
            warehouse_service_sql.get_warehouse(warehouse1.warehouse_id)

        # Verify inventory is in warehouse2
        dest_inventory = warehouse_service_sql.get_warehouse_inventory(
            warehouse2.warehouse_id
        )
        assert len(dest_inventory) == 1
        assert dest_inventory[0].quantity == 10

    def test_delete_empty_warehouse_succeeds(self, warehouse_service_sql):
        """Test that empty warehouse can be deleted without transfer."""
        warehouse = warehouse_service_sql.create_warehouse("Empty Warehouse")

        # Should delete successfully
        warehouse_service_sql.delete_warehouse(warehouse.warehouse_id)

        with pytest.raises(WarehouseNotFoundError):
            warehouse_service_sql.get_warehouse(warehouse.warehouse_id)

    def test_complete_workflow_close_warehouse(
        self, warehouse_service_sql, product_repo_sql
    ):
        """Test complete workflow: warehouse closure with inventory transfer."""
        # Setup: Create products
        product1 = Product(product_id=1, name="Product 1", price=10.0)
        product2 = Product(product_id=2, name="Product 2", price=20.0)
        product_repo_sql.save(product1)
        product_repo_sql.save(product2)

        # Create warehouses
        closing_warehouse = warehouse_service_sql.create_warehouse("Closing Warehouse")
        main_warehouse = warehouse_service_sql.create_warehouse("Main Warehouse")

        # Add inventory to closing warehouse
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            closing_warehouse.warehouse_id, 1, 100
        )
        warehouse_service_sql.warehouse_repo.add_product_to_warehouse(
            closing_warehouse.warehouse_id, 2, 50
        )

        # Step 1: Verify inventory exists
        closing_inventory = warehouse_service_sql.get_warehouse_inventory(
            closing_warehouse.warehouse_id
        )
        assert len(closing_inventory) == 2

        # Step 2: Transfer all inventory to main warehouse
        transferred = warehouse_service_sql.transfer_all_inventory(
            closing_warehouse.warehouse_id, main_warehouse.warehouse_id
        )
        assert len(transferred) == 2

        # Step 3: Verify closing warehouse is empty
        closing_inventory = warehouse_service_sql.get_warehouse_inventory(
            closing_warehouse.warehouse_id
        )
        assert len(closing_inventory) == 0

        # Step 4: Verify main warehouse has all inventory
        main_inventory = warehouse_service_sql.get_warehouse_inventory(
            main_warehouse.warehouse_id
        )
        assert len(main_inventory) == 2
        main_dict = {item.product_id: item.quantity for item in main_inventory}
        assert main_dict[1] == 100
        assert main_dict[2] == 50

        # Step 5: Delete closing warehouse
        warehouse_service_sql.delete_warehouse(closing_warehouse.warehouse_id)

        # Step 6: Verify only main warehouse exists
        with pytest.raises(WarehouseNotFoundError):
            warehouse_service_sql.get_warehouse(closing_warehouse.warehouse_id)

        # Main warehouse still has inventory
        main_inventory = warehouse_service_sql.get_warehouse_inventory(
            main_warehouse.warehouse_id
        )
        assert len(main_inventory) == 2
