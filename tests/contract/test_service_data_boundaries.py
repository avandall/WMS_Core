from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_audit_service_owns_audit_events_without_cross_service_foreign_keys() -> None:
    model_path = (
        ROOT_DIR
        / "Services/audit-service/src/app/modules/audit/infrastructure/models/audit_event.py"
    )
    source = model_path.read_text()

    assert 'ForeignKey("users.' not in source
    assert 'ForeignKey("warehouses.' not in source
    assert "relationship(\"UserModel" not in source
    assert "relationship(\"WarehouseModel" not in source


def test_audit_service_imports_only_owned_models_for_db_initialization() -> None:
    database_path = ROOT_DIR / "Services/audit-service/src/app/shared/core/database.py"
    source = database_path.read_text()

    assert "app.modules.audit.infrastructure.models.audit_event" in source
    assert "app.modules.users.infrastructure.models.user" not in source
    assert "app.modules.warehouses.infrastructure.models.warehouse" not in source
