from __future__ import annotations

from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]


# ===========================================================================
# Phase 3 – inventory read API shows availability
# ===========================================================================


class TestProtoFileHasQuantityMatrixFields:
    def test_proto_warehouse_inventory_row_has_physical_qty(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "physical_qty" in content

    def test_proto_warehouse_inventory_row_has_reserved_qty(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "reserved_qty" in content

    def test_proto_warehouse_inventory_row_has_incoming_qty(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "incoming_qty" in content

    def test_proto_warehouse_inventory_row_has_in_transit_qty(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "in_transit_qty" in content

    def test_proto_warehouse_inventory_row_has_available_qty(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "available_qty" in content

    def test_proto_retains_legacy_quantity_field(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "int64 quantity = 4;" in content


class TestGrpcServicerIncludesQuantityMatrixFields:
    def test_grpc_servicer_passes_physical_qty(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "physical_qty" in content

    def test_grpc_servicer_passes_reserved_qty(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "reserved_qty" in content

    def test_grpc_servicer_passes_incoming_qty(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "incoming_qty" in content

    def test_grpc_servicer_passes_in_transit_qty(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "in_transit_qty" in content

    def test_grpc_servicer_passes_available_qty(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "available_qty" in content


class TestRestApiIncludesQuantityMatrixFields:
    def test_rest_routes_passes_physical_qty(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"physical_qty"' in content

    def test_rest_routes_passes_reserved_qty(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"reserved_qty"' in content

    def test_rest_routes_passes_incoming_qty(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"incoming_qty"' in content

    def test_rest_routes_passes_in_transit_qty(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"in_transit_qty"' in content

    def test_rest_routes_passes_available_qty(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"available_qty"' in content

    def test_rest_routes_retains_legacy_quantity_field(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"quantity": int(r.quantity)' in content


class TestInventoryRepoCalculatesAvailableQty:
    def test_repo_calculates_available_qty(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        assert "available_qty" in content
        assert "physical_qty" in content
        assert "reserved_qty" in content


class TestPhase3BackwardCompatibility:
    def test_repo_still_returns_quantity(self) -> None:
        repo_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py"
        content = repo_file.read_text()
        # Ensure the old quantity field is still returned
        assert '"quantity": int(row.quantity)' in content

    def test_grpc_servicer_uses_defaults_for_new_fields(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        # Ensure servicer uses .get() with defaults for backward compatibility
        assert 'r.get("physical_qty"' in content
        assert 'r.get("available_qty"' in content
