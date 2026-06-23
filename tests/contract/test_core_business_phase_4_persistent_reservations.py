from __future__ import annotations

from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]


# ===========================================================================
# Phase 4 – persistent reservations
# ===========================================================================


class TestStockReservationModelExists:
    def test_stock_reservation_model_file_exists(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/stock_reservation.py"
        assert model_file.exists()

    def test_model_has_required_fields(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/stock_reservation.py"
        content = model_file.read_text()
        assert "source_type" in content
        assert "source_id" in content
        assert "document_id" in content
        assert "product_id" in content
        assert "warehouse_id" in content
        assert "requested_qty" in content
        assert "reserved_qty" in content
        assert "released_qty" in content
        assert "consumed_qty" in content
        assert "status" in content
        assert "idempotency_key" in content

    def test_model_has_unique_constraint_for_idempotency(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/stock_reservation.py"
        content = model_file.read_text()
        assert "idempotency_key" in content
        assert "unique=True" in content or "UniqueConstraint" in content


class TestPhase4MigrationScriptExists:
    def test_migration_sql_file_exists(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase4_add_stock_reservations.sql"
        assert migration_file.exists()

    def test_migration_creates_stock_reservations_table(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase4_add_stock_reservations.sql"
        content = migration_file.read_text()
        assert "CREATE TABLE stock_reservations" in content

    def test_migration_adds_indexes(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase4_add_stock_reservations.sql"
        content = migration_file.read_text()
        assert "CREATE INDEX" in content
        assert "ix_stock_reservations_product_warehouse" in content

    def test_migration_adds_unique_constraint_for_idempotency(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase4_add_stock_reservations.sql"
        content = migration_file.read_text()
        assert "idempotency_key" in content
        assert "UNIQUE" in content


class TestInventoryRepoHasReservationMethods:
    def test_repo_has_create_reservation_method(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "def create_reservation" in content

    def test_repo_has_release_reservation_method(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "def release_reservation" in content

    def test_repo_has_consume_reservation_method(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "def consume_reservation" in content

    def test_repo_has_list_reservations_method(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "def list_reservations" in content

    def test_repo_has_calculate_available_stock_method(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "def calculate_available_stock" in content


class TestInventoryRepoImplementsATPCheck:
    def test_create_reservation_checks_available_stock(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "available_qty" in content
        assert "InsufficientStockError" in content

    def test_create_reservation_updates_reserved_qty(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "reserved_qty +=" in content

    def test_release_reservation_updates_reserved_qty(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "reserved_qty -=" in content


class TestInventoryRepoImplementsIdempotency:
    def test_create_reservation_checks_idempotency_key(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "idempotency_key" in content
        assert "existing" in content


class TestInventoryServiceUsesPersistentReservations:
    def test_reserve_stock_calls_create_reservation(self) -> None:
        service_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py"
        content = service_file.read_text()
        assert "create_reservation" in content

    def test_reserve_stock_uses_idempotency_key(self) -> None:
        service_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py"
        content = service_file.read_text()
        assert "idempotency_key" in content

    def test_release_reservation_calls_repo_release(self) -> None:
        service_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py"
        content = service_file.read_text()
        assert "release_reservation" in content


class TestInventoryRepoInterfaceHasReservationMethods:
    def test_interface_has_create_reservation(self) -> None:
        interface_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/domain/interfaces/inventory_repo.py"
        content = interface_file.read_text()
        assert "create_reservation" in content

    def test_interface_has_release_reservation(self) -> None:
        interface_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/domain/interfaces/inventory_repo.py"
        content = interface_file.read_text()
        assert "release_reservation" in content

    def test_interface_has_consume_reservation(self) -> None:
        interface_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/domain/interfaces/inventory_repo.py"
        content = interface_file.read_text()
        assert "consume_reservation" in content

    def test_interface_has_list_reservations(self) -> None:
        interface_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/domain/interfaces/inventory_repo.py"
        content = interface_file.read_text()
        assert "list_reservations" in content

    def test_interface_has_calculate_available_stock(self) -> None:
        interface_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/domain/interfaces/inventory_repo.py"
        content = interface_file.read_text()
        assert "calculate_available_stock" in content


class TestPhase4BackwardCompatibility:
    def test_reserve_stock_still_records_movement_event(self) -> None:
        service_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py"
        content = service_file.read_text()
        assert "_record_movement" in content
        assert "StockReserved" in content

    def test_release_reservation_still_records_movement_event(self) -> None:
        service_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py"
        content = service_file.read_text()
        assert "ReservationReleased" in content
