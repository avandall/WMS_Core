"""
Integration test for TASK-084:
Testing API Gateway REST endpoints and gRPC integration for:
- POST /api/v1/waves
- GET /api/v1/waves/{wave_id}
- POST /api/v1/cycle-counts
- GET /api/v1/cycle-counts/{cycle_count_id}
- POST /api/v1/packing/verify
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api_gateway.app import create_app
from api_gateway.auth import CurrentUser, get_current_user
from api_gateway.gen.wms.documents.v1 import documents_pb2


@pytest.fixture(autouse=True)
def setup_tables():
    from app.shared.core.database import Base, engine
    from app.modules.documents.infrastructure.models.picking_wave import PickingWaveModel
    from app.modules.documents.infrastructure.models.cycle_count_sheet import CycleCountSheetModel
    from app.modules.documents.infrastructure.models.carton_package import CartonPackageModel
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)



@pytest.fixture
def client():
    app = create_app()
    admin_user = CurrentUser(user_id=1, role="admin", email="admin@example.com")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)



def test_gateway_create_and_get_wave(client):
    mock_wave_resp = documents_pb2.WaveResponse(
        wave_id="WAVE-GW-001",
        carrier="SHOPEE_EXPRESS",
        dispatch_cutoff="2026-09-25T18:00:00Z",
        max_orders=40,
        status="DRAFT",
        order_count=0,
        created_at="2026-09-25T12:00:00Z",
    )

    mock_stub = MagicMock()
    mock_stub.CreateWave.return_value = mock_wave_resp
    mock_stub.GetWave.return_value = mock_wave_resp

    with patch("api_gateway.routes.documents_stub") as mock_ds:
        mock_ds.return_value.__enter__.return_value = mock_stub

        # 1. Create Wave via REST API Gateway
        resp = client.post(
            "/api/v1/waves",
            json={
                "wave_id": "WAVE-GW-001",
                "carrier": "SHOPEE_EXPRESS",
                "dispatch_cutoff": "2026-09-25T18:00:00Z",
                "max_orders": 40,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["wave_id"] == "WAVE-GW-001"
        assert data["carrier"] == "SHOPEE_EXPRESS"
        assert data["max_orders"] == 40
        assert data["status"] == "DRAFT"

        # 2. Get Wave via REST API Gateway
        resp_get = client.get("/api/v1/waves/WAVE-GW-001")
        assert resp_get.status_code == 200, resp_get.text
        assert resp_get.json()["wave_id"] == "WAVE-GW-001"


def test_gateway_create_and_get_cycle_count(client):
    mock_cc_resp = documents_pb2.CycleCountResponse(
        cycle_count_id="CC-GW-001",
        warehouse_id=1,
        title="Weekly Audit",
        status="DRAFT",
        assigned_to="staff_bob",
        discrepancy_qty_threshold=5,
        discrepancy_value_threshold=50.0,
        created_by="manager",
        note="Zone A check",
        items=[
            documents_pb2.CycleCountItemProto(
                item_id="ITEM-1",
                product_id=101,
                location_id="A-01-01",
                system_qty=100,
                counted_qty=0,
                lot_number="LOT-1",
                unit_cost=10.0,
            )
        ],
        created_at="2026-09-25T12:00:00Z",
    )

    mock_stub = MagicMock()
    mock_stub.CreateCycleCount.return_value = mock_cc_resp
    mock_stub.GetCycleCount.return_value = mock_cc_resp

    with patch("api_gateway.routes.documents_stub") as mock_ds:
        mock_ds.return_value.__enter__.return_value = mock_stub

        # 1. Create Cycle Count via REST API Gateway
        resp = client.post(
            "/api/v1/cycle-counts",
            json={
                "cycle_count_id": "CC-GW-001",
                "warehouse_id": 1,
                "title": "Weekly Audit",
                "items": [
                    {
                        "item_id": "ITEM-1",
                        "product_id": 101,
                        "location_id": "A-01-01",
                        "system_qty": 100,
                        "lot_number": "LOT-1",
                        "unit_cost": 10.0,
                    }
                ],
                "assigned_to": "staff_bob",
                "discrepancy_qty_threshold": 5,
                "discrepancy_value_threshold": 50.0,
                "created_by": "manager",
                "note": "Zone A check",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["cycle_count_id"] == "CC-GW-001"
        assert data["warehouse_id"] == 1
        assert data["title"] == "Weekly Audit"
        assert len(data["items"]) == 1
        assert data["items"][0]["product_id"] == 101

        # 2. Get Cycle Count via REST API Gateway
        resp_get = client.get("/api/v1/cycle-counts/CC-GW-001")
        assert resp_get.status_code == 200, resp_get.text
        assert resp_get.json()["cycle_count_id"] == "CC-GW-001"


def test_gateway_verify_packing(client):
    mock_pack_resp = documents_pb2.VerifyPackingResponse(
        carton_id="CARTON-GW-001",
        theoretical_weight_g=600.0,
        measured_weight_g=610.0,
        deviation_g=10.0,
        is_valid=True,
        allowed_tolerance_g=50.0,
        message="Weight verification PASSED",
        status="WEIGHT_VERIFIED",
    )

    mock_stub = MagicMock()
    mock_stub.VerifyPacking.return_value = mock_pack_resp

    with patch("api_gateway.routes.documents_stub") as mock_ds:
        mock_ds.return_value.__enter__.return_value = mock_stub

        resp = client.post(
            "/api/v1/packing/verify",
            json={
                "carton_id": "CARTON-GW-001",
                "order_id": "ORD-123",
                "measured_weight_g": 610.0,
                "packaging_tare_weight_g": 100.0,
                "items": [
                    {
                        "product_id": "P1",
                        "sku": "SKU-001",
                        "quantity": 5,
                        "unit_weight_g": 100.0,
                    }
                ],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["carton_id"] == "CARTON-GW-001"
        assert data["is_valid"] is True
        assert data["theoretical_weight_g"] == 600.0
        assert data["deviation_g"] == 10.0


def test_grpc_servicer_wave_and_cycle_count_direct():
    """Direct end-to-end integration test of DocumentsServiceServicer methods."""
    from documents_service.grpc_servicer import DocumentsServiceServicer
    servicer = DocumentsServiceServicer()

    mock_context = MagicMock()

    # 1. Create Wave
    create_wave_req = documents_pb2.CreateWaveRequest(
        wave_id="WAVE-SRV-001",
        carrier="GHN",
        dispatch_cutoff="2026-09-25T18:00:00Z",
        max_orders=30,
    )
    wave_resp = servicer.CreateWave(create_wave_req, mock_context)
    assert wave_resp.wave_id == "WAVE-SRV-001"
    assert wave_resp.carrier == "GHN"
    assert wave_resp.status == "DRAFT"

    # Get Wave
    get_wave_resp = servicer.GetWave(documents_pb2.GetWaveRequest(wave_id="WAVE-SRV-001"), mock_context)
    assert get_wave_resp.wave_id == "WAVE-SRV-001"

    # 2. Create Cycle Count
    create_cc_req = documents_pb2.CreateCycleCountRequest(
        cycle_count_id="CC-SRV-001",
        warehouse_id=1,
        title="Cycle Count Direct Test",
        items=[
            documents_pb2.CycleCountItemProto(
                item_id="ITM-1",
                product_id=101,
                location_id="LOC-1",
                system_qty=50,
                lot_number="LOT-X",
                unit_cost=15.0,
            )
        ],
    )
    cc_resp = servicer.CreateCycleCount(create_cc_req, mock_context)
    assert cc_resp.cycle_count_id == "CC-SRV-001"
    assert len(cc_resp.items) == 1

    # Get Cycle Count
    get_cc_resp = servicer.GetCycleCount(documents_pb2.GetCycleCountRequest(cycle_count_id="CC-SRV-001"), mock_context)
    assert get_cc_resp.cycle_count_id == "CC-SRV-001"

    # 3. Verify Packing
    verify_pack_req = documents_pb2.VerifyPackingRequest(
        carton_id="CARTON-SRV-001",
        order_id="ORD-SRV-1",
        measured_weight_g=210.0,
        packaging_tare_weight_g=100.0,
        items=[
            documents_pb2.PackItemProto(
                product_id="P1",
                sku="SKU-1",
                quantity=1,
                unit_weight_g=100.0,
            )
        ],
        override_tolerance_g=50.0,
    )
    pack_resp = servicer.VerifyPacking(verify_pack_req, mock_context)
    assert pack_resp.carton_id == "CARTON-SRV-001"
    assert pack_resp.is_valid is True
    assert pack_resp.theoretical_weight_g == 200.0
