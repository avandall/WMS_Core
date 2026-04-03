"""
Functional tests for warehouse management workflows.
Tests complete end-to-end business processes using services directly.
"""

import pytest
from app.application.services.product_service import ProductService
from app.application.services.warehouse_service import WarehouseService
from app.application.services.inventory_service import InventoryService
from app.application.services.document_service import DocumentService
from app.infrastructure.persistence.repositories.product_repo import ProductRepo
from app.infrastructure.persistence.repositories.warehouse_repo import WarehouseRepo
from app.infrastructure.persistence.repositories.inventory_repo import InventoryRepo
from app.infrastructure.persistence.repositories.document_repo import DocumentRepo
from app.domain.entities.document import DocumentType
from app.domain.exceptions import ValidationError, InvalidQuantityError


class TestWarehouseManagementWorkflow:
    """Functional tests for complete warehouse management workflows."""

    @pytest.fixture(autouse=True)
    def setup(self, test_session):
        """Set up test fixtures with real repositories and services."""
        # Create repositories with SQL session
        self.product_repo = ProductRepo(test_session)
        self.inventory_repo = InventoryRepo(test_session)
        self.warehouse_repo = WarehouseRepo(test_session)
        self.document_repo = DocumentRepo(test_session)

        # Create services
        self.product_service = ProductService(self.product_repo, self.inventory_repo)
        self.inventory_service = InventoryService(
            self.inventory_repo, self.product_repo, self.warehouse_repo
        )
        self.warehouse_service = WarehouseService(
            self.warehouse_repo, self.product_repo, self.inventory_repo
        )
        self.document_service = DocumentService(
            self.document_repo,
            self.warehouse_repo,
            self.product_repo,
            self.inventory_repo,
        )

    def test_product_lifecycle_workflow(self):
        """Test complete product lifecycle: create, update, use in transactions, delete."""
        # Create product
        product = self.product_service.create_product(
            product_id=1,
            name="Functional Test Product",
            price=100.0,
            description="Product for functional testing",
        )
        assert product.product_id == 1
        assert product.name == "Functional Test Product"

        # Update product
        updated_product = self.product_service.update_product(
            product_id=1, name="Updated Functional Product", price=120.0
        )
        assert updated_product.name == "Updated Functional Product"
        assert updated_product.price == 120.0

        # Get product details
        retrieved_product = self.product_service.get_product_details(1)
        assert retrieved_product.price == 120.0

        # Use product in warehouse operations (will be tested in other workflows)

        # Delete product
        self.product_service.delete_product(1)

        # Verify product is gone
        from app.domain.exceptions import EntityNotFoundError

        with pytest.raises(EntityNotFoundError):
            self.product_service.get_product_details(1)

    def test_warehouse_inventory_management_workflow(self):
        """Test warehouse creation and inventory management workflow."""
        # Create warehouse
        warehouse = self.warehouse_service.create_warehouse("Functional Test Warehouse")
        warehouse_id = warehouse.warehouse_id

        # Create product
        self.product_service.create_product(
            product_id=2, name="Inventory Test Product", price=50.0
        )

        # Initially empty inventory
        inventory = self.warehouse_service.get_warehouse_inventory(warehouse_id)
        assert len(inventory) == 0

        # Import to warehouse
        import_doc2 = self.document_service.create_import_document(
            to_warehouse_id=warehouse_id,
            items=[{"product_id": 2, "quantity": 100, "unit_price": 50.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            import_doc2.document_id, approved_by="manager"
        )

        # Check inventory
        inventory = self.warehouse_service.get_warehouse_inventory(warehouse_id)
        assert len(inventory) == 1
        assert inventory[0].product_id == 2
        assert inventory[0].quantity == 100

        # Import more of the same product
        import_doc3 = self.document_service.create_import_document(
            to_warehouse_id=warehouse_id,
            items=[{"product_id": 2, "quantity": 50, "unit_price": 50.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            import_doc3.document_id, approved_by="manager"
        )

        inventory = self.warehouse_service.get_warehouse_inventory(warehouse_id)
        assert inventory[0].quantity == 150

        # Export some product
        export_doc = self.document_service.create_export_document(
            from_warehouse_id=warehouse_id,
            items=[{"product_id": 2, "quantity": 75, "unit_price": 50.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            export_doc.document_id, approved_by="manager"
        )

        inventory = self.warehouse_service.get_warehouse_inventory(warehouse_id)
        assert inventory[0].quantity == 75

        # Export remaining product
        export_doc2 = self.document_service.create_export_document(
            from_warehouse_id=warehouse_id,
            items=[{"product_id": 2, "quantity": 75, "unit_price": 50.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            export_doc2.document_id, approved_by="manager"
        )

        inventory = self.warehouse_service.get_warehouse_inventory(warehouse_id)
        assert len(inventory) == 0

    def test_import_document_workflow(self):
        """Test complete import document workflow."""
        # Create warehouse and product
        wh = self.warehouse_service.create_warehouse("Import Test Warehouse")
        warehouse_id = wh.warehouse_id

        self.product_service.create_product(
            product_id=3, name="Import Test Product", price=75.0
        )

        # Create import document
        items = [{"product_id": 3, "quantity": 200, "unit_price": 75.0}]

        document = self.document_service.create_import_document(
            to_warehouse_id=warehouse_id, items=items, created_by="functional_test_user"
        )

        assert document.doc_type == DocumentType.IMPORT
        assert document.to_warehouse_id == warehouse_id
        assert len(document.items) == 1
        assert document.status.name == "DRAFT"

        # Post the document (this would typically trigger inventory updates)
        # Note: The document service might need additional implementation for posting

    def test_export_document_workflow(self):
        """Test complete export document workflow."""
        # Create warehouse and add product to it
        warehouse = self.warehouse_service.create_warehouse("Export Test Warehouse")
        warehouse_id = warehouse.warehouse_id

        self.product_service.create_product(
            product_id=4, name="Export Test Product", price=60.0
        )

        # Import product to warehouse via document
        import_doc = self.document_service.create_import_document(
            to_warehouse_id=warehouse_id,
            items=[{"product_id": 4, "quantity": 100, "unit_price": 60.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            import_doc.document_id, approved_by="manager"
        )

        # Create export document
        items = [{"product_id": 4, "quantity": 30, "unit_price": 60.0}]

        document = self.document_service.create_export_document(
            from_warehouse_id=warehouse_id,
            items=items,
            created_by="functional_test_user",
        )

        assert document.doc_type == DocumentType.EXPORT
        assert document.from_warehouse_id == warehouse_id
        assert len(document.items) == 1
        assert document.status.name == "DRAFT"

    def test_transfer_document_workflow(self):
        """Test complete transfer document workflow."""
        # Create two warehouses
        source_warehouse = self.warehouse_service.create_warehouse("Source Warehouse")
        dest_warehouse = self.warehouse_service.create_warehouse(
            "Destination Warehouse"
        )
        source_id = source_warehouse.warehouse_id
        dest_id = dest_warehouse.warehouse_id

        # Create product and add to source warehouse
        self.product_service.create_product(
            product_id=5, name="Transfer Test Product", price=80.0
        )

        # Import stock into source warehouse
        import_doc = self.document_service.create_import_document(
            to_warehouse_id=source_id,
            items=[{"product_id": 5, "quantity": 150, "unit_price": 80.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            import_doc.document_id, approved_by="manager"
        )

        # Create transfer document
        items = [{"product_id": 5, "quantity": 75, "unit_price": 80.0}]

        document = self.document_service.create_transfer_document(
            from_warehouse_id=source_id,
            to_warehouse_id=dest_id,
            items=items,
            created_by="functional_test_user",
        )

        assert document.doc_type == DocumentType.TRANSFER
        assert document.from_warehouse_id == source_id
        assert document.to_warehouse_id == dest_id
        assert len(document.items) == 1
        assert document.status.name == "DRAFT"

    def test_insufficient_stock_prevention(self):
        """Test that operations prevent insufficient stock situations."""
        # Create warehouse and product
        warehouse = self.warehouse_service.create_warehouse("Stock Control Warehouse")
        warehouse_id = warehouse.warehouse_id

        self.product_service.create_product(
            product_id=6, name="Stock Control Product", price=90.0
        )

        # Import limited quantity
        import_doc = self.document_service.create_import_document(
            to_warehouse_id=warehouse_id,
            items=[{"product_id": 6, "quantity": 50, "unit_price": 90.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            import_doc.document_id, approved_by="manager"
        )

        # Try to create export document with more than available
        items = [
            {"product_id": 6, "quantity": 75, "unit_price": 90.0}  # More than available
        ]

        # This should succeed at document level (documents can be created for future stock)
        document = self.document_service.create_export_document(
            from_warehouse_id=warehouse_id, items=items, created_by="test_user"
        )
        assert document is not None

        # Posting export with more than available should fail
        export_doc2 = self.document_service.create_export_document(
            from_warehouse_id=warehouse_id,
            items=[{"product_id": 6, "quantity": 75, "unit_price": 90.0}],
            created_by="test_user",
        )
        with pytest.raises(Exception):
            self.document_service.post_document(
                export_doc2.document_id, approved_by="manager"
            )

    def test_multiple_warehouses_inventory_tracking(self):
        """Test inventory tracking across multiple warehouses."""
        # Create multiple warehouses
        warehouse1 = self.warehouse_service.create_warehouse("Warehouse 1")
        warehouse2 = self.warehouse_service.create_warehouse("Warehouse 2")
        w1_id = warehouse1.warehouse_id
        w2_id = warehouse2.warehouse_id

        # Create product
        self.product_service.create_product(
            product_id=7, name="Multi-Warehouse Product", price=45.0
        )

        # Import to warehouses via documents
        import_doc1 = self.document_service.create_import_document(
            to_warehouse_id=w1_id,
            items=[{"product_id": 7, "quantity": 100, "unit_price": 45.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            import_doc1.document_id, approved_by="manager"
        )

        import_doc2 = self.document_service.create_import_document(
            to_warehouse_id=w2_id,
            items=[{"product_id": 7, "quantity": 200, "unit_price": 45.0}],
            created_by="functional_test_user",
        )
        self.document_service.post_document(
            import_doc2.document_id, approved_by="manager"
        )

        # Check individual warehouse inventories
        w1_inventory = self.warehouse_service.get_warehouse_inventory(w1_id)
        w2_inventory = self.warehouse_service.get_warehouse_inventory(w2_id)

        assert len(w1_inventory) == 1
        assert w1_inventory[0].quantity == 100
        assert len(w2_inventory) == 1
        assert w2_inventory[0].quantity == 200

        # Total inventory should be tracked separately
        # (This would require additional service methods to aggregate)

    def test_business_rules_enforcement(self):
        """Test that business rules are properly enforced across the system."""
        # Test warehouse location requirements
        with pytest.raises(ValidationError):
            self.warehouse_service.create_warehouse("")  # Empty location

        # Test product validation
        with pytest.raises(ValidationError):
            self.product_service.create_product(
                product_id=8,
                name="",  # Empty name
                price=10.0,
            )

        with pytest.raises(InvalidQuantityError):
            self.product_service.create_product(
                product_id=9,
                name="Valid Name",
                price=-5.0,  # Negative price
            )

        # Test quantity validations
        warehouse = self.warehouse_service.create_warehouse("Rules Test Warehouse")
        self.product_service.create_product(10, "Rules Product", 25.0)

        with pytest.raises(Exception):  # InvalidQuantityError
            self.document_service.create_import_document(
                to_warehouse_id=warehouse.warehouse_id,
                items=[{"product_id": 10, "quantity": -10, "unit_price": 25.0}],
                created_by="functional_test_user",
            )
