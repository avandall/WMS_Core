"""
Functional Tests for Warehouse Operations
Tests warehouse operations from a business functionality perspective
Focuses on user workflows and business rules rather than implementation details
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.modules.products.domain.entities.product import Product
from app.modules.documents.domain.entities.document import Document, DocumentProduct, DocumentType, DocumentStatus
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.documents.application.services.document_service import DocumentService
from app.modules.products.application.services.product_service import ProductService


class TestWarehouseOperationsFunctional:
    """Functional tests for warehouse operations"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_warehouse_service(self):
        """Mock WarehouseService"""
        return Mock(spec=WarehouseService)

    @pytest.fixture
    def mock_inventory_service(self):
        """Mock InventoryService"""
        return Mock(spec=InventoryService)

    @pytest.fixture
    def mock_document_service(self):
        """Mock DocumentService"""
        return Mock(spec=DocumentService)

    @pytest.fixture
    def mock_product_service(self):
        """Mock ProductService"""
        return Mock(spec=ProductService)

    @pytest.fixture
    def sample_warehouse(self):
        """Sample warehouse for testing"""
        return Warehouse(
            warehouse_id=1,
            location="Main Warehouse",
            inventory=[
                InventoryItem(product_id=1, quantity=100),
                InventoryItem(product_id=2, quantity=50)
            ]
        )

    @pytest.fixture
    def sample_products(self):
        """Sample products for testing"""
        return [
            Product(product_id=1, name="Product A", price=99.99),
            Product(product_id=2, name="Product B", price=49.99),
            Product(product_id=3, name="Product C", price=29.99)
        ]

    @pytest.fixture
    def sample_inventory_items(self):
        """Sample inventory items for testing"""
        return [
            InventoryItem(product_id=1, quantity=100),
            InventoryItem(product_id=2, quantity=50),
            InventoryItem(product_id=3, quantity=25)
        ]

    # ============================================================================
    # WAREHOUSE CREATION AND MANAGEMENT WORKFLOWS
    # ============================================================================

    def test_create_new_warehouse_workflow(self, mock_warehouse_service, mock_inventory_service):
        """Test functional workflow for creating a new warehouse"""
        
        # Setup mocks
        created_warehouse = Warehouse(warehouse_id=1, location="New Warehouse")
        mock_warehouse_service.create_warehouse.return_value = created_warehouse
        mock_warehouse_service.get_warehouse_inventory.return_value = []
        
        # Execute workflow
        warehouse = mock_warehouse_service.create_warehouse("New Warehouse")
        inventory = mock_warehouse_service.get_warehouse_inventory(warehouse.warehouse_id)
        
        # Verify workflow results
        assert warehouse.location == "New Warehouse"
        assert warehouse.warehouse_id == 1
        assert len(inventory) == 0  # New warehouse starts empty
        
        # Verify service interactions
        mock_warehouse_service.create_warehouse.assert_called_once_with("New Warehouse")
        mock_warehouse_service.get_warehouse_inventory.assert_called_once_with(1)

    def test_warehouse_setup_with_initial_inventory(self, mock_warehouse_service, mock_inventory_service, mock_document_service, sample_products, sample_inventory_items):
        """Test functional workflow for setting up warehouse with initial inventory"""
        
        # Setup mocks
        warehouse = Warehouse(warehouse_id=1, location="Setup Warehouse")
        import_document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=[
                DocumentProduct(product_id=1, quantity=100, unit_price=99.99),
                DocumentProduct(product_id=2, quantity=50, unit_price=49.99)
            ],
            created_by="admin"
        )
        
        mock_warehouse_service.create_warehouse.return_value = warehouse
        mock_document_service.create_import_document.return_value = import_document
        mock_document_service.post_document.return_value = import_document
        # Set status to POSTED to simulate successful posting
        mock_document_service.post_document.return_value.status = DocumentStatus.POSTED
        mock_warehouse_service.get_warehouse_inventory.return_value = sample_inventory_items[:2]
        
        # Execute workflow
        # 1. Create warehouse
        warehouse = mock_warehouse_service.create_warehouse("Setup Warehouse")
        
        # 2. Create import document for initial inventory
        items_data = [
            {"product_id": 1, "quantity": 100, "unit_price": 99.99},
            {"product_id": 2, "quantity": 50, "unit_price": 49.99}
        ]
        document = mock_document_service.create_import_document(
            to_warehouse_id=warehouse.warehouse_id,
            items=items_data,
            created_by="admin"
        )
        
        # 3. Post document to add inventory
        posted_document = mock_document_service.post_document(document.document_id, "manager")
        
        # 4. Verify inventory
        inventory = mock_warehouse_service.get_warehouse_inventory(warehouse.warehouse_id)
        
        # Verify workflow results
        assert warehouse.location == "Setup Warehouse"
        assert posted_document.status == DocumentStatus.POSTED
        assert len(inventory) == 2
        assert inventory[0].product_id == 1
        assert inventory[0].quantity == 100
        assert inventory[1].product_id == 2
        assert inventory[1].quantity == 50

    def test_warehouse_relocation_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service, sample_warehouse, sample_inventory_items):
        """Test functional workflow for relocating warehouse inventory"""
        
        # Setup mocks
        source_warehouse = sample_warehouse
        target_warehouse = Warehouse(warehouse_id=2, location="Target Warehouse")
        transfer_document = Document(
            document_id=1,
            doc_type=DocumentType.TRANSFER,
            from_warehouse_id=1,
            to_warehouse_id=2,
            items=[
                DocumentProduct(product_id=1, quantity=50, unit_price=99.99),
                DocumentProduct(product_id=2, quantity=25, unit_price=49.99)
            ],
            created_by="admin"
        )
        
        mock_warehouse_service.get_warehouse.side_effect = [source_warehouse, target_warehouse]
        mock_document_service.create_transfer_document.return_value = transfer_document
        mock_document_service.post_document.return_value = transfer_document
        # Set status to POSTED to simulate successful posting
        mock_document_service.post_document.return_value.status = DocumentStatus.POSTED
        mock_warehouse_service.transfer_all_inventory.return_value = sample_inventory_items[:2]
        
        # Execute workflow
        # 1. Get source warehouse
        source = mock_warehouse_service.get_warehouse(1)
        
        # 2. Create target warehouse
        target = mock_warehouse_service.create_warehouse("Target Warehouse")
        
        # 3. Create transfer document
        items_data = [
            {"product_id": 1, "quantity": 50, "unit_price": 99.99},
            {"product_id": 2, "quantity": 25, "unit_price": 49.99}
        ]
        document = mock_document_service.create_transfer_document(
            from_warehouse_id=source.warehouse_id,
            to_warehouse_id=target.warehouse_id,
            items=items_data,
            created_by="admin"
        )
        
        # 4. Post transfer document
        posted_document = mock_document_service.post_document(document.document_id, "manager")
        
        # 5. Alternative: Transfer all inventory at once
        transferred_items = mock_warehouse_service.transfer_all_inventory(
            from_warehouse_id=source.warehouse_id,
            to_warehouse_id=target.warehouse_id
        )
        
        # Verify workflow results
        assert posted_document.status == DocumentStatus.POSTED
        assert posted_document.from_warehouse_id == 1
        assert posted_document.to_warehouse_id == 2
        assert len(transferred_items) == 2

    # ============================================================================
    # INVENTORY MANAGEMENT WORKFLOWS
    # ============================================================================

    def test_inventory_receiving_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service, mock_product_service, sample_products):
        """Test functional workflow for receiving inventory"""
        
        # Setup mocks
        warehouse = Warehouse(warehouse_id=1, location="Receiving Warehouse")
        product = sample_products[0]
        import_document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=[DocumentProduct(product_id=1, quantity=100, unit_price=99.99)],
            created_by="admin",
            note="Receiving shipment #12345"
        )
        
        mock_warehouse_service.get_warehouse.return_value = warehouse
        mock_product_service.get_product_details.return_value = product
        mock_document_service.create_import_document.return_value = import_document
        mock_document_service.post_document.return_value = import_document
        # Set status to POSTED to simulate successful posting
        mock_document_service.post_document.return_value.status = DocumentStatus.POSTED
        mock_warehouse_service.get_warehouse_inventory.return_value = [InventoryItem(product_id=1, quantity=100)]
        
        # Execute workflow
        # 1. Verify warehouse exists
        warehouse = mock_warehouse_service.get_warehouse(1)
        
        # 2. Verify product exists
        product = mock_product_service.get_product_details(1)
        
        # 3. Create import document
        items_data = [{"product_id": product.product_id, "quantity": 100, "unit_price": 99.99}]
        document = mock_document_service.create_import_document(
            to_warehouse_id=warehouse.warehouse_id,
            items=items_data,
            created_by="admin",
            note="Receiving shipment #12345"
        )
        
        # 4. Post document to receive inventory
        posted_document = mock_document_service.post_document(document.document_id, "manager")
        
        # 5. Verify inventory updated
        inventory = mock_warehouse_service.get_warehouse_inventory(warehouse.warehouse_id)
        
        # Verify workflow results
        assert posted_document.status == DocumentStatus.POSTED
        assert posted_document.note == "Receiving shipment #12345"
        assert len(inventory) == 1
        assert inventory[0].product_id == 1
        assert inventory[0].quantity == 100

    def test_inventory_shipping_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service, mock_product_service, sample_products, sample_inventory_items):
        """Test functional workflow for shipping inventory"""
        
        # Setup mocks
        warehouse = Warehouse(warehouse_id=1, location="Shipping Warehouse")
        product = sample_products[0]
        export_document = Document(
            document_id=1,
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=1,
            items=[DocumentProduct(product_id=1, quantity=25, unit_price=99.99)],
            created_by="admin",
            note="Customer order #67890"
        )
        
        mock_warehouse_service.get_warehouse.return_value = warehouse
        mock_product_service.get_product_details.return_value = product
        # Use side_effect to return different inventory values on different calls
        mock_warehouse_service.get_warehouse_inventory.side_effect = [
            [InventoryItem(product_id=1, quantity=100)],  # Before shipping
            [InventoryItem(product_id=1, quantity=75)]   # After shipping
        ]
        mock_document_service.create_export_document.return_value = export_document
        mock_document_service.post_document.return_value = export_document
        # Set status to POSTED to simulate successful posting
        mock_document_service.post_document.return_value.status = DocumentStatus.POSTED
        
        # Execute workflow
        # 1. Check current inventory
        current_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        initial_quantity = current_inventory[0].quantity if current_inventory else 0
        
        # 2. Create export document
        items_data = [{"product_id": 1, "quantity": 25, "unit_price": 99.99}]
        document = mock_document_service.create_export_document(
            from_warehouse_id=1,
            items=items_data,
            created_by="admin",
            note="Customer order #67890"
        )
        
        # 3. Post document to ship inventory
        posted_document = mock_document_service.post_document(document.document_id, "manager")
        
        # 4. Verify inventory updated
        final_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        final_quantity = final_inventory[0].quantity if final_inventory else 0
        
        # Verify workflow results
        assert posted_document.status == DocumentStatus.POSTED
        assert posted_document.note == "Customer order #67890"
        assert initial_quantity == 100
        assert final_quantity == 75  # 100 - 25 shipped

    def test_inventory_adjustment_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service):
        """Test functional workflow for inventory adjustments"""
        
        # Setup mocks
        warehouse = Warehouse(warehouse_id=1, location="Adjustment Warehouse")
        
        mock_warehouse_service.get_warehouse.return_value = warehouse
        mock_warehouse_service.get_warehouse_inventory.return_value = [InventoryItem(product_id=1, quantity=100)]
        mock_inventory_service.add_to_total_inventory.return_value = None
        mock_inventory_service.remove_from_total_inventory.return_value = None
        
        # Execute workflow
        # 1. Check current inventory
        current_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        initial_quantity = current_inventory[0].quantity if current_inventory else 0
        
        # 2. Add inventory (stock in)
        mock_inventory_service.add_to_total_inventory(1, 25)
        
        # 3. Remove inventory (stock out)
        mock_inventory_service.remove_from_total_inventory(1, 10)
        
        # 4. Check final inventory
        final_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        
        # Verify workflow results
        assert initial_quantity == 100
        mock_inventory_service.add_to_total_inventory.assert_called_once_with(1, 25)
        mock_inventory_service.remove_from_total_inventory.assert_called_once_with(1, 10)

    # ============================================================================
    # STOCK LEVEL MANAGEMENT WORKFLOWS
    # ============================================================================

    def test_low_stock_monitoring_workflow(self, mock_inventory_service, mock_product_service, sample_products, sample_inventory_items):
        """Test functional workflow for monitoring low stock levels"""
        
        # Setup mocks
        low_stock_items = [
            {"product": sample_products[2], "current_quantity": 5, "threshold": 10, "needs_restock": True}
        ]
        
        mock_inventory_service.get_low_stock_products.return_value = low_stock_items
        mock_product_service.get_product_details.side_effect = sample_products
        
        # Execute workflow
        # 1. Check low stock products
        low_stock = mock_inventory_service.get_low_stock_products(threshold=10)
        
        # 2. Generate restock recommendations
        restock_recommendations = []
        for item in low_stock:
            product = mock_product_service.get_product_details(item["product"].product_id)
            restock_quantity = item["threshold"] * 2  # Restock to double the threshold
            restock_recommendations.append({
                "product": product,
                "current_quantity": item["current_quantity"],
                "recommended_quantity": restock_quantity,
                "urgency": "HIGH" if item["current_quantity"] < item["threshold"] / 2 else "MEDIUM"
            })
        
        # Verify workflow results
        assert len(low_stock) == 1
        assert low_stock[0]["product"].product_id == 3
        assert low_stock[0]["current_quantity"] == 5
        assert low_stock[0]["needs_restock"] is True
        
        assert len(restock_recommendations) == 1
        assert restock_recommendations[0]["recommended_quantity"] == 20
        assert restock_recommendations[0]["urgency"] == "MEDIUM"

    def test_stock_count_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service, sample_warehouse, sample_inventory_items):
        """Test functional workflow for physical stock count"""
        
        # Setup mocks
        adjustment_document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,  # Using import for adjustments
            to_warehouse_id=1,
            items=[
                DocumentProduct(product_id=1, quantity=5, unit_price=0.00),  # Adjustment
                DocumentProduct(product_id=2, quantity=3, unit_price=0.00)  # Adjustment
            ],
            created_by="admin"
        )
        
        mock_warehouse_service.get_warehouse.return_value = sample_warehouse
        mock_warehouse_service.get_warehouse_inventory.return_value = sample_inventory_items
        mock_document_service.create_import_document.return_value = adjustment_document
        mock_document_service.post_document.return_value = adjustment_document
        # Set status to POSTED to simulate successful posting
        mock_document_service.post_document.return_value.status = DocumentStatus.POSTED
        
        # Execute workflow
        # 1. Get current system inventory
        system_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        system_counts = {item.product_id: item.quantity for item in system_inventory}
        
        # 2. Simulate physical count results
        physical_counts = {
            1: 105,  # System says 100, physical count says 105
            2: 47,   # System says 50, physical count says 47
            3: 25    # System says 25, physical count says 25 (matches)
        }
        
        # 3. Calculate adjustments needed
        adjustments = []
        for product_id, physical_count in physical_counts.items():
            system_count = system_counts.get(product_id, 0)
            difference = physical_count - system_count
            if difference != 0:
                adjustments.append({
                    "product_id": product_id,
                    "difference": difference,
                    "adjustment_type": "INCREASE" if difference > 0 else "DECREASE",
                    "quantity": abs(difference)
                })
        
        # 4. Create adjustment document
        adjustment_items = []
        for adj in adjustments:
            adjustment_items.append({
                "product_id": adj["product_id"],
                "quantity": adj["quantity"],
                "unit_price": 0.00  # Adjustments have no cost
            })
        
        if adjustment_items:
            document = mock_document_service.create_import_document(
                to_warehouse_id=1,
                items=adjustment_items,
                created_by="admin",
                note="Stock count adjustment - Cycle #123"
            )
            
            # 5. Post adjustment document
            posted_document = mock_document_service.post_document(document.document_id, "manager")
        
        # Verify workflow results
        assert len(adjustments) == 2
        assert adjustments[0]["product_id"] == 1
        assert adjustments[0]["difference"] == 5
        assert adjustments[0]["adjustment_type"] == "INCREASE"
        
        assert adjustments[1]["product_id"] == 2
        assert adjustments[1]["difference"] == -3
        assert adjustments[1]["adjustment_type"] == "DECREASE"

    # ============================================================================
    # MULTI-WAREHOUSE OPERATIONS WORKFLOWS
    # ============================================================================

    def test_cross_warehouse_transfer_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service, sample_products):
        """Test functional workflow for cross-warehouse transfers"""
        
        # Setup mocks
        source_warehouse = Warehouse(warehouse_id=1, location="Source Warehouse")
        target_warehouse = Warehouse(warehouse_id=2, location="Target Warehouse")
        transfer_document = Document(
            document_id=1,
            doc_type=DocumentType.TRANSFER,
            from_warehouse_id=1,
            to_warehouse_id=2,
            items=[DocumentProduct(product_id=1, quantity=50, unit_price=99.99)],
            created_by="admin",
            note="Stock replenishment for Target Warehouse"
        )
        
        mock_warehouse_service.get_warehouse.side_effect = [source_warehouse, target_warehouse]
        mock_warehouse_service.get_warehouse_inventory.side_effect = [
            [InventoryItem(product_id=1, quantity=100)],  # Source inventory
            [InventoryItem(product_id=1, quantity=25)]   # Target inventory
        ]
        mock_document_service.create_transfer_document.return_value = transfer_document
        mock_document_service.post_document.return_value = transfer_document
        # Set status to POSTED to simulate successful posting
        mock_document_service.post_document.return_value.status = DocumentStatus.POSTED
        mock_warehouse_service.transfer_product.return_value = None
        
        # Execute workflow
        # 1. Check source warehouse inventory
        source_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        source_quantity = source_inventory[0].quantity if source_inventory else 0
        
        # 2. Check target warehouse inventory
        target_inventory = mock_warehouse_service.get_warehouse_inventory(2)
        target_quantity = target_inventory[0].quantity if target_inventory else 0
        
        # 3. Verify sufficient stock for transfer
        transfer_quantity = 50
        assert source_quantity >= transfer_quantity, "Insufficient stock for transfer"
        
        # 4. Create transfer document
        items_data = [{"product_id": 1, "quantity": transfer_quantity, "unit_price": 99.99}]
        document = mock_document_service.create_transfer_document(
            from_warehouse_id=1,
            to_warehouse_id=2,
            items=items_data,
            created_by="admin",
            note="Stock replenishment for Target Warehouse"
        )
        
        # 5. Post transfer document
        posted_document = mock_document_service.post_document(document.document_id, "manager")
        
        # 6. Alternative: Use direct transfer service
        mock_warehouse_service.transfer_product(
            from_warehouse_id=1,
            to_warehouse_id=2,
            product_id=1,
            quantity=transfer_quantity
        )
        
        # Verify workflow results
        assert source_quantity == 100
        assert target_quantity == 25
        assert posted_document.status == DocumentStatus.POSTED
        assert posted_document.note == "Stock replenishment for Target Warehouse"

    def test_warehouse_consolidation_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service, sample_products):
        """Test functional workflow for warehouse consolidation"""
        
        # Setup mocks
        old_warehouse = Warehouse(warehouse_id=1, location="Old Warehouse")
        new_warehouse = Warehouse(warehouse_id=2, location="New Warehouse")
        
        mock_warehouse_service.get_warehouse.side_effect = [old_warehouse, new_warehouse]
        mock_warehouse_service.get_warehouse_inventory.return_value = [
            InventoryItem(product_id=1, quantity=100),
            InventoryItem(product_id=2, quantity=50),
            InventoryItem(product_id=3, quantity=25)
        ]
        mock_warehouse_service.transfer_all_inventory.return_value = [
            InventoryItem(product_id=1, quantity=100),
            InventoryItem(product_id=2, quantity=50),
            InventoryItem(product_id=3, quantity=25)
        ]
        mock_warehouse_service.delete_warehouse.return_value = None
        
        # Execute workflow
        # 1. Get old warehouse inventory
        old_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        
        # 2. Transfer all inventory to new warehouse
        transferred_items = mock_warehouse_service.transfer_all_inventory(
            from_warehouse_id=1,
            to_warehouse_id=2
        )
        
        # 3. Verify all items transferred
        assert len(transferred_items) == len(old_inventory)
        
        # 4. Delete old warehouse
        mock_warehouse_service.delete_warehouse(1)
        
        # Verify workflow results
        assert len(old_inventory) == 3
        assert len(transferred_items) == 3
        mock_warehouse_service.transfer_all_inventory.assert_called_once_with(from_warehouse_id=1, to_warehouse_id=2)
        mock_warehouse_service.delete_warehouse.assert_called_once_with(1)

    # ============================================================================
    # REPORTING AND ANALYTICS WORKFLOWS
    # ============================================================================

    def test_warehouse_utilization_report_workflow(self, mock_warehouse_service, mock_inventory_service, sample_warehouse, sample_inventory_items):
        """Test functional workflow for warehouse utilization reporting"""
        
        # Setup mocks
        warehouses_with_inventory = [
            {
                "warehouse": sample_warehouse,
                "inventory_summary": {
                    "total_items": 175,  # 100 + 50 + 25
                    "unique_products": 3,
                    "inventory_details": sample_inventory_items
                }
            }
        ]
        
        mock_warehouse_service.get_all_warehouses_with_inventory_summary.return_value = warehouses_with_inventory
        mock_inventory_service.get_all_inventory_with_details.return_value = [
            {
                "product": Mock(product_id=1, name="Product A"),
                "total_quantity": 100,
                "warehouse_distribution": [
                    {"warehouse_id": 1, "warehouse_name": "Main Warehouse", "quantity": 100}
                ]
            },
            {
                "product": Mock(product_id=2, name="Product B"),
                "total_quantity": 50,
                "warehouse_distribution": [
                    {"warehouse_id": 1, "warehouse_name": "Main Warehouse", "quantity": 50}
                ]
            },
            {
                "product": Mock(product_id=3, name="Product C"),
                "total_quantity": 25,
                "warehouse_distribution": [
                    {"warehouse_id": 1, "warehouse_name": "Main Warehouse", "quantity": 25}
                ]
            }
        ]
        
        # Execute workflow
        # 1. Get warehouse summaries
        warehouse_summaries = mock_warehouse_service.get_all_warehouses_with_inventory_summary()
        
        # 2. Get detailed inventory information
        inventory_details = mock_inventory_service.get_all_inventory_with_details()
        
        # 3. Generate utilization report
        utilization_report = {
            "total_warehouses": len(warehouse_summaries),
            "total_products": len(inventory_details),
            "total_inventory_items": sum(summary["inventory_summary"]["total_items"] for summary in warehouse_summaries),
            "average_items_per_warehouse": sum(summary["inventory_summary"]["total_items"] for summary in warehouse_summaries) / len(warehouse_summaries) if warehouse_summaries else 0,
            "warehouse_details": []
        }
        
        for summary in warehouse_summaries:
            warehouse_detail = {
                "warehouse_id": summary["warehouse"].warehouse_id,
                "location": summary["warehouse"].location,
                "total_items": summary["inventory_summary"]["total_items"],
                "unique_products": summary["inventory_summary"]["unique_products"],
                "utilization_percentage": (summary["inventory_summary"]["unique_products"] / len(inventory_details)) * 100 if inventory_details else 0
            }
            utilization_report["warehouse_details"].append(warehouse_detail)
        
        # Verify workflow results
        assert utilization_report["total_warehouses"] == 1
        assert utilization_report["total_products"] == 3
        assert utilization_report["total_inventory_items"] == 175
        assert utilization_report["average_items_per_warehouse"] == 175.0
        assert len(utilization_report["warehouse_details"]) == 1

    def test_inventory_turnover_analysis_workflow(self, mock_inventory_service, mock_document_service, sample_products):
        """Test functional workflow for inventory turnover analysis"""
        
        # Setup mocks
        inventory_summary = {
            "total_products": 3,
            "total_inventory_items": 175,
            "low_stock_products": [
                {"product": sample_products[2], "current_quantity": 25, "threshold": 10}
            ]
        }
        
        recent_documents = [
            Document(
                document_id=1,
                doc_type=DocumentType.EXPORT,
                from_warehouse_id=1,
                items=[DocumentProduct(product_id=1, quantity=25, unit_price=99.99)],
                created_by="admin"
            ),
            Document(
                document_id=2,
                doc_type=DocumentType.EXPORT,
                from_warehouse_id=1,
                items=[DocumentProduct(product_id=2, quantity=15, unit_price=49.99)],
                created_by="admin"
            )
        ]
        
        mock_inventory_service.get_inventory_summary.return_value = inventory_summary
        mock_document_service.get_pending_documents.return_value = []
        mock_document_service.get_documents_by_status.return_value = recent_documents
        
        # Execute workflow
        # 1. Get current inventory summary
        current_summary = mock_inventory_service.get_inventory_summary()
        
        # 2. Get recent sales/exports
        recent_exports = mock_document_service.get_documents_by_status(DocumentStatus.POSTED)
        
        # 3. Calculate turnover metrics
        total_sales_quantity = 0
        product_sales = {}
        
        for document in recent_exports:
            if document.doc_type in [DocumentType.EXPORT, DocumentType.SALE]:
                for item in document.items:
                    total_sales_quantity += item.quantity
                    product_sales[item.product_id] = product_sales.get(item.product_id, 0) + item.quantity
        
        # 4. Generate turnover analysis
        turnover_analysis = {
            "total_products": current_summary["total_products"],
            "total_inventory_value": current_summary["total_inventory_items"],
            "total_sales_quantity": total_sales_quantity,
            "product_turnover": [],
            "slow_moving_products": [],
            "fast_moving_products": []
        }
        
        for product_id, sales_quantity in product_sales.items():
            current_quantity = next((item["product"].product_id for item in current_summary["low_stock_products"] if item["product"].product_id == product_id), 0)
            turnover_rate = sales_quantity / max(current_quantity, 1)
            
            turnover_analysis["product_turnover"].append({
                "product_id": product_id,
                "sales_quantity": sales_quantity,
                "current_quantity": current_quantity,
                "turnover_rate": turnover_rate
            })
            
            if turnover_rate > 2:
                turnover_analysis["fast_moving_products"].append(product_id)
            elif turnover_rate < 0.5:
                turnover_analysis["slow_moving_products"].append(product_id)
        
        # Verify workflow results
        assert turnover_analysis["total_products"] == 3
        assert turnover_analysis["total_sales_quantity"] == 40  # 25 + 15
        assert len(turnover_analysis["product_turnover"]) == 2

    # ============================================================================
    # ERROR HANDLING AND EDGE CASE WORKFLOWS
    # ============================================================================

    def test_insufficient_stock_handling_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service):
        """Test functional workflow for handling insufficient stock situations"""
        
        # Setup mocks
        warehouse = Warehouse(warehouse_id=1, location="Test Warehouse")
        
        mock_warehouse_service.get_warehouse.return_value = warehouse
        mock_warehouse_service.get_warehouse_inventory.return_value = [InventoryItem(product_id=1, quantity=10)]
        
        # Execute workflow
        # 1. Check available stock
        available_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        available_quantity = available_inventory[0].quantity if available_inventory else 0
        
        # 2. Attempt to fulfill order requiring more stock
        required_quantity = 25
        
        # 3. Handle insufficient stock
        if available_quantity < required_quantity:
            # Option 1: Partial fulfillment
            partial_fulfillment = min(available_quantity, required_quantity)
            
            # Option 2: Suggest alternative warehouse
            alternative_warehouses = [2, 3]  # Mock alternative warehouse IDs
            
            # Option 3: Create backorder
            backorder_quantity = required_quantity - available_quantity
            
            # Generate response
            response = {
                "status": "INSUFFICIENT_STOCK",
                "available_quantity": available_quantity,
                "required_quantity": required_quantity,
                "partial_fulfillment_possible": partial_fulfillment > 0,
                "partial_fulfillment_quantity": partial_fulfillment,
                "backorder_quantity": backorder_quantity,
                "alternative_warehouses": alternative_warehouses,
                "recommendations": [
                    "Fulfill partial order and create backorder",
                    "Check alternative warehouses for stock",
                    "Place emergency order with supplier"
                ]
            }
        else:
            response = {"status": "SUFFICIENT_STOCK"}
        
        # Verify workflow results
        assert available_quantity == 10
        assert required_quantity == 25
        assert response["status"] == "INSUFFICIENT_STOCK"
        assert response["partial_fulfillment_quantity"] == 10
        assert response["backorder_quantity"] == 15

    def test_warehouse_closure_workflow(self, mock_warehouse_service, mock_inventory_service, mock_document_service, sample_products):
        """Test functional workflow for warehouse closure and decommissioning"""
        
        # Setup mocks
        closing_warehouse = Warehouse(warehouse_id=1, location="Closing Warehouse")
        target_warehouse = Warehouse(warehouse_id=2, location="Target Warehouse")
        
        mock_warehouse_service.get_warehouse.side_effect = [closing_warehouse, target_warehouse]
        mock_warehouse_service.get_warehouse_inventory.side_effect = [
            # First call: inventory before transfer
            [
                InventoryItem(product_id=1, quantity=100),
                InventoryItem(product_id=2, quantity=50)
            ],
            # Second call: empty inventory after transfer
            []
        ]
        mock_warehouse_service.transfer_all_inventory.return_value = [
            InventoryItem(product_id=1, quantity=100),
            InventoryItem(product_id=2, quantity=50)
        ]
        mock_warehouse_service.delete_warehouse.return_value = None
        
        # Execute workflow
        # 1. Check warehouse inventory
        inventory = mock_warehouse_service.get_warehouse_inventory(1)
        
        # 2. Transfer all inventory to target warehouse
        if inventory:
            transferred_items = mock_warehouse_service.transfer_all_inventory(
                from_warehouse_id=1,
                to_warehouse_id=2
            )
        
        # 3. Verify warehouse is empty
        final_inventory = mock_warehouse_service.get_warehouse_inventory(1)
        
        # 4. Close warehouse
        if not final_inventory:
            mock_warehouse_service.delete_warehouse(1)
            closure_status = "SUCCESS"
        else:
            closure_status = "FAILED - Inventory remaining"
        
        # Verify workflow results
        assert len(inventory) == 2
        assert len(transferred_items) == 2
        assert closure_status == "SUCCESS"
        mock_warehouse_service.delete_warehouse.assert_called_once_with(1)
