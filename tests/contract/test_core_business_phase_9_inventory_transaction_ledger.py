from __future__ import annotations

from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]


# ===========================================================================
# Phase 9 – inventory transaction ledger
# ===========================================================================


class TestInventoryTransactionModel:
    def test_inventory_transaction_model_exists(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        assert model_file.exists()

    def test_inventory_transaction_model_has_transaction_type(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "transaction_type" in content

    def test_inventory_transaction_model_has_document_id(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "document_id" in content

    def test_inventory_transaction_model_has_document_line_id(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "document_line_id" in content

    def test_inventory_transaction_model_has_product_id(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "product_id" in content

    def test_inventory_transaction_model_has_warehouse_id(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "warehouse_id" in content

    def test_inventory_transaction_model_has_quantity(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "quantity" in content

    def test_inventory_transaction_model_has_user_id(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "user_id" in content

    def test_inventory_transaction_model_has_created_at(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "created_at" in content

    def test_inventory_transaction_model_has_payload(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "payload" in content

    def test_inventory_transaction_model_has_idempotency_key(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "idempotency_key" in content

    def test_inventory_transaction_model_has_unique_constraint_on_idempotency(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "UniqueConstraint" in content or "unique=True" in content

    def test_inventory_transaction_model_has_qty_before_after_fields(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory_transaction.py"
        content = model_file.read_text()
        assert "physical_qty_before" in content
        assert "physical_qty_after" in content
        assert "reserved_qty_before" in content
        assert "reserved_qty_after" in content
        assert "available_qty_before" in content
        assert "available_qty_after" in content


class TestInventoryRepoHasTransactionMethods:
    def test_inventory_repo_has_write_transaction(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "def write_transaction" in content

    def test_inventory_repo_has_list_transactions(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "def list_transactions" in content

    def test_write_transaction_has_idempotency_check(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        write_start = content.find("def write_transaction")
        write_end = content.find("\n    def ", write_start + 1)
        write_section = content[write_start:write_end]
        assert "idempotency_key" in write_section

    def test_write_transaction_checks_existing_transaction(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        write_start = content.find("def write_transaction")
        write_end = content.find("\n    def ", write_start + 1)
        write_section = content[write_start:write_end]
        assert "existing" in write_section

    def test_list_transactions_has_filtering_parameters(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        list_start = content.find("def list_transactions")
        list_end = content.find("\n    def ", list_start + 1)
        list_section = content[list_start:list_end]
        assert "document_id" in list_section
        assert "product_id" in list_section
        assert "warehouse_id" in list_section
        assert "transaction_type" in list_section


class TestInventoryRepoInterfaceHasTransactionMethods:
    def test_interface_has_write_transaction(self) -> None:
        interface_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/domain/interfaces/inventory_repo.py"
        content = interface_file.read_text()
        assert "write_transaction" in content

    def test_interface_has_list_transactions(self) -> None:
        interface_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/domain/interfaces/inventory_repo.py"
        content = interface_file.read_text()
        assert "list_transactions" in content


class TestPhase9Migration:
    def test_migration_file_exists(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase9_add_inventory_transactions.sql"
        assert migration_file.exists()

    def test_migration_creates_inventory_transactions_table(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase9_add_inventory_transactions.sql"
        content = migration_file.read_text()
        assert "CREATE TABLE inventory_transactions" in content

    def test_migration_has_all_required_columns(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase9_add_inventory_transactions.sql"
        content = migration_file.read_text()
        assert "transaction_type" in content
        assert "document_id" in content
        assert "document_line_id" in content
        assert "product_id" in content
        assert "warehouse_id" in content
        assert "quantity" in content
        assert "user_id" in content
        assert "created_at" in content
        assert "payload" in content
        assert "idempotency_key" in content

    def test_migration_has_idempotency_unique_constraint(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase9_add_inventory_transactions.sql"
        content = migration_file.read_text()
        assert "UNIQUE" in content or "unique" in content

    def test_migration_has_indexes(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase9_add_inventory_transactions.sql"
        content = migration_file.read_text()
        assert "CREATE INDEX" in content


class TestProtoHasTransactionRPC:
    def test_proto_has_list_transactions_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "rpc ListTransactions" in content

    def test_proto_has_transaction_row_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "message TransactionRow" in content

    def test_proto_has_list_transactions_request(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "message ListTransactionsRequest" in content

    def test_proto_has_list_transactions_response(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "message ListTransactionsResponse" in content

    def test_transaction_row_has_all_fields(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "transaction_type" in content
        assert "document_id" in content
        assert "product_id" in content
        assert "warehouse_id" in content
        assert "quantity" in content
        assert "idempotency_key" in content


class TestGrpcServicerHasListTransactions:
    def test_servicer_has_list_transactions_method(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "def ListTransactions" in content

    def test_servicer_calls_repo_list_transactions(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        list_start = content.find("def ListTransactions")
        list_end = content.find("\n    def ", list_start + 1)
        list_section = content[list_start:list_end]
        assert "list_transactions" in list_section


class TestRestApiHasTransactionsEndpoint:
    def test_routes_has_transactions_endpoint(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/inventory/transactions"' in content

    def test_transactions_endpoint_calls_list_transactions_grpc(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        trans_section = content[content.find('"/inventory/transactions"'):content.find('"/users"', content.find('"/inventory/transactions"'))]
        assert "ListTransactions" in trans_section


class TestPhase9BackwardCompatibility:
    def test_old_movement_ledger_still_exists(self) -> None:
        model_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/movement_ledger.py"
        assert model_file.exists()

    def test_movement_ledger_model_still_in_init(self) -> None:
        init_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/__init__.py"
        content = init_file.read_text()
        assert "InventoryMovementLedgerModel" in content

    def test_old_reservation_methods_still_exist(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "create_reservation" in content
        assert "release_reservation" in content
        assert "consume_reservation" in content

    def test_old_inventory_methods_still_exist(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "def save" in content
        assert "def add_quantity" in content
        assert "def get_quantity" in content

    def test_proto_retains_old_rpcs(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "rpc ListInventoryItems" in content
        assert "rpc GetAvailability" in content
        assert "rpc ListReservations" in content
