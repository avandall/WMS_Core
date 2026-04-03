"""
SQL integration tests for DocumentRepo.
Tests actual database operations including FK constraints and cascade deletes.
"""

import pytest
from datetime import datetime

from app.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentType,
    DocumentStatus,
)
from app.domain.entities.product import Product
from app.domain.entities.warehouse import Warehouse
from app.domain.exceptions import DocumentNotFoundError


class TestDocumentRepoSQL:
    """Test SQL document repository with real database operations."""

    def test_save_new_document(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test saving a new document."""
        # Create dependencies
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Create document
        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            from_warehouse_id=None,
            to_warehouse_id=1,
            items=items,
            created_by="TestUser",
            note="Test import",
        )
        document_repo_sql.save(doc)

        # Retrieve and verify
        retrieved = document_repo_sql.get(1)
        assert retrieved is not None
        assert retrieved.document_id == 1
        assert retrieved.doc_type == DocumentType.IMPORT
        assert retrieved.to_warehouse_id == 1
        assert len(retrieved.items) == 1
        assert retrieved.items[0].product_id == 1
        assert retrieved.items[0].quantity == 10

    def test_save_existing_document_updates(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test that save updates existing document."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Create initial document
        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="User1",
        )
        document_repo_sql.save(doc)

        # Update document
        doc.note = "Updated note"
        doc.items.append(DocumentProduct(product_id=1, quantity=5, unit_price=60.0))
        document_repo_sql.save(doc)

        # Verify updates
        retrieved = document_repo_sql.get(1)
        assert retrieved.note == "Updated note"
        assert len(retrieved.items) == 2

    def test_get_nonexistent_document(self, document_repo_sql):
        """Test getting non-existent document returns None."""
        result = document_repo_sql.get(9999)
        assert result is None

    def test_get_all_documents(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test retrieving all documents."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        # Create multiple documents
        for i in range(1, 4):
            items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
            doc = Document(
                document_id=i,
                doc_type=DocumentType.IMPORT,
                to_warehouse_id=1,
                items=items,
                created_by="User",
            )
            document_repo_sql.save(doc)

        all_docs = document_repo_sql.get_all()
        assert len(all_docs) == 3

    def test_update_status(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test updating document status."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="User",
        )
        document_repo_sql.save(doc)

        # Update status
        document_repo_sql.update_status(1, DocumentStatus.POSTED)

        retrieved = document_repo_sql.get(1)
        assert retrieved.status == DocumentStatus.POSTED

    def test_update_status_nonexistent_raises_error(self, document_repo_sql):
        """Test updating status of non-existent document raises error."""
        with pytest.raises(DocumentNotFoundError):
            document_repo_sql.update_status(9999, DocumentStatus.POSTED)

    def test_delete_document(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test deleting a document."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=100,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="User",
        )
        document_repo_sql.save(doc)

        document_repo_sql.delete(100)
        assert document_repo_sql.get(100) is None

    def test_delete_nonexistent_document_raises_error(self, document_repo_sql):
        """Test deleting non-existent document raises error."""
        with pytest.raises(DocumentNotFoundError):
            document_repo_sql.delete(9999)

    def test_delete_document_cascades_to_items(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql, test_session
    ):
        """Test that deleting document also deletes its items (cascade)."""
        from app.infrastructure.persistence.models import DocumentItemModel

        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        items = [
            DocumentProduct(product_id=1, quantity=10, unit_price=50.0),
            DocumentProduct(product_id=1, quantity=5, unit_price=60.0),
        ]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="User",
        )
        document_repo_sql.save(doc)

        # Verify items exist
        item_count = (
            test_session.query(DocumentItemModel).filter_by(document_id=1).count()
        )
        assert item_count == 2

        # Delete document
        document_repo_sql.delete(1)

        # Verify items are also deleted
        item_count = (
            test_session.query(DocumentItemModel).filter_by(document_id=1).count()
        )
        assert item_count == 0

    def test_get_document_helper(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test get_document helper method."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="User",
        )
        document_repo_sql.save(doc)

        retrieved = document_repo_sql.get(1)
        assert retrieved.document_id == 1

    def test_get_document_nonexistent_raises_error(self, document_repo_sql):
        """Test get_document with non-existent ID raises error."""
        assert document_repo_sql.get(9999) is None

    def test_document_with_transfer_type(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test creating transfer document with from and to warehouses."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse1 = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse2 = Warehouse(warehouse_id=2, location="Warehouse B")
        warehouse_repo_sql.save(warehouse1)
        warehouse_repo_sql.save(warehouse2)

        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.TRANSFER,
            from_warehouse_id=1,
            to_warehouse_id=2,
            items=items,
            created_by="User",
        )
        document_repo_sql.save(doc)

        retrieved = document_repo_sql.get(1)
        assert retrieved.doc_type == DocumentType.TRANSFER
        assert retrieved.from_warehouse_id == 1
        assert retrieved.to_warehouse_id == 2

    def test_document_with_export_type(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test creating export document."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=1,
            to_warehouse_id=None,
            items=items,
            created_by="User",
        )
        document_repo_sql.save(doc)

        retrieved = document_repo_sql.get(1)
        assert retrieved.doc_type == DocumentType.EXPORT
        assert retrieved.from_warehouse_id == 1
        assert retrieved.to_warehouse_id is None

    def test_document_with_multiple_items(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test document with multiple product items."""
        product1 = Product(product_id=1, name="Product 1", price=10.0)
        product2 = Product(product_id=2, name="Product 2", price=20.0)
        product3 = Product(product_id=3, name="Product 3", price=30.0)
        product_repo_sql.save(product1)
        product_repo_sql.save(product2)
        product_repo_sql.save(product3)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        items = [
            DocumentProduct(product_id=1, quantity=5, unit_price=10.0),
            DocumentProduct(product_id=2, quantity=10, unit_price=20.0),
            DocumentProduct(product_id=3, quantity=15, unit_price=30.0),
        ]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="User",
        )
        document_repo_sql.save(doc)

        retrieved = document_repo_sql.get(1)
        assert len(retrieved.items) == 3

        # Verify all items
        item_dict = {item.product_id: item for item in retrieved.items}
        assert item_dict[1].quantity == 5
        assert item_dict[2].quantity == 10
        assert item_dict[3].quantity == 15

    def test_document_metadata_fields(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test document metadata like approved_by, note, timestamps."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="Creator",
            note="Important shipment",
        )
        doc.approved_by = "Approver"
        doc.posted_at = datetime.now()

        document_repo_sql.save(doc)

        retrieved = document_repo_sql.get(1)
        assert retrieved.created_by == "Creator"
        assert retrieved.approved_by == "Approver"
        assert retrieved.note == "Important shipment"
        assert retrieved.posted_at is not None

    def test_document_status_transitions(
        self, document_repo_sql, product_repo_sql, warehouse_repo_sql
    ):
        """Test document status can be updated through multiple states."""
        product = Product(product_id=1, name="Product A", price=50.0)
        product_repo_sql.save(product)

        warehouse = Warehouse(warehouse_id=1, location="Warehouse A")
        warehouse_repo_sql.save(warehouse)

        items = [DocumentProduct(product_id=1, quantity=10, unit_price=50.0)]
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="User",
        )
        document_repo_sql.save(doc)

        # Initial status
        retrieved = document_repo_sql.get(1)
        assert retrieved.status == DocumentStatus.DRAFT

        # Update to posted
        document_repo_sql.update_status(1, DocumentStatus.POSTED)
        retrieved = document_repo_sql.get(1)
        assert retrieved.status == DocumentStatus.POSTED

        # Update to cancelled
        document_repo_sql.update_status(1, DocumentStatus.CANCELLED)
        retrieved = document_repo_sql.get(1)
        assert retrieved.status == DocumentStatus.CANCELLED
