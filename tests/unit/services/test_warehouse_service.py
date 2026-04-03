"""
Unit tests aligned to document-only operations.
Tests focus on DocumentService posting import/export operations affecting warehouse inventory.
"""

import pytest
from unittest.mock import Mock
from app.application.services.document_service import DocumentService
from app.application.services.warehouse_service import WarehouseService
from app.domain.entities.warehouse import Warehouse
from app.domain.entities.inventory import InventoryItem
from app.domain.exceptions import (
    ValidationError,
    WarehouseNotFoundError,
    InsufficientStockError,
    InvalidQuantityError,
)


class TestDocumentOperations:
    """Test cases for document-driven warehouse operations."""

    @pytest.fixture
    def mock_warehouse_repo(self):
        """Mock warehouse repository."""
        return Mock()

    @pytest.fixture
    def mock_product_repo(self):
        """Mock product repository."""
        return Mock()

    @pytest.fixture
    def mock_inventory_repo(self):
        """Mock inventory repository."""
        return Mock()

    @pytest.fixture
    def mock_id_generator(self):
        """Mock ID generator."""
        return Mock(return_value=123)

    @pytest.fixture
    def warehouse_service(
        self,
        mock_warehouse_repo,
        mock_product_repo,
        mock_inventory_repo,
        mock_id_generator,
    ):
        """Warehouse service with injected mock ID generator."""
        return WarehouseService(
            mock_warehouse_repo,
            mock_product_repo,
            mock_inventory_repo,
            id_generator=mock_id_generator,
        )

    @pytest.fixture
    def document_service(
        self, mock_warehouse_repo, mock_product_repo, mock_inventory_repo
    ):
        """Document service with mocked dependencies."""
        # Create a simple mock document repo with in-memory storage
        mock_document_repo = Mock()
        stored_docs = {}

        def save(doc):
            stored_docs[doc.document_id] = doc

        mock_document_repo.save.side_effect = save
        mock_document_repo.get.side_effect = lambda doc_id: stored_docs.get(doc_id)
        mock_document_repo.get_all.side_effect = lambda: list(stored_docs.values())
        service = DocumentService(
            mock_document_repo,
            mock_warehouse_repo,
            mock_product_repo,
            mock_inventory_repo,
        )
        return service

    @pytest.fixture
    def sample_warehouse(self):
        """Sample warehouse for testing."""
        return Warehouse(
            warehouse_id=1,
            location="Test Warehouse",
            inventory=[
                InventoryItem(product_id=1, quantity=10),
                InventoryItem(product_id=2, quantity=5),
            ],
        )

    def test_import_document_post_updates_inventory(
        self,
        document_service,
        mock_warehouse_repo,
        mock_product_repo,
        mock_inventory_repo,
    ):
        """Posting import document adds to total inventory and warehouse."""
        from app.domain.entities.warehouse import Warehouse

        mock_warehouse_repo.get.return_value = Warehouse(
            warehouse_id=1, location="Test Warehouse"
        )
        mock_product = Mock()
        mock_product.product_id = 100
        mock_product.price = 25.0
        mock_product_repo.get.return_value = mock_product
        # Prepare: create import document
        doc = document_service.create_import_document(
            to_warehouse_id=1,
            items=[{"product_id": 100, "quantity": 10, "unit_price": 25.0}],
            created_by="tester",
        )
        # Act: post document
        document_service.post_document(doc.document_id, approved_by="manager")
        # Assert: warehouse and total inventory updated
        mock_inventory_repo.add_quantity.assert_called_once_with(100, 10)
        mock_warehouse_repo.add_product_to_warehouse.assert_called_once_with(1, 100, 10)

    def test_import_document_validation_error(
        self, document_service, mock_warehouse_repo, mock_product_repo
    ):
        """Creating import document with invalid quantity fails."""
        mock_warehouse_repo.get.return_value = Warehouse(
            warehouse_id=1, location="Test Warehouse"
        )
        mock_product_repo.get.return_value = Mock(product_id=100)
        with pytest.raises(InvalidQuantityError):
            document_service.create_import_document(
                to_warehouse_id=1,
                items=[{"product_id": 100, "quantity": -5, "unit_price": 25.0}],
                created_by="tester",
            )

    def test_import_document_warehouse_not_found(
        self, document_service, mock_warehouse_repo
    ):
        """Creating import document for non-existent warehouse fails."""
        mock_warehouse_repo.get.return_value = None
        with pytest.raises(WarehouseNotFoundError):
            document_service.create_import_document(
                to_warehouse_id=999,
                items=[{"product_id": 100, "quantity": 10, "unit_price": 25.0}],
                created_by="tester",
            )

    def test_export_document_post_updates_inventory(
        self,
        document_service,
        mock_warehouse_repo,
        mock_product_repo,
        mock_inventory_repo,
    ):
        """Posting export document removes from warehouse and total inventory."""
        from app.domain.entities.warehouse import Warehouse
        from app.domain.entities.inventory import InventoryItem

        mock_warehouse_repo.get.return_value = Warehouse(
            warehouse_id=1, location="Test Warehouse"
        )
        mock_product_repo.get.return_value = Mock(product_id=100, price=25.0)
        # Simulate initial warehouse inventory
        mock_warehouse_repo.get_warehouse_inventory.return_value = [
            InventoryItem(product_id=100, quantity=10)
        ]
        doc = document_service.create_export_document(
            from_warehouse_id=1,
            items=[{"product_id": 100, "quantity": 5, "unit_price": 25.0}],
            created_by="tester",
        )
        document_service.post_document(doc.document_id, approved_by="manager")
        mock_warehouse_repo.remove_product_from_warehouse.assert_called_once_with(
            1, 100, 5
        )
        mock_inventory_repo.remove_quantity.assert_called_once_with(100, 5)

    def test_export_post_insufficient_stock(
        self, document_service, mock_warehouse_repo, mock_product_repo
    ):
        """Posting export with insufficient stock fails."""
        from app.domain.entities.warehouse import Warehouse
        from app.domain.entities.inventory import InventoryItem

        mock_warehouse_repo.get.return_value = Warehouse(
            warehouse_id=1, location="Test Warehouse"
        )
        mock_product_repo.get.return_value = Mock(product_id=100, price=25.0)
        mock_warehouse_repo.get_warehouse_inventory.return_value = [
            InventoryItem(product_id=100, quantity=10)
        ]
        doc = document_service.create_export_document(
            from_warehouse_id=1,
            items=[{"product_id": 100, "quantity": 50, "unit_price": 25.0}],
            created_by="tester",
        )
        with pytest.raises(InsufficientStockError):
            document_service.post_document(doc.document_id, approved_by="manager")

    def test_export_document_warehouse_not_found(
        self, document_service, mock_warehouse_repo, mock_product_repo
    ):
        """Creating export document for non-existent warehouse fails on creation or posting."""
        mock_warehouse_repo.get.return_value = None
        with pytest.raises(WarehouseNotFoundError):
            document_service.create_export_document(
                from_warehouse_id=999,
                items=[{"product_id": 100, "quantity": 5, "unit_price": 25.0}],
                created_by="tester",
            )

    def test_get_warehouse_inventory_success(
        self, warehouse_service, mock_warehouse_repo, mock_product_repo
    ):
        """Test getting warehouse inventory successfully."""
        # Arrange
        from app.domain.entities.inventory import InventoryItem

        mock_inventory = [
            InventoryItem(product_id=1, quantity=10),
            InventoryItem(product_id=2, quantity=5),
        ]
        mock_warehouse_repo.get_warehouse_inventory.return_value = mock_inventory

        # Mock product repo
        mock_product1 = Mock()
        mock_product1.product_id = 1
        mock_product1.name = "Product 1"
        mock_product1.price = 10.0

        mock_product2 = Mock()
        mock_product2.product_id = 2
        mock_product2.name = "Product 2"
        mock_product2.price = 20.0

        mock_product_repo.get.side_effect = (
            lambda pid: mock_product1 if pid == 1 else mock_product2
        )

        # Act
        result = warehouse_service.get_warehouse_inventory(1)

        # Assert
        assert len(result) == 2
        assert result[0].product_id == 1
        assert result[0].quantity == 10
        assert result[1].product_id == 2
        assert result[1].quantity == 5
        mock_warehouse_repo.get_warehouse_inventory.assert_called_once_with(1)

    def test_get_warehouse_inventory_not_found(
        self, warehouse_service, mock_warehouse_repo
    ):
        """Test getting inventory for non-existent warehouse."""
        # Arrange
        mock_warehouse_repo.get_warehouse_inventory.side_effect = (
            WarehouseNotFoundError("Warehouse not found")
        )

        # Act & Assert
        with pytest.raises(WarehouseNotFoundError, match="Warehouse not found"):
            warehouse_service.get_warehouse_inventory(999)

        mock_warehouse_repo.get_warehouse_inventory.assert_called_once_with(999)

    def test_create_warehouse_success(
        self, warehouse_service, mock_warehouse_repo, mock_id_generator
    ):
        """Test creating a warehouse successfully."""
        # Arrange
        mock_warehouse_repo.create_warehouse.return_value = None

        # Act
        result = warehouse_service.create_warehouse("New Warehouse")

        # Assert
        assert result.warehouse_id == 123
        assert result.location == "New Warehouse"
        assert result.inventory == []
        mock_id_generator.assert_called_once()
        mock_warehouse_repo.create_warehouse.assert_called_once()
        # Verify the warehouse passed to repo has correct data
        call_args = mock_warehouse_repo.create_warehouse.call_args[0][0]
        assert call_args.warehouse_id == 123
        assert call_args.location == "New Warehouse"

    def test_create_warehouse_validation_error(
        self, warehouse_service, mock_warehouse_repo, mock_id_generator
    ):
        """Test creating a warehouse with validation error."""
        # Act & Assert
        with pytest.raises(ValidationError, match="location must be a non-empty string"):
            warehouse_service.create_warehouse("")

        # The validation happens in the domain layer before calling the repo
        mock_id_generator.assert_called_once()
        mock_warehouse_repo.create_warehouse.assert_not_called()

    def test_create_warehouse_with_id_success(
        self, warehouse_service, mock_warehouse_repo, sample_warehouse
    ):
        """Test creating a warehouse with pre-defined ID successfully."""  # Arrange
        mock_warehouse_repo.get.return_value = None
        # Act
        warehouse_service.create_warehouse_with_id(sample_warehouse)

        # Assert
        mock_warehouse_repo.create_warehouse.assert_called_once_with(sample_warehouse)

    def test_create_warehouse_with_id_already_exists(
        self, warehouse_service, mock_warehouse_repo, sample_warehouse
    ):
        """Test creating a warehouse that already exists."""
        # Arrange
        from app.domain.exceptions import EntityAlreadyExistsError

        mock_warehouse_repo.get.return_value = sample_warehouse

        # Act & Assert
        with pytest.raises(
            EntityAlreadyExistsError, match="Warehouse with ID 1 already exists"
        ):
            warehouse_service.create_warehouse_with_id(sample_warehouse)
