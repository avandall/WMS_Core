from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Import domain and service objects
# ---------------------------------------------------------------------------
DOCUMENTS_SRC = ROOT_DIR / "Services/documents-service/src"
sys.path.insert(0, str(DOCUMENTS_SRC))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.modules.documents.application.services.document_service import DocumentService

INVENTORY_SRC = ROOT_DIR / "Services/inventory-service/src"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
sys.path.insert(0, str(INVENTORY_SRC))

from app.modules.inventory.application.services.inventory_service import InventoryService


# ---------------------------------------------------------------------------
# InMemory Repository for Inventory to verify physical and in-transit qtys
# ---------------------------------------------------------------------------
class DummyInventoryRepo:
    def __init__(self) -> None:
        self.stock: dict[tuple[int, int], dict[str, int]] = {}
        self.transactions: list[dict[str, Any]] = []

    def adjust_warehouse_quantity(self, product_id: int, warehouse_id: int, quantity_delta: int) -> None:
        key = (product_id, warehouse_id)
        if key not in self.stock:
            self.stock[key] = {"physical": 0, "in_transit": 0}
        self.stock[key]["physical"] += quantity_delta

    def adjust_warehouse_in_transit(self, product_id: int, warehouse_id: int, quantity_delta: int) -> None:
        key = (product_id, warehouse_id)
        if key not in self.stock:
            self.stock[key] = {"physical": 0, "in_transit": 0}
        self.stock[key]["in_transit"] += quantity_delta

    def adjust_quantity(self, product_id: int, quantity_delta: int) -> None:
        pass

    def has_movement_event(self, event_id: str) -> bool:
        return False

    def write_transaction(self, **kwargs) -> None:
        self.transactions.append(kwargs)

    def list_transactions(self, **kwargs) -> list[dict[str, Any]]:
        return [{"id": 42}]


# ===========================================================================
# Phase 14 – Transfer Issue and Receipt Coordination Verification
# ===========================================================================
class TestInventoryServiceLogicPhase14:
    def test_transfer_issue_reduces_source_physical_increases_in_transit(self) -> None:
        repo = DummyInventoryRepo()
        # Seed 100 physical stock at warehouse 1
        repo.stock[(202, 1)] = {"physical": 100, "in_transit": 0}
        
        service = InventoryService(repo, event_publisher=Mock())

        # TRANSFER_ISSUE from warehouse 1 of qty 10
        service.confirm_inventory_transaction(
            transaction_type="TRANSFER_ISSUE",
            product_id=202,
            warehouse_id=1,
            quantity=10,
        )

        assert repo.stock[(202, 1)]["physical"] == 90
        assert repo.stock[(202, 1)]["in_transit"] == 10

    def test_transfer_receipt_reduces_in_transit_increases_destination_physical(self) -> None:
        repo = DummyInventoryRepo()
        # Seed in-transit stock at warehouse 1 (source), and physical at warehouse 2 (destination)
        repo.stock[(202, 1)] = {"physical": 90, "in_transit": 10}
        repo.stock[(202, 2)] = {"physical": 50, "in_transit": 0}
        
        service = InventoryService(repo, event_publisher=Mock())

        # TRANSFER_RECEIPT at warehouse 2 (destination) with source warehouse 1 of qty 10
        service.confirm_inventory_transaction(
            transaction_type="TRANSFER_RECEIPT",
            product_id=202,
            warehouse_id=2,
            quantity=10,
            source_warehouse_id=1,
        )

        # Source in-transit should be reduced to 0
        assert repo.stock[(202, 1)]["in_transit"] == 0
        # Destination physical stock should be increased to 60
        assert repo.stock[(202, 2)]["physical"] == 60


class TestApiGatewayRoutesPhase14:
    def test_routes_handles_transfer_coordination(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert "target_tx_type = \"TRANSFER_ISSUE\"" in content
        assert "target_tx_type = \"TRANSFER_RECEIPT\"" in content
        assert "source_warehouse_id=doc.from_warehouse_id," in content
        assert 'is_transfer_receipt = (doc_type == "TRANSFER" and current_status == "EXECUTED")' in content
