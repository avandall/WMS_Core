"""
Unit tests for Document domain entities.
"""

import pytest
from app.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentType,
    DocumentStatus,
)
from app.domain.exceptions import (
    ValidationError,
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidDocumentStatusError,
    InvalidQuantityError,
    InvalidIDError,
)


class TestDocumentProduct:
    """Test cases for DocumentProduct domain entity."""

    def test_document_product_creation_valid(self):
        """Test creating a document product with valid data."""
        product = DocumentProduct(product_id=1, quantity=10, unit_price=25.50)

        assert product.product_id == 1
        assert product.quantity == 10
        assert product.unit_price == 25.50

    @pytest.mark.parametrize("invalid_id", [0, -1, "1", None, 1.5])
    def test_document_product_invalid_product_id(self, invalid_id):
        """Test creating document product with invalid product ID."""
        with pytest.raises(
            InvalidIDError, match="product_id must be a positive integer"
        ):
            DocumentProduct(product_id=invalid_id, quantity=5, unit_price=10.0)

    @pytest.mark.parametrize("invalid_quantity", [0, -1, -5, "10", None, 1.5])
    def test_document_product_invalid_quantity(self, invalid_quantity):
        """Test creating document product with invalid quantity."""
        with pytest.raises(
            InvalidQuantityError, match="quantity must be a positive integer"
        ):
            DocumentProduct(product_id=1, quantity=invalid_quantity, unit_price=10.0)

    @pytest.mark.parametrize("invalid_price", [-1, -0.01, "10", None])
    def test_document_product_invalid_unit_price(self, invalid_price):
        """Test creating document product with invalid unit price."""
        with pytest.raises(
            InvalidQuantityError, match="unit_price must be a non-negative number"
        ):
            DocumentProduct(product_id=1, quantity=5, unit_price=invalid_price)

    def test_calculate_total_value(self):
        """Test calculating total value."""
        product = DocumentProduct(product_id=1, quantity=10, unit_price=25.50)

        assert product.calculate_total_value() == 255.0

    def test_string_representation(self):
        """Test string representation of document product."""
        product = DocumentProduct(product_id=1, quantity=10, unit_price=25.50)

        expected = "DocumentProduct(product_id=1, quantity=10, unit_price=25.5)"
        assert str(product) == expected
        assert repr(product) == expected


class TestDocument:
    """Test cases for Document domain entity."""

    def test_document_creation_import_valid(self):
        """Test creating an import document with valid data."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user1",
        )

        assert document.document_id == 1
        assert document.doc_type == DocumentType.IMPORT
        assert document.status == DocumentStatus.DRAFT
        assert document.from_warehouse_id is None
        assert document.to_warehouse_id == 1
        assert document.items == []
        assert document.created_by == "user1"
        assert document.approved_by is None

    def test_document_creation_export_valid(self):
        """Test creating an export document with valid data."""
        document = Document(
            document_id=2,
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=1,
            created_by="user1",
        )

        assert document.document_id == 2
        assert document.doc_type == DocumentType.EXPORT
        assert document.from_warehouse_id == 1
        assert document.to_warehouse_id is None

    def test_document_creation_transfer_valid(self):
        """Test creating a transfer document with valid data."""
        document = Document(
            document_id=3,
            doc_type=DocumentType.TRANSFER,
            from_warehouse_id=1,
            to_warehouse_id=2,
            created_by="user1",
        )

        assert document.document_id == 3
        assert document.doc_type == DocumentType.TRANSFER
        assert document.from_warehouse_id == 1
        assert document.to_warehouse_id == 2

    def test_document_creation_with_items(self):
        """Test creating a document with initial items."""
        items = [
            DocumentProduct(product_id=1, quantity=10, unit_price=25.0),
            DocumentProduct(product_id=2, quantity=5, unit_price=15.0),
        ]
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="user1",
        )

        assert len(document.items) == 2
        assert document.items[0].product_id == 1
        assert document.items[1].product_id == 2

    @pytest.mark.parametrize("invalid_id", [0, -1, "1", None, 1.5])
    def test_document_invalid_id(self, invalid_id):
        """Test creating document with invalid ID."""
        with pytest.raises(
            InvalidIDError, match="document_id must be a positive integer"
        ):
            Document(
                document_id=invalid_id,
                doc_type=DocumentType.IMPORT,
                to_warehouse_id=1,
                created_by="user",
            )

    def test_document_invalid_type(self):
        """Test creating document with invalid type."""
        with pytest.raises(ValidationError, match="doc_type must be a valid DocumentType"):
            Document(
                document_id=1, doc_type="INVALID", to_warehouse_id=1, created_by="user"
            )

    def test_document_import_missing_destination(self):
        """Test creating import document without destination warehouse."""
        with pytest.raises(
            ValidationError, match="IMPORT documents require a destination warehouse"
        ):
            Document(document_id=1, doc_type=DocumentType.IMPORT, created_by="user")

    def test_document_export_missing_source(self):
        """Test creating export document without source warehouse."""
        with pytest.raises(
            ValidationError, match="EXPORT and SALE documents require a source warehouse"
        ):
            Document(document_id=1, doc_type=DocumentType.EXPORT, created_by="user")

    def test_document_transfer_missing_warehouses(self):
        """Test creating transfer document with missing warehouses."""
        with pytest.raises(
            ValidationError, match="TRANSFER documents require both source and destination warehouses"
        ):
            Document(
                document_id=1,
                doc_type=DocumentType.TRANSFER,
                from_warehouse_id=1,
                created_by="user",
            )

    def test_document_transfer_same_warehouse(self):
        """Test creating transfer document with same source and destination."""
        with pytest.raises(
            BusinessRuleViolationError, match="TRANSFER documents cannot use the same warehouse for source and destination"
        ):
            Document(
                document_id=1,
                doc_type=DocumentType.TRANSFER,
                from_warehouse_id=1,
                to_warehouse_id=1,
                created_by="user",
            )

    @pytest.mark.parametrize("invalid_created_by", ["", "   ", None])
    def test_document_invalid_created_by(self, invalid_created_by):
        """Test creating document with invalid created_by."""
        with pytest.raises(ValidationError, match="created_by must be a non-empty string"):
            Document(
                document_id=1,
                doc_type=DocumentType.IMPORT,
                to_warehouse_id=1,
                created_by=invalid_created_by,
            )

    def test_add_item_valid(self):
        """Test adding an item to document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)

        document.add_item(item)

        assert len(document.items) == 1
        assert document.items[0] == item

    def test_add_item_duplicate_product(self):
        """Test adding duplicate product to document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item1 = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        item2 = DocumentProduct(product_id=1, quantity=5, unit_price=20.0)

        document.add_item(item1)

        with pytest.raises(
            BusinessRuleViolationError, match="Product 1 already exists in document"
        ):
            document.add_item(item2)

    def test_add_item_posted_document(self):
        """Test adding item to posted document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)
        document.post("approver")

        with pytest.raises(
            InvalidDocumentStatusError, match="Cannot modify document 1 when not in DRAFT status"
        ):
            document.add_item(
                DocumentProduct(product_id=2, quantity=5, unit_price=15.0)
            )

    def test_remove_item_valid(self):
        """Test removing an item from document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)

        document.remove_item(product_id=1)

        assert len(document.items) == 0

    def test_remove_item_not_found(self):
        """Test removing non-existent item from document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )

        with pytest.raises(
            EntityNotFoundError, match="Product 1 not found in document"
        ):
            document.remove_item(product_id=1)

    def test_remove_item_posted_document(self):
        """Test removing item from posted document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)
        document.post("approver")

        with pytest.raises(InvalidDocumentStatusError):
            document.remove_item(product_id=1)

    def test_update_item_valid(self):
        """Test updating an item in document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)

        document.update_item(product_id=1, quantity=15, unit_price=30.0)

        assert document.items[0].quantity == 15
        assert document.items[0].unit_price == 30.0

    def test_update_item_not_found(self):
        """Test updating non-existent item in document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )

        with pytest.raises(
            EntityNotFoundError, match="Product 1 not found in document"
        ):
            document.update_item(product_id=1, quantity=15, unit_price=30.0)

    def test_update_item_posted_document(self):
        """Test updating item in posted document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)
        document.post("approver")

        with pytest.raises(InvalidDocumentStatusError):
            document.update_item(product_id=1, quantity=15, unit_price=30.0)

    def test_post_document_valid(self):
        """Test posting a document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)

        document.post("approver")

        assert document.status == DocumentStatus.POSTED
        assert document.approved_by == "approver"

    def test_post_document_no_items(self):
        """Test posting document without items."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )

        with pytest.raises(
            BusinessRuleViolationError, match="Cannot post document without items"
        ):
            document.post("approver")

    def test_post_document_invalid_approver(self):
        """Test posting document with invalid approver."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)

        with pytest.raises(ValidationError, match="approved_by must be a non-empty string"):
            document.post("")

    def test_post_document_already_posted(self):
        """Test posting already posted document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)
        document.post("approver")

        with pytest.raises(
            InvalidDocumentStatusError, match="Document 1 is not in DRAFT status"
        ):
            document.post("another_approver")

    def test_cancel_document_draft(self):
        """Test canceling a draft document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )

        document.cancel()

        assert document.status == DocumentStatus.CANCELLED

    def test_cancel_document_posted(self):
        """Test canceling a posted document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        item = DocumentProduct(product_id=1, quantity=10, unit_price=25.0)
        document.add_item(item)
        document.post("approver")

        with pytest.raises(
            InvalidDocumentStatusError, match="Cannot cancel a posted document 1"
        ):
            document.cancel()

    def test_calculate_total_value(self):
        """Test calculating total value of document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        document.add_item(DocumentProduct(product_id=1, quantity=10, unit_price=25.0))
        document.add_item(DocumentProduct(product_id=2, quantity=5, unit_price=15.0))

        assert document.calculate_total_value() == 325.0  # (10*25) + (5*15)

    def test_get_summary(self):
        """Test getting document summary."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user1",
            note="Test note",
        )
        document.add_item(DocumentProduct(product_id=1, quantity=10, unit_price=25.0))

        summary = document.get_summary()

        assert summary["document_id"] == 1
        assert summary["type"] == "IMPORT"
        assert summary["status"] == "DRAFT"
        assert summary["from_warehouse"] is None
        assert summary["to_warehouse"] == 1
        assert summary["total_items"] == 1
        assert summary["total_quantity"] == 10
        assert summary["total_value"] == 250.0
        assert summary["created_by"] == "user1"
        assert summary["approved_by"] is None

    def test_can_be_modified(self):
        """Test checking if document can be modified."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )

        assert document.can_be_modified() is True

        document.cancel()
        assert document.can_be_modified() is False

    def test_string_representation(self):
        """Test string representation of document."""
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        document.add_item(DocumentProduct(product_id=1, quantity=10, unit_price=25.0))

        expected = "Document(id=1, type=IMPORT, status=DRAFT, items=1)"
        assert str(document) == expected
        assert repr(document) == expected

    def test_equality(self):
        """Test document equality based on ID."""
        document1 = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        document2 = Document(
            document_id=1,
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=1,
            created_by="user",
        )
        document3 = Document(
            document_id=2,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )

        assert document1 == document2
        assert document1 != document3
        assert document1 != "not a document"

    def test_hash(self):
        """Test document hash based on ID."""
        document1 = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        document2 = Document(
            document_id=1,
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=1,
            created_by="user",
        )
        document3 = Document(
            document_id=2,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )

        assert hash(document1) == hash(document2)
        assert hash(document1) != hash(document3)
