"""
Unit tests for DocumentRepo.
"""

import pytest
from app.infrastructure.persistence.repositories.document_repo import DocumentRepo
from app.domain.entities.document import Document, DocumentType, DocumentStatus
from app.domain.exceptions import DocumentNotFoundError


class TestDocumentRepo:
    """Test cases for DocumentRepo."""

    @pytest.fixture(autouse=True)
    def setup(self, test_session):
        """Set up test fixtures with SQL session."""
        self.repo = DocumentRepo(test_session)

    def test_save_and_get_document(self):
        """Test saving and retrieving a document."""
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="test_user",
        )

        self.repo.save(doc)
        retrieved = self.repo.get(1)

        assert retrieved is not None
        assert retrieved.document_id == 1
        assert retrieved.doc_type == DocumentType.IMPORT
        assert retrieved.status == DocumentStatus.DRAFT

    def test_get_nonexistent_document(self):
        """Test getting a nonexistent document returns None."""
        result = self.repo.get(999)
        assert result is None

    def test_get_all_documents(self):
        """Test getting all documents."""
        doc1 = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user1",
        )
        doc2 = Document(
            document_id=2,
            doc_type=DocumentType.EXPORT,
            from_warehouse_id=1,
            created_by="user2",
        )

        self.repo.save(doc1)
        self.repo.save(doc2)

        all_docs = self.repo.get_all()
        assert len(all_docs) == 2
        assert all_docs[0].document_id in [1, 2]
        assert all_docs[1].document_id in [1, 2]

    def test_get_all_empty_repo(self):
        """Test getting all documents from empty repo returns empty list."""
        all_docs = self.repo.get_all()
        assert all_docs == []

    def test_update_status_existing_document(self):
        """Test updating status of existing document."""
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        self.repo.save(doc)

        self.repo.update_status(1, DocumentStatus.POSTED)
        updated = self.repo.get(1)
        assert updated.status == DocumentStatus.POSTED

    def test_update_status_nonexistent_document(self):
        """Test updating status of nonexistent document raises DocumentNotFoundError."""
        with pytest.raises(DocumentNotFoundError, match="Document 999 not found"):
            self.repo.update_status(999, DocumentStatus.POSTED)

    def test_delete_existing_document(self):
        """Test deleting an existing document."""
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        self.repo.save(doc)

        self.repo.delete(1)
        assert self.repo.get(1) is None

    def test_delete_nonexistent_document(self):
        """Test deleting a nonexistent document raises DocumentNotFoundError."""
        with pytest.raises(DocumentNotFoundError, match="Document 999 not found"):
            self.repo.delete(999)

    def test_get_document_existing(self):
        """Test getting document details for existing document."""
        doc = Document(
            document_id=1,
            doc_type=DocumentType.IMPORT,
            to_warehouse_id=1,
            created_by="user",
        )
        self.repo.save(doc)

        retrieved = self.repo.get(1)
        assert retrieved.document_id == 1
        assert retrieved.doc_type == DocumentType.IMPORT

    def test_get_document_nonexistent(self):
        """Test getting document details for nonexistent document returns None."""
        result = self.repo.get(999)
        assert result is None
