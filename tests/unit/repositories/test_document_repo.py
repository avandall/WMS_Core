"""
Comprehensive Unit Tests for DocumentRepo
Covers all DocumentRepo methods, validation, edge cases, and database operations
"""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from sqlalchemy.orm import Session
from typing import List, Optional

from app.modules.documents.infrastructure.repositories.document_repo import DocumentRepo
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType
)
from app.shared.domain.business_exceptions import DocumentNotFoundError
# Use mock models to avoid SQLAlchemy dependency issues
try:
    from app.infrastructure.persistence.models import DocumentModel, DocumentItemModel
    REAL_MODELS_AVAILABLE = True
except ImportError:
    from tests.mocks.models import MockDocumentModel as DocumentModel
    from tests.mocks.models import MockDocumentItemModel as DocumentItemModel
    REAL_MODELS_AVAILABLE = False



class TestDocumentRepo:
    """Test Document Repository Implementation"""

    # ============================================================================
    # SETUP TESTS
    # ============================================================================

    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        session = Mock(spec=Session)
        session.get = Mock()
        session.add = Mock()
        session.delete = Mock()
        session.execute = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session

    @pytest.fixture
    def document_repo(self, mock_session):
        """DocumentRepo instance with mocked session"""
        return DocumentRepo(session=mock_session)

    @pytest.fixture
    def sample_document(self):
        """Sample document for testing"""
        items = [DocumentProduct(product_id=1, quantity=10, unit_price=99.99)]
        return Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="admin",
            note="Test Note"
        )

    @pytest.fixture
    def sample_document_model(self):
        """Sample DocumentModel for testing"""
        # Create a simple mock to avoid SQLAlchemy relationship issues
        model = Mock(spec=DocumentModel)
        model.document_id = 1
        model.doc_type = "IMPORT"
        model.status = "DRAFT"
        model.from_warehouse_id = None
        model.to_warehouse_id = 1
        model.created_by = "admin"
        model.approved_by = None
        model.note = "Test Note"
        model.customer_id = None
        model.items = []
        return model

    @pytest.fixture
    def sample_document_item_model(self):
        """Sample DocumentItemModel for testing"""
        # Create a mock DocumentItemModel with required attributes
        mock_item = Mock(spec=DocumentItemModel)
        mock_item.product_id = 1
        mock_item.quantity = 10
        mock_item.unit_price = 99.99
        return mock_item

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_document_repo_initialization(self, mock_session):
        """Test DocumentRepo initialization"""
        repo = DocumentRepo(session=mock_session)
        
        assert repo.session == mock_session
        assert repo._auto_commit is False

    @patch('app.modules.documents.infrastructure.repositories.document_repo.IDGenerator')
    def test_sync_id_generator_with_existing_document(self, mock_id_generator, document_repo, mock_session):
        """Test _sync_id_generator with existing document"""
        # Mock session.execute to return max_id
        mock_result = Mock()
        mock_result.scalar.return_value = 100
        mock_session.execute.return_value = mock_result
        
        # Create repo to trigger _sync_id_generator
        DocumentRepo(session=mock_session)
        
        # Verify IDGenerator was called with correct start_id
        mock_id_generator.reset_generator.assert_called_once_with("document", 101)

    @patch('app.modules.documents.infrastructure.repositories.document_repo.IDGenerator')
    def test_sync_id_generator_no_existing_document(self, mock_id_generator, document_repo, mock_session):
        """Test _sync_id_generator with no existing document"""
        # Mock session.execute to return None
        mock_result = Mock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Create repo to trigger _sync_id_generator
        DocumentRepo(session=mock_session)
        
        # Verify IDGenerator was called with start_id=1
        mock_id_generator.reset_generator.assert_called_once_with("document", 1)

    # ============================================================================
    # SAVE TESTS
    # ============================================================================

    def test_save_new_document(self, document_repo, mock_session, sample_document):
        """Test save method with new document"""
        # Mock session.get to return None (document doesn't exist)
        mock_session.get.return_value = None
        
        document_repo.save(sample_document)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(DocumentModel, 1)
        
        # Verify session.add was called (new document)
        assert mock_session.add.call_count >= 1  # Document + items
        
        # Verify commit was not called (auto_commit=False)
        mock_session.commit.assert_not_called()

    def test_save_existing_document(self, document_repo, mock_session, sample_document, sample_document_model):
        """Test save method with existing document"""
        # Mock session.get to return existing document
        mock_session.get.return_value = sample_document_model
        
        # Patch DocumentItemModel to avoid AuditLogModel relationship issues
        with patch('app.modules.documents.infrastructure.repositories.document_repo.DocumentItemModel') as mock_item_model:
            mock_item_model.return_value = Mock()
            
            document_repo.save(sample_document)
        
        # For existing documents, session.add is NOT called (only for new documents)
        # The repository updates the existing model directly
        # Verify session.get was called to find the existing document
        mock_session.get.assert_called_once()
        
        # Verify the existing model was updated by checking the mock
        assert sample_document_model.doc_type == "IMPORT"
        assert sample_document_model.status == "DRAFT"
        assert sample_document_model.created_by == "admin"
        assert sample_document_model.note == "Test Note"

    def test_save_document_with_items(self, document_repo, mock_session, sample_document):
        """Test save method with document having items"""
        # Mock session.get to return None (new document)
        mock_session.get.return_value = None
        
        document_repo.save(sample_document)
        
        # Verify document was added (items are added to document's collection, not session individually)
        assert mock_session.add.call_count >= 1  # Document
        
        # Check that the document model was added with items
        add_calls = mock_session.add.call_args_list
        document_model_call = add_calls[0]
        added_document = document_model_call[0][0]
        
        # Verify the document has the expected items
        assert len(added_document.items) >= 1
        added_item = added_document.items[0]
        assert added_item.product_id == 1
        assert added_item.quantity == 10
        assert added_item.unit_price == 99.99

    def test_save_document_with_auto_commit(self, document_repo, mock_session, sample_document):
        """Test save method with auto_commit enabled"""
        # Create repo with auto_commit
        repo = DocumentRepo(session=mock_session)
        repo._auto_commit = True
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        repo.save(sample_document)
        
        # Verify commit was called (auto_commit=True)
        mock_session.commit.assert_called_once()

    def test_save_document_clears_existing_items(self, document_repo, mock_session, sample_document, sample_document_model):
        """Test save method clears existing items before adding new ones"""
        # Mock session.get to return existing document with items
        existing_item = DocumentItemModel(product_id=2, quantity=5, unit_price=49.99)
        sample_document_model.items = [existing_item]
        mock_session.get.return_value = sample_document_model
        
        document_repo.save(sample_document)
        
        # Verify old items were cleared and new items were added
        assert len(sample_document_model.items) == 1  # New item from sample_document
        # Verify it's the new item, not the old one
        new_item = sample_document_model.items[0]
        assert new_item.product_id == 1  # From sample_document
        assert new_item.quantity == 10   # From sample_document
        assert new_item.unit_price == 99.99  # From sample_document

    def test_save_document_with_all_fields(self, document_repo, mock_session):
        """Test save method with document having all fields"""
        # Create document with all fields
        items = [DocumentProduct(product_id=1, quantity=10, unit_price=99.99)]
        document = Document(
            document_id=1,
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=1,
            to_warehouse_id=2,
            items=items,
            created_by="admin",
            note="Test Note",
            customer_id=123
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        document_repo.save(document)
        
        # Verify all fields were set
        add_calls = mock_session.add.call_args_list
        document_model_call = add_calls[0]
        added_document = document_model_call[0][0]
        
        assert added_document.doc_type == "EXPORT"
        assert added_document.from_warehouse_id == 1
        assert added_document.to_warehouse_id == 2
        assert added_document.created_by == "admin"
        # approved_by is not a field in Document entity, removed this assertion
        assert added_document.note == "Test Note"
        assert added_document.customer_id == 123

    # ============================================================================
    # GET TESTS
    # ============================================================================

    def test_get_document_found(self, document_repo, mock_session, sample_document_model):
        """Test get method when document is found"""
        # Mock session.get to return document model
        mock_session.get.return_value = sample_document_model
        
        result = document_repo.get(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(DocumentModel, 1)
        
        # Verify result
        assert result is not None
        assert result.document_id == 1
        assert result.doc_type == DocumentType.IMPORT
        assert result.status == DocumentStatus.DRAFT

    def test_get_document_not_found(self, document_repo, mock_session):
        """Test get method when document is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        result = document_repo.get(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(DocumentModel, 1)
        
        # Verify result
        assert result is None

    def test_get_document_with_items(self, document_repo, mock_session, sample_document_model, sample_document_item_model):
        """Test get method when document has items"""
        # Mock session.get to return document model with items
        sample_document_model.items = [sample_document_item_model]
        mock_session.get.return_value = sample_document_model
        
        result = document_repo.get(1)
        
        # Verify result contains items
        assert len(result.items) == 1
        assert result.items[0].product_id == 1
        assert result.items[0].quantity == 10
        assert result.items[0].unit_price == 99.99

    # ============================================================================
    # GET ALL TESTS
    # ============================================================================

    def test_get_all_success(self, document_repo, mock_session):
        """Test get_all method successful retrieval"""
        # Create sample models with proper warehouse configurations and all required attributes
        document_model1 = DocumentModel(document_id=1, doc_type="IMPORT", status="DRAFT", 
                                      from_warehouse_id=None, to_warehouse_id=1, created_by="admin")
        document_model2 = DocumentModel(document_id=2, doc_type="EXPORT", status="POSTED",
                                      from_warehouse_id=1, to_warehouse_id=None, created_by="admin")
        
        # Mock session.execute to return models
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [document_model1, document_model2]
        mock_session.execute.return_value = mock_result
        
        result = document_repo.get_all()
        
        # Verify session.execute was called (may be called multiple times in implementation)
        assert mock_session.execute.call_count >= 1
        
        # Verify result
        assert len(result) == 2
        assert result[0].document_id == 1
        assert result[0].doc_type == DocumentType.IMPORT
        assert result[1].document_id == 2
        assert result[1].doc_type == DocumentType.EXPORT

    def test_get_all_empty(self, document_repo, mock_session):
        """Test get_all method with no documents"""
        # Mock session.execute to return empty list
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = document_repo.get_all()
        
        # Verify result
        assert result == []

    def test_get_all_with_items(self, document_repo, mock_session, sample_document_item_model):
        """Test get_all method with documents having items"""
        # Create models with items - use mock models to avoid SQLAlchemy relationship issues
        document_model1 = Mock(spec=DocumentModel)
        document_model1.document_id = 1
        document_model1.doc_type = "IMPORT"
        document_model1.status = "DRAFT"
        document_model1.from_warehouse_id = None
        document_model1.to_warehouse_id = 1
        document_model1.created_by = "admin"
        document_model1.items = [sample_document_item_model]
        
        document_model2 = Mock(spec=DocumentModel)
        document_model2.document_id = 2
        document_model2.doc_type = "EXPORT"
        document_model2.status = "POSTED"
        document_model2.from_warehouse_id = 1
        document_model2.to_warehouse_id = None
        document_model2.created_by = "admin"
        document_model2.items = []
        
        # Mock session.execute to return models
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [document_model1, document_model2]
        mock_session.execute.return_value = mock_result
        
        result = document_repo.get_all()
        
        # Verify result contains items for first document
        assert len(result) == 2
        assert len(result[0].items) == 1
        assert len(result[1].items) == 0

    # ============================================================================
    # UPDATE STATUS TESTS
    # ============================================================================

    def test_update_status_success(self, document_repo, mock_session, sample_document_model):
        """Test update_status method successful update"""
        # Mock session.get to return document model
        mock_session.get.return_value = sample_document_model
        
        document_repo.update_status(1, DocumentStatus.POSTED)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(DocumentModel, 1)
        
        # Verify status was updated
        assert sample_document_model.status == "POSTED"

    def test_update_status_document_not_found(self, document_repo, mock_session):
        """Test update_status method when document is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        with pytest.raises(DocumentNotFoundError, match="Document 1 not found"):
            document_repo.update_status(1, DocumentStatus.POSTED)

    def test_update_status_all_statuses(self, document_repo, mock_session, sample_document_model):
        """Test update_status method with all possible statuses"""
        statuses = [DocumentStatus.DRAFT, DocumentStatus.POSTED, DocumentStatus.CANCELLED]
        
        # Mock session.get to return document model
        mock_session.get.return_value = sample_document_model
        
        for status in statuses:
            document_repo.update_status(1, status)
            assert sample_document_model.status == status.value

    # ============================================================================
    # DELETE TESTS
    # ============================================================================

    def test_delete_document_success(self, document_repo, mock_session, sample_document_model):
        """Test delete method successful deletion"""
        # Mock session.get to return document model
        mock_session.get.return_value = sample_document_model
        
        document_repo.delete(1)
        
        # Verify session.get was called
        mock_session.get.assert_called_once_with(DocumentModel, 1)
        
        # Verify session.delete was called
        mock_session.delete.assert_called_once_with(sample_document_model)

    def test_delete_document_not_found(self, document_repo, mock_session):
        """Test delete method when document is not found"""
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        with pytest.raises(DocumentNotFoundError, match="Document 1 not found"):
            document_repo.delete(1)

    def test_delete_document_with_auto_commit(self, document_repo, mock_session, sample_document_model):
        """Test delete method with auto_commit enabled"""
        # Create repo with auto_commit
        repo = DocumentRepo(session=mock_session)
        repo._auto_commit = True
        
        # Mock session.get to return document model
        mock_session.get.return_value = sample_document_model
        
        repo.delete(1)
        
        # Verify commit was called (auto_commit=True)
        mock_session.commit.assert_called_once()

    # ============================================================================
    # TO DOMAIN TESTS
    # ============================================================================

    def test_to_domain_conversion(self, sample_document_item_model):
        """Test _to_domain static method"""
        # Create document model with items - use mock to avoid SQLAlchemy relationship issues
        document_model = Mock(spec=DocumentModel)
        document_model.document_id = 1
        document_model.doc_type = "IMPORT"
        document_model.status = "DRAFT"
        document_model.from_warehouse_id = None
        document_model.to_warehouse_id = 1
        document_model.created_by = "admin"
        document_model.approved_by = None
        document_model.note = "Test Note"
        document_model.customer_id = None
        document_model.items = [sample_document_item_model]
        
        result = DocumentRepo._to_domain(document_model)
        
        # Verify conversion
        assert result.document_id == 1
        assert result.doc_type == DocumentType.IMPORT
        assert result.status == DocumentStatus.DRAFT
        assert result.from_warehouse_id is None
        assert result.to_warehouse_id == 1
        assert result.created_by == "admin"
        assert result.approved_by is None
        assert result.note == "Test Note"
        assert result.customer_id is None
        assert len(result.items) == 1
        assert result.items[0].product_id == 1
        assert result.items[0].quantity == 10
        assert result.items[0].unit_price == 99.99

    def test_to_domain_conversion_empty_items(self):
        """Test _to_domain static method with empty items"""
        # Create document model without items
        document_model = DocumentModel(
            document_id=1,
            doc_type="IMPORT",
            status="DRAFT",
            from_warehouse_id=None,
            to_warehouse_id=1,
            created_by="admin",
            approved_by=None,
            note="Test Note",
            customer_id=None
        )
        document_model.items = []
        
        result = DocumentRepo._to_domain(document_model)
        
        # Verify conversion
        assert len(result.items) == 0

    def test_to_domain_conversion_all_document_types(self, sample_document_item_model):
        """Test _to_domain static method with all document types"""
        document_types = [DocumentType.IMPORT, DocumentType.EXPORT, DocumentType.SALE, DocumentType.TRANSFER]
        
        for doc_type in document_types:
            # Use mock models to avoid SQLAlchemy relationship issues
            document_model = Mock(spec=DocumentModel)
            document_model.document_id = 1
            document_model.doc_type = doc_type.value
            document_model.status = "DRAFT"
            document_model.from_warehouse_id = 1 if doc_type != DocumentType.IMPORT else None
            document_model.to_warehouse_id = 2 if doc_type == DocumentType.TRANSFER else (1 if doc_type != DocumentType.EXPORT else None)
            document_model.created_by = "admin"
            document_model.approved_by = None
            document_model.note = "Test Note"
            document_model.customer_id = None
            document_model.items = [sample_document_item_model]
            
            result = DocumentRepo._to_domain(document_model)
            
            # Verify conversion
            assert result.doc_type == doc_type

    def test_to_domain_conversion_all_statuses(self, sample_document_item_model):
        """Test _to_domain static method with all document statuses"""
        statuses = [DocumentStatus.DRAFT, DocumentStatus.POSTED, DocumentStatus.CANCELLED]
        
        for status in statuses:
            # Use mock models to avoid SQLAlchemy relationship issues
            document_model = Mock(spec=DocumentModel)
            document_model.document_id = 1
            document_model.doc_type = "IMPORT"
            document_model.status = status.value
            document_model.from_warehouse_id = None
            document_model.to_warehouse_id = 1
            document_model.created_by = "admin"
            document_model.approved_by = None
            document_model.note = "Test Note"
            document_model.customer_id = None
            document_model.items = [sample_document_item_model]
            
            result = DocumentRepo._to_domain(document_model)
            
            # Verify conversion
            assert result.status == status

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    def test_save_then_get_integration(self, document_repo, mock_session, sample_document):
        """Test integration between save and get methods"""
        # Mock session.get to return None first, then document model
        document_model = DocumentModel(
            document_id=1,
            doc_type="IMPORT",
            status="DRAFT",
            from_warehouse_id=None,
            to_warehouse_id=1,
            created_by="admin",
            approved_by=None,
            note="Test Note",
            customer_id=None
        )
        mock_session.get.side_effect = [None, document_model]
        
        # Save document
        document_repo.save(sample_document)
        
        # Get document
        result = document_repo.get(1)
        
        # Verify result
        assert result is not None
        assert result.document_id == 1
        assert result.doc_type == DocumentType.IMPORT

    def test_save_then_update_status_integration(self, document_repo, mock_session, sample_document):
        """Test integration between save and update_status methods"""
        # Mock session.get to return None first, then document model
        document_model = DocumentModel(
            document_id=1,
            doc_type="IMPORT",
            status="DRAFT",
            from_warehouse_id=None,
            to_warehouse_id=1,
            created_by="admin",
            approved_by=None,
            note="Test Note",
            customer_id=None
        )
        mock_session.get.side_effect = [None, document_model, document_model]
        
        # Save document
        document_repo.save(sample_document)
        
        # Update status
        document_repo.update_status(1, DocumentStatus.POSTED)
        
        # Verify status was updated
        assert document_model.status == "POSTED"

    def test_save_then_delete_integration(self, document_repo, mock_session, sample_document):
        """Test integration between save and delete methods"""
        # Mock session.get to return None first, then document model
        document_model = DocumentModel(
            document_id=1,
            doc_type="IMPORT",
            status="DRAFT",
            from_warehouse_id=None,
            to_warehouse_id=1,
            created_by="admin",
            approved_by=None,
            note="Test Note",
            customer_id=None
        )
        mock_session.get.side_effect = [None, document_model]
        
        # Save document
        document_repo.save(sample_document)
        
        # Delete document
        document_repo.delete(1)
        
        # Verify delete was called
        mock_session.delete.assert_called_once()

    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================

    def test_save_document_with_unicode_data(self, document_repo, mock_session):
        """Test save method with Unicode data"""
        items = [DocumentProduct(product_id=1, quantity=10, unit_price=99.99)]
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="Üñïçødé Üsér",
            note="Üñïçødé nëtë"
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        document_repo.save(document)
        
        # Check added document model
        add_calls = mock_session.add.call_args_list
        document_model_call = add_calls[0]
        added_document = document_model_call[0][0]
        assert added_document.created_by == "Üñïçødé Üsér"
        assert added_document.note == "Üñïçødé nëtë"

    def test_save_document_with_special_characters(self, document_repo, mock_session):
        """Test save method with special characters"""
        items = [DocumentProduct(product_id=1, quantity=10, unit_price=99.99)]
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="user@company.com",
            note="Special chars: !@#$%^&*()"
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        document_repo.save(document)
        
        # Check added document model
        add_calls = mock_session.add.call_args_list
        document_model_call = add_calls[0]
        added_document = document_model_call[0][0]
        assert added_document.created_by == "user@company.com"
        assert added_document.note == "Special chars: !@#$%^&*()"

    def test_save_document_with_large_id(self, document_repo, mock_session):
        """Test save method with large document ID"""
        items = [DocumentProduct(product_id=1, quantity=10, unit_price=99.99)]
        document = Document(
            document_id=2147483647,  # Max int
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="admin"
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        document_repo.save(document)
        
        # Check added document model
        add_calls = mock_session.add.call_args_list
        document_model_call = add_calls[0]
        added_document = document_model_call[0][0]
        assert added_document.document_id == 2147483647

    def test_save_document_with_many_items(self, document_repo, mock_session):
        """Test save method with many items"""
        items = [
            DocumentProduct(product_id=1, quantity=10, unit_price=99.99),
            DocumentProduct(product_id=2, quantity=20, unit_price=49.99),
            DocumentProduct(product_id=3, quantity=30, unit_price=29.99),
        ]
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="admin"
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        document_repo.save(document)
        
        # Verify document was added (items are added to document's collection, not session individually)
        assert mock_session.add.call_count >= 1  # Document

    def test_operations_with_decimal_prices(self, document_repo, mock_session):
        """Test operations with decimal prices"""
        items = [DocumentProduct(product_id=1, quantity=10, unit_price=99.999)]
        document = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            items=items,
            created_by="admin"
        )
        
        # Mock session.get to return None
        mock_session.get.return_value = None
        
        document_repo.save(document)
        
        # Check that the document was saved with decimal prices
        # Items are added to document's collection, not session individually
        assert mock_session.add.call_count >= 1
        # The decimal price should be preserved in the document domain object
        assert document.items[0].unit_price == 99.999

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_save_database_error_handling(self, document_repo, mock_session, sample_document):
        """Test save method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            document_repo.save(sample_document)

    def test_get_database_error_handling(self, document_repo, mock_session):
        """Test get method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            document_repo.get(1)

    def test_get_all_database_error_handling(self, document_repo, mock_session):
        """Test get_all method handles database errors gracefully"""
        # Mock session.execute to raise exception
        mock_session.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            document_repo.get_all()

    def test_update_status_database_error_handling(self, document_repo, mock_session):
        """Test update_status method handles database errors gracefully"""
        # Mock session.get to raise exception
        mock_session.get.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            document_repo.update_status(1, DocumentStatus.POSTED)

    def test_delete_database_error_handling(self, document_repo, mock_session, sample_document_model):
        """Test delete method handles database errors gracefully"""
        # Mock session.get to return document model
        mock_session.get.return_value = sample_document_model
        
        # Mock session.delete to raise exception
        mock_session.delete.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            document_repo.delete(1)
