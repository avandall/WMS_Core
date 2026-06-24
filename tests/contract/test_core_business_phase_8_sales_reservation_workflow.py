from __future__ import annotations

from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]


# ===========================================================================
# Phase 8 – sales reservation workflow
# ===========================================================================


class TestDocumentServiceHasReservationMethods:
    def test_document_service_has_reserve_request_stock(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "def reserve_request_stock" in content

    def test_document_service_has_release_request_reservation(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "def release_request_reservation" in content

    def test_reserve_request_stock_only_for_sale_documents(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        reserve_start = content.find("def reserve_request_stock")
        reserve_end = content.find("\n    def ", reserve_start + 1)
        reserve_section = content[reserve_start:reserve_end]
        assert "SALE" in reserve_section

    def test_reserve_request_stock_updates_reserved_qty(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        reserve_start = content.find("def reserve_request_stock")
        reserve_end = content.find("\n    def ", reserve_start + 1)
        reserve_section = content[reserve_start:reserve_end]
        assert "reserved_qty" in reserve_section

    def test_reserve_request_stock_emits_stock_reserved_event(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        reserve_start = content.find("def reserve_request_stock")
        reserve_end = content.find("\n    def ", reserve_start + 1)
        reserve_section = content[reserve_start:reserve_end]
        assert "StockReserved" in reserve_section

    def test_release_request_reservation_emits_reservation_released_event(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        release_start = content.find("def release_request_reservation")
        release_end = content.find("\n    def ", release_start + 1)
        release_section = content[release_start:release_end]
        assert "ReservationReleased" in release_section


class TestProtoHasReservationRPCs:
    def test_proto_has_reserve_request_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "rpc ReserveRequest" in content

    def test_proto_has_release_reservation_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "rpc ReleaseReservation" in content

    def test_proto_has_reserve_request_request_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "message ReserveRequestRequest" in content

    def test_proto_has_reserve_request_response_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "message ReserveRequestResponse" in content

    def test_proto_has_release_reservation_request_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "message ReleaseReservationRequest" in content

    def test_proto_has_release_reservation_response_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "message ReleaseReservationResponse" in content


class TestGrpcServicerHasReservationMethods:
    def test_servicer_has_reserve_request_method(self) -> None:
        servicer_file = ROOT_DIR / "Services/documents-service/src/documents_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "def ReserveRequest" in content

    def test_servicer_has_release_reservation_method(self) -> None:
        servicer_file = ROOT_DIR / "Services/documents-service/src/documents_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "def ReleaseReservation" in content

    def test_servicer_calls_reserve_request_stock(self) -> None:
        servicer_file = ROOT_DIR / "Services/documents-service/src/documents_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "service.reserve_request_stock" in content

    def test_servicer_calls_release_request_reservation(self) -> None:
        servicer_file = ROOT_DIR / "Services/documents-service/src/documents_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "service.release_request_reservation" in content


class TestRestApiHasReservationEndpoints:
    def test_routes_has_reserve_endpoint(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/documents/{document_id}/reserve"' in content

    def test_routes_has_release_reservation_endpoint(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/documents/{document_id}/release-reservation"' in content

    def test_reserve_endpoint_calls_reserve_request_grpc(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        reserve_section = content[content.find('"/documents/{document_id}/reserve"'):content.find('"/documents/{document_id}"', content.find('"/documents/{document_id}/reserve"'))]
        assert "ReserveRequest" in reserve_section

    def test_release_reservation_endpoint_calls_release_reservation_grpc(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        release_section = content[content.find('"/documents/{document_id}/release-reservation"'):content.find('"/documents/{document_id}"', content.find('"/documents/{document_id}/release-reservation"'))]
        assert "ReleaseReservation" in release_section


class TestPhase8BackwardCompatibility:
    def test_approve_request_still_exists(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "def approve_request" in content

    def test_post_document_still_exists(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "def post_document" in content

    def test_proto_retains_approve_request_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "rpc ApproveRequest" in content

    def test_proto_retains_post_document_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "rpc PostDocument" in content


class TestPhase8ReservationLogic:
    def test_reserve_request_stock_checks_document_status(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        reserve_start = content.find("def reserve_request_stock")
        reserve_end = content.find("\n    def ", reserve_start + 1)
        reserve_section = content[reserve_start:reserve_end]
        assert "POSTED" in reserve_section

    def test_reserve_request_stock_sets_execution_started_at(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        reserve_start = content.find("def reserve_request_stock")
        reserve_end = content.find("\n    def ", reserve_start + 1)
        reserve_section = content[reserve_start:reserve_end]
        assert "execution_started_at" in reserve_section

    def test_release_request_reservation_sets_completed_at(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        release_start = content.find("def release_request_reservation")
        release_end = content.find("\n    def ", release_start + 1)
        release_section = content[release_start:release_end]
        assert "completed_at" in release_section

    def test_reserve_request_stock_tracks_reservation_ids(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        reserve_start = content.find("def reserve_request_stock")
        reserve_end = content.find("\n    def ", reserve_start + 1)
        reserve_section = content[reserve_start:reserve_end]
        assert "reservation_ids" in reserve_section

    def test_release_request_reservation_tracks_reservation_ids(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        release_start = content.find("def release_request_reservation")
        release_end = content.find("\n    def ", release_start + 1)
        release_section = content[release_start:release_end]
        assert "reservation_ids" in release_section
