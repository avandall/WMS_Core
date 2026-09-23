"""
Unit tests for Document State Machine & State Transition Enforcement — TASK-022
Validates blocking illegal transitions (confirm_execution when not IN_PROGRESS, direct cancel on RESERVED/IN_PROGRESS/EXECUTED).
"""

from unittest.mock import MagicMock
import pytest

from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.shared.domain.business_exceptions import InvalidDocumentStatusError


@pytest.fixture
def mock_document_repo():
    repo = MagicMock()
    repo._store = {}

    def mock_get(doc_id):
        return repo._store.get(doc_id)

    def mock_save(doc):
        repo._store[doc.document_id] = doc

    repo.get.side_effect = mock_get
    repo.save.side_effect = mock_save
    return repo


@pytest.fixture
def document_service(mock_document_repo):
    return DocumentService(document_repo=mock_document_repo)


def create_sample_document(document_id: int = 1, status: DocumentStatus = DocumentStatus.DRAFT) -> Document:
    item = DocumentProduct(product_id=101, quantity=10, unit_price=25.0)
    doc = Document(
        document_id=document_id,
        doc_type=DocumentType.SALE,
        from_warehouse_id=1,
        items=[item],
        created_by="test_user",
    )
    doc.status = status
    return doc


def test_confirm_execution_rejected_when_executed(document_service, mock_document_repo):
    """
    TASK-022 Requirement:
    `confirm_execution` must raise InvalidDocumentStatusError if document status is EXECUTED.
    Prevents double deduction (BIZ-16 / FLOW-01).
    """
    doc = create_sample_document(document_id=10, status=DocumentStatus.EXECUTED)
    mock_document_repo._store[10] = doc

    items_payload = [{"product_id": 101, "quantity": 10}]
    with pytest.raises(InvalidDocumentStatusError) as exc_info:
        document_service.confirm_execution(document_id=10, items=items_payload)

    assert "must be IN_PROGRESS" in str(exc_info.value) or "EXECUTED" in str(exc_info.value)


@pytest.mark.parametrize("invalid_status", [
    DocumentStatus.DRAFT,
    DocumentStatus.POSTED,
    DocumentStatus.RESERVED,
    DocumentStatus.COMPLETED,
    DocumentStatus.CANCELLED,
])
def test_confirm_execution_rejected_when_not_in_progress(document_service, mock_document_repo, invalid_status):
    """
    TASK-022 Requirement:
    `confirm_execution` must raise InvalidDocumentStatusError if document status != IN_PROGRESS.
    """
    doc = create_sample_document(document_id=20, status=invalid_status)
    mock_document_repo._store[20] = doc

    items_payload = [{"product_id": 101, "quantity": 10}]
    with pytest.raises(InvalidDocumentStatusError):
        document_service.confirm_execution(document_id=20, items=items_payload)


def test_confirm_execution_success_when_in_progress(document_service, mock_document_repo):
    """
    `confirm_execution` succeeds when document status is IN_PROGRESS.
    """
    doc = create_sample_document(document_id=30, status=DocumentStatus.IN_PROGRESS)
    mock_document_repo._store[30] = doc

    items_payload = [{"product_id": 101, "quantity": 10}]
    confirmed_doc = document_service.confirm_execution(document_id=30, items=items_payload)

    assert confirmed_doc.status == DocumentStatus.EXECUTED
    assert confirmed_doc.items[0].executed_qty == 10


def test_cancel_rejected_when_in_progress_without_release_flow():
    """
    TASK-022 Requirement:
    Direct call to `doc.cancel()` on IN_PROGRESS document without release flow raises InvalidDocumentStatusError.
    """
    doc = create_sample_document(document_id=40, status=DocumentStatus.IN_PROGRESS)
    with pytest.raises(InvalidDocumentStatusError) as exc_info:
        doc.cancel(cancelled_by="admin", reason="Direct cancel attempt", from_release_flow=False)

    assert "without release flow" in str(exc_info.value)


def test_cancel_rejected_when_reserved_without_release_flow():
    """
    TASK-022 Requirement:
    Direct call to `doc.cancel()` on RESERVED document without release flow raises InvalidDocumentStatusError.
    """
    doc = create_sample_document(document_id=50, status=DocumentStatus.RESERVED)
    with pytest.raises(InvalidDocumentStatusError) as exc_info:
        doc.cancel(cancelled_by="admin", reason="Direct cancel attempt", from_release_flow=False)

    assert "without release flow" in str(exc_info.value)


def test_cancel_rejected_when_executed():
    """
    TASK-022 Requirement:
    `doc.cancel()` on EXECUTED document raises InvalidDocumentStatusError even if from_release_flow=True.
    """
    doc = create_sample_document(document_id=60, status=DocumentStatus.EXECUTED)
    with pytest.raises(InvalidDocumentStatusError) as exc_info:
        doc.cancel(cancelled_by="admin", reason="Cancel executed doc", from_release_flow=True)

    assert "Cannot cancel document" in str(exc_info.value)


def test_cancel_rejected_when_completed():
    """
    `doc.cancel()` on COMPLETED document raises InvalidDocumentStatusError.
    """
    doc = create_sample_document(document_id=70, status=DocumentStatus.COMPLETED)
    with pytest.raises(InvalidDocumentStatusError):
        doc.cancel(cancelled_by="admin", reason="Cancel completed doc", from_release_flow=True)


def test_cancel_allowed_for_draft():
    """
    Direct `doc.cancel()` on DRAFT document succeeds.
    """
    doc = create_sample_document(document_id=80, status=DocumentStatus.DRAFT)
    doc.cancel(cancelled_by="user_1", reason="No longer needed")

    assert doc.status == DocumentStatus.CANCELLED
    assert doc.cancelled_by == "user_1"
    assert doc.cancellation_reason == "No longer needed"


def test_cancel_allowed_with_release_flow():
    """
    `doc.cancel(..., from_release_flow=True)` on RESERVED or IN_PROGRESS document succeeds.
    """
    doc_res = create_sample_document(document_id=90, status=DocumentStatus.RESERVED)
    doc_res.cancel(cancelled_by="system", reason="Released via saga", from_release_flow=True)
    assert doc_res.status == DocumentStatus.CANCELLED

    doc_prog = create_sample_document(document_id=91, status=DocumentStatus.IN_PROGRESS)
    doc_prog.cancel(cancelled_by="system", reason="Released via saga", from_release_flow=True)
    assert doc_prog.status == DocumentStatus.CANCELLED
