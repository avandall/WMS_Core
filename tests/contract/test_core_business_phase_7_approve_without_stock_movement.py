from __future__ import annotations

from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]


# ===========================================================================
# Phase 7 – approve without stock movement
# ===========================================================================


class TestDocumentServiceHasApproveRequest:
    def test_document_service_has_approve_request_method(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "def approve_request" in content

    def test_approve_request_does_not_emit_inventory_movement_requested(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        # Verify that approve_request only publishes DocumentPosted, NOT InventoryMovementRequested
        assert "approve_request" in content
        # Check the method publishes DocumentPosted
        assert "DocumentPosted" in content
        # The method should NOT call _publish_document_posted which emits InventoryMovementRequested
        # Instead it should only call event_publisher.publish with DocumentPosted
        # Extract just the approve_request method body (up to the next method def)
        approve_start = content.find("def approve_request")
        approve_end = content.find("\n    def ", approve_start + 1)
        approve_section = content[approve_start:approve_end]
        # Check that it doesn't call _publish_document_posted (which emits InventoryMovementRequested)
        assert "_publish_document_posted" not in approve_section

    def test_approve_request_sets_approved_at(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "approved_at" in content
        assert "datetime.now()" in content

    def test_approve_request_sets_posted_at_for_backward_compatibility(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        approve_section = content[content.find("def approve_request"):content.find("def cancel_document")]
        assert "posted_at" in approve_section


class TestProtoHasApproveRequest:
    def test_proto_has_approve_request_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "rpc ApproveRequest" in content

    def test_proto_has_approve_request_request_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "message ApproveRequestRequest" in content

    def test_proto_has_approve_request_response_message(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "message ApproveRequestResponse" in content

    def test_approve_request_request_has_document_id(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "int64 document_id = 1" in content

    def test_approve_request_request_has_approved_by(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "string approved_by = 2" in content


class TestGrpcServicerHasApproveRequest:
    def test_servicer_has_approve_request_method(self) -> None:
        servicer_file = ROOT_DIR / "Services/documents-service/src/documents_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "def ApproveRequest" in content

    def test_servicer_calls_service_approve_request(self) -> None:
        servicer_file = ROOT_DIR / "Services/documents-service/src/documents_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "service.approve_request" in content


class TestRestApiHasApproveEndpoint:
    def test_routes_has_approve_endpoint(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/documents/{document_id}/approve"' in content

    def test_approve_endpoint_calls_approve_request_grpc(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        approve_section = content[content.find('"/documents/{document_id}/approve"'):content.find('"/documents/{document_id}"', content.find('"/documents/{document_id}/approve"'))]
        assert "ApproveRequest" in approve_section

    def test_approve_endpoint_uses_doc_post_permission(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        approve_section = content[content.find('"/documents/{document_id}/approve"'):content.find('"/documents/{document_id}"', content.find('"/documents/{document_id}/approve"'))]
        assert "DOC_POST" in approve_section


class TestPhase7BackwardCompatibility:
    def test_post_document_still_exists(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "def post_document" in content

    def test_post_document_still_emits_inventory_movement_requested(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "InventoryMovementRequested" in content

    def test_post_document_grpc_still_exists(self) -> None:
        servicer_file = ROOT_DIR / "Services/documents-service/src/documents_service/grpc_servicer.py"
        content = servicer_file.read_text()
        assert "def PostDocument" in content

    def test_post_document_rest_endpoint_still_exists(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/documents/{document_id}/post"' in content

    def test_proto_retains_post_document_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "rpc PostDocument" in content

    def test_approve_request_does_not_remove_post_document(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        # Both should exist
        assert "rpc PostDocument" in content
        assert "rpc ApproveRequest" in content


class TestPhase7NoStockMovement:
    def test_approve_request_comment_mentions_no_stock_movement(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        approve_section = content[content.find("def approve_request"):content.find("def cancel_document")]
        assert "no stock movement" in approve_section.lower() or "without triggering" in approve_section.lower()

    def test_approve_request_only_changes_status_and_metadata(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        approve_section = content[content.find("def approve_request"):content.find("def cancel_document")]
        # Should only change status, approved_by, approved_at, posted_at
        assert "document.status" in approve_section
        assert "document.approved_by" in approve_section
        assert "document.approved_at" in approve_section
        # Should NOT call document.post() which would trigger old behavior
        assert "document.post(" not in approve_section
