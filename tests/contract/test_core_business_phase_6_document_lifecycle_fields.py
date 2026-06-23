from __future__ import annotations

from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]


# ===========================================================================
# Phase 6 – document lifecycle fields
# ===========================================================================


class TestDocumentModelHasLifecycleFields:
    def test_document_model_has_transaction_type(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document.py"
        content = model_file.read_text()
        assert "transaction_type" in content

    def test_document_model_has_reason_code(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document.py"
        content = model_file.read_text()
        assert "reason_code" in content

    def test_document_model_has_requested_by(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document.py"
        content = model_file.read_text()
        assert "requested_by" in content

    def test_document_model_has_approved_at(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document.py"
        content = model_file.read_text()
        assert "approved_at" in content

    def test_document_model_has_execution_started_at(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document.py"
        content = model_file.read_text()
        assert "execution_started_at" in content

    def test_document_model_has_completed_at(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document.py"
        content = model_file.read_text()
        assert "completed_at" in content

    def test_document_model_has_assigned_to(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document.py"
        content = model_file.read_text()
        assert "assigned_to" in content


class TestDocumentItemModelHasLifecycleFields:
    def test_document_item_model_has_requested_qty(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document_item.py"
        content = model_file.read_text()
        assert "requested_qty" in content

    def test_document_item_model_has_reserved_qty(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document_item.py"
        content = model_file.read_text()
        assert "reserved_qty" in content

    def test_document_item_model_has_executed_qty(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document_item.py"
        content = model_file.read_text()
        assert "executed_qty" in content

    def test_document_item_model_has_rejected_qty(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document_item.py"
        content = model_file.read_text()
        assert "rejected_qty" in content

    def test_document_item_model_has_difference_qty(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document_item.py"
        content = model_file.read_text()
        assert "difference_qty" in content

    def test_document_item_model_has_execution_status(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document_item.py"
        content = model_file.read_text()
        assert "execution_status" in content


class TestDocumentEntityHasLifecycleFields:
    def test_document_entity_has_transaction_type(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "transaction_type" in content

    def test_document_entity_has_reason_code(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "reason_code" in content

    def test_document_entity_has_requested_by(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "requested_by" in content

    def test_document_entity_has_approved_at(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "approved_at" in content

    def test_document_entity_has_execution_started_at(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "execution_started_at" in content

    def test_document_entity_has_completed_at(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "completed_at" in content

    def test_document_entity_has_assigned_to(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "assigned_to" in content


class TestDocumentProductEntityHasLifecycleFields:
    def test_document_product_has_requested_qty(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "requested_qty" in content

    def test_document_product_has_reserved_qty(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "reserved_qty" in content

    def test_document_product_has_executed_qty(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "executed_qty" in content

    def test_document_product_has_rejected_qty(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "rejected_qty" in content

    def test_document_product_has_difference_qty(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "difference_qty" in content

    def test_document_product_has_execution_status(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "execution_status" in content

    def test_document_product_requested_qty_defaults_to_quantity(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "requested_qty: int = quantity" in content


class TestPhase6MigrationScript:
    def test_migration_file_exists(self) -> None:
        migration_file = ROOT_DIR / "Services/documents-service/migrations/phase6_add_document_lifecycle_fields.sql"
        assert migration_file.exists()

    def test_migration_adds_document_header_fields(self) -> None:
        migration_file = ROOT_DIR / "Services/documents-service/migrations/phase6_add_document_lifecycle_fields.sql"
        content = migration_file.read_text()
        assert "transaction_type" in content
        assert "reason_code" in content
        assert "requested_by" in content
        assert "approved_at" in content
        assert "execution_started_at" in content
        assert "completed_at" in content
        assert "assigned_to" in content

    def test_migration_adds_document_line_fields(self) -> None:
        migration_file = ROOT_DIR / "Services/documents-service/migrations/phase6_add_document_lifecycle_fields.sql"
        content = migration_file.read_text()
        assert "requested_qty" in content
        assert "reserved_qty" in content
        assert "executed_qty" in content
        assert "rejected_qty" in content
        assert "difference_qty" in content
        assert "execution_status" in content

    def test_migration_backfills_requested_qty(self) -> None:
        migration_file = ROOT_DIR / "Services/documents-service/migrations/phase6_add_document_lifecycle_fields.sql"
        content = migration_file.read_text()
        assert "UPDATE document_items SET requested_qty = quantity" in content

    def test_migration_adds_indexes(self) -> None:
        migration_file = ROOT_DIR / "Services/documents-service/migrations/phase6_add_document_lifecycle_fields.sql"
        content = migration_file.read_text()
        assert "CREATE INDEX" in content


class TestPhase6BackwardCompatibility:
    def test_document_model_retains_old_fields(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document.py"
        content = model_file.read_text()
        assert "doc_type" in content
        assert "status" in content
        assert "posted_at" in content

    def test_document_item_model_retains_old_fields(self) -> None:
        model_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/infrastructure/models/document_item.py"
        content = model_file.read_text()
        assert "quantity" in content
        assert "unit_price" in content

    def test_document_entity_retains_old_fields(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "doc_type" in content
        assert "status" in content
        assert "quantity" in content

    def test_document_product_retains_old_fields(self) -> None:
        entity_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/domain/entities/document.py"
        content = entity_file.read_text()
        assert "quantity" in content
        assert "unit_price" in content
