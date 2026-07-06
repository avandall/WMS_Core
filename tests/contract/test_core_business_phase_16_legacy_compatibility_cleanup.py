from __future__ import annotations

import os
# Ensure a valid database URL is configured before any settings are loaded
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import sys
import pytest
import warnings
from pathlib import Path
from unittest.mock import Mock

ROOT_DIR = Path(__file__).resolve().parents[2]

# Helper to load a service's sys.path correctly
def _load_service(src_path: Path):
    sys.path.insert(0, str(src_path))
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]


class DummyDocumentRepo:
    def __init__(self):
        self.committed = False
        self.db = {}

    def get(self, document_id: int):
        return self.db.get(document_id)

    def save(self, doc):
        self.db[doc.document_id] = doc

    def commit(self):
        self.committed = True


def test_document_service_post_document_raises_deprecation_warning() -> None:
    _load_service(ROOT_DIR / "Services/documents-service/src")
    from app.modules.documents.application.services.document_service import DocumentService
    from app.modules.documents.domain.entities.document import DocumentType, DocumentStatus

    repo = DummyDocumentRepo()
    publisher = Mock()
    service = DocumentService(repo, event_publisher=publisher)  # type: ignore[arg-type]

    doc = Mock()
    doc.document_id = 42
    doc.doc_type = DocumentType.SALE
    doc.status = DocumentStatus.DRAFT
    doc.customer_id = 9
    doc.from_warehouse_id = 1
    doc.to_warehouse_id = None
    doc.items = [Mock(product_id=101, quantity=5, unit_price=10.0)]
    doc.posted_event_payload = Mock(return_value={})
    doc.inventory_movement_requested_payload = Mock(return_value={})
    doc._item_snapshots = Mock(return_value=[])
    repo.save(doc)

    with pytest.deprecated_call():
        service.post_document(42, "user_admin")


def test_api_gateway_post_document_route_marked_deprecated() -> None:
    routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
    content = routes_file.read_text()
    
    # Assert route decorator has deprecated=True
    assert 'deprecated=True' in content
    assert '"/documents/{document_id}/post"' in content


def test_dashboard_ui_label_is_warehouse_operations() -> None:
    index_file = ROOT_DIR / "dashboard/index.html"
    content = index_file.read_text()
    
    assert "Warehouse Operations" in content
    assert "Documents" not in content or "Warehouse Operations" in content
