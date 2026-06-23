from __future__ import annotations

from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]


# ===========================================================================
# Phase 5 – reservation API and minimal UI visibility
# ===========================================================================


class TestProtoFileHasReservationMessages:
    def test_proto_has_get_availability_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "rpc GetAvailability" in content

    def test_proto_has_list_reservations_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "rpc ListReservations" in content

    def test_proto_has_release_reservation_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "rpc ReleaseReservation" in content

    def test_proto_has_get_availability_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "message GetAvailabilityRequest" in content
        assert "message GetAvailabilityResponse" in content

    def test_proto_has_reservation_row_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "message ReservationRow" in content

    def test_proto_has_list_reservations_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "message ListReservationsRequest" in content
        assert "message ListReservationsResponse" in content

    def test_proto_has_release_reservation_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "message ReleaseReservationRequest" in content
        assert "message ReleaseReservationResponse" in content


class TestGrpcServicerHasReservationMethods:
    def test_servicer_has_get_availability(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "def GetAvailability" in content

    def test_servicer_has_list_reservations(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "def ListReservations" in content

    def test_servicer_has_release_reservation(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "def ReleaseReservation" in content

    def test_servicer_calls_calculate_available_stock(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "calculate_available_stock" in content

    def test_servicer_calls_list_reservations(self) -> None:
        servicer_file = ROOT_DIR / "Services/inventory-service/src/inventory_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "list_reservations" in content


class TestRestApiHasReservationEndpoints:
    def test_routes_has_get_availability_endpoint(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/inventory/availability"' in content

    def test_routes_has_list_reservations_endpoint(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/inventory/reservations"' in content

    def test_routes_has_release_reservation_endpoint(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/inventory/reservations/{reservation_id}/release"' in content

    def test_availability_endpoint_returns_physical_qty(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"physical_qty"' in content

    def test_availability_endpoint_returns_reserved_qty(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"reserved_qty"' in content

    def test_availability_endpoint_returns_available_qty(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"available_qty"' in content


class TestDashboardShowsQuantityMatrix:
    def test_dashboard_script_shows_physical_column(self) -> None:
        script_file = ROOT_DIR / "dashboard/script.js"
        content = script_file.read_text()
        assert "Physical" in content

    def test_dashboard_script_shows_reserved_column(self) -> None:
        script_file = ROOT_DIR / "dashboard/script.js"
        content = script_file.read_text()
        assert "Reserved" in content

    def test_dashboard_script_shows_available_column(self) -> None:
        script_file = ROOT_DIR / "dashboard/script.js"
        content = script_file.read_text()
        assert "Available" in content

    def test_dashboard_script_uses_physical_qty_field(self) -> None:
        script_file = ROOT_DIR / "dashboard/script.js"
        content = script_file.read_text()
        assert "physical_qty" in content

    def test_dashboard_script_uses_reserved_qty_field(self) -> None:
        script_file = ROOT_DIR / "dashboard/script.js"
        content = script_file.read_text()
        assert "reserved_qty" in content

    def test_dashboard_script_uses_available_qty_field(self) -> None:
        script_file = ROOT_DIR / "dashboard/script.js"
        content = script_file.read_text()
        assert "available_qty" in content

    def test_dashboard_script_has_backward_compatibility_fallback(self) -> None:
        script_file = ROOT_DIR / "dashboard/script.js"
        content = script_file.read_text()
        assert "??" in content  # Nullish coalescing for fallbacks


class TestPhase5BackwardCompatibility:
    def test_proto_retains_legacy_rpcs(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "rpc ListInventoryItems" in content
        assert "rpc GetInventoryByWarehouse" in content
        assert "rpc GetProductQuantity" in content

    def test_dashboard_retains_legacy_quantity_column(self) -> None:
        script_file = ROOT_DIR / "dashboard/script.js"
        content = script_file.read_text()
        assert "item.quantity" in content  # Fallback for backward compatibility

    def test_routes_retains_legacy_inventory_endpoints(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/inventory"' in content
        assert '"/inventory/by-warehouse"' in content
        assert '"/inventory/{product_id}"' in content
