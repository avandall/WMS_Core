from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
INVENTORY_SRC = ROOT_DIR / "Services/inventory-service/src"
sys.path.insert(0, str(INVENTORY_SRC))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.shared.domain.business_exceptions import InsufficientStockError, InvalidQuantityError


class InMemoryInventoryRepo:
    def __init__(self) -> None:
        self.inventory: dict[int, int] = {}
        self.warehouse_inventory: dict[tuple[int, int], int] = {}
        self.movements: dict[str, dict[str, Any]] = {}

    def save(self, inventory_item: InventoryItem) -> None:
        self.inventory[inventory_item.product_id] = inventory_item.quantity

    def add_quantity(self, product_id: int, quantity: int) -> None:
        self.inventory[product_id] = self.inventory.get(product_id, 0) + quantity

    def adjust_quantity(self, product_id: int, quantity_delta: int) -> None:
        next_quantity = self.inventory.get(product_id, 0) + quantity_delta
        if next_quantity < 0:
            raise InsufficientStockError("insufficient total stock")
        self.inventory[product_id] = next_quantity

    def get_quantity(self, product_id: int) -> int:
        return self.inventory.get(product_id, 0)

    def get_all(self) -> list[InventoryItem]:
        return [
            InventoryItem(product_id=product_id, quantity=quantity)
            for product_id, quantity in self.inventory.items()
        ]

    def delete(self, product_id: int) -> None:
        self.inventory.pop(product_id, None)

    def remove_quantity(self, product_id: int, quantity: int) -> None:
        self.adjust_quantity(product_id, -quantity)

    def adjust_warehouse_quantity(
        self, product_id: int, warehouse_id: int, quantity_delta: int
    ) -> None:
        key = (warehouse_id, product_id)
        next_quantity = self.warehouse_inventory.get(key, 0) + quantity_delta
        if next_quantity < 0:
            raise InsufficientStockError("insufficient warehouse stock")
        self.warehouse_inventory[key] = next_quantity

    def get_inventory_by_warehouse_rows(self) -> list[dict[str, Any]]:
        return []

    def get_warehouse_distribution(self, product_id: int) -> list[dict[str, Any]]:
        return []

    def get_warehouse_summary(self) -> dict[int, dict[str, Any]]:
        return {}

    def has_movement_event(self, event_id: str) -> bool:
        return event_id in self.movements

    def record_movement_event(
        self,
        *,
        event_id: str,
        movement_type: str,
        document_id: int | None,
        payload: dict[str, Any],
    ) -> None:
        self.movements[event_id] = {
            "movement_type": movement_type,
            "document_id": document_id,
            "payload": payload,
        }


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


def _service() -> tuple[InventoryService, InMemoryInventoryRepo, RecordingPublisher]:
    repo = InMemoryInventoryRepo()
    publisher = RecordingPublisher()
    return InventoryService(repo, event_publisher=publisher), repo, publisher


# ---------------------------------------------------------------------------
# Phase 0 – baseline: capture current behaviour before changing it
# ---------------------------------------------------------------------------


class TestImportMovementBaseline:
    def test_import_increases_total_stock(self) -> None:
        service, repo, _ = _service()
        payload = {
            "event_id": "import-baseline-1",
            "document_id": 1,
            "doc_type": "IMPORT",
            "to_warehouse_id": 10,
            "items": [{"product_id": 100, "quantity": 5}],
        }
        service.apply_document_movement(payload)
        assert repo.get_quantity(100) == 5

    def test_import_increases_warehouse_stock(self) -> None:
        service, repo, _ = _service()
        payload = {
            "event_id": "import-baseline-2",
            "document_id": 1,
            "doc_type": "IMPORT",
            "to_warehouse_id": 10,
            "items": [{"product_id": 100, "quantity": 5}],
        }
        service.apply_document_movement(payload)
        assert repo.warehouse_inventory[(10, 100)] == 5


class TestExportSaleMovementBaseline:
    def test_export_decreases_total_stock(self) -> None:
        service, repo, _ = _service()
        repo.inventory[100] = 10
        repo.warehouse_inventory[(10, 100)] = 10
        payload = {
            "event_id": "export-baseline-1",
            "document_id": 2,
            "doc_type": "EXPORT",
            "from_warehouse_id": 10,
            "items": [{"product_id": 100, "quantity": 3}],
        }
        service.apply_document_movement(payload)
        assert repo.get_quantity(100) == 7

    def test_sale_decreases_total_stock(self) -> None:
        service, repo, _ = _service()
        repo.inventory[100] = 10
        repo.warehouse_inventory[(10, 100)] = 10
        payload = {
            "event_id": "sale-baseline-1",
            "document_id": 3,
            "doc_type": "SALE",
            "from_warehouse_id": 10,
            "items": [{"product_id": 100, "quantity": 4}],
        }
        service.apply_document_movement(payload)
        assert repo.get_quantity(100) == 6

    def test_export_exceeding_stock_raises(self) -> None:
        service, repo, _ = _service()
        repo.inventory[100] = 2
        repo.warehouse_inventory[(10, 100)] = 2
        payload = {
            "event_id": "export-overstock-1",
            "document_id": 2,
            "doc_type": "EXPORT",
            "from_warehouse_id": 10,
            "items": [{"product_id": 100, "quantity": 5}],
        }
        with pytest.raises(InsufficientStockError):
            service.apply_document_movement(payload)


class TestTransferMovementBaseline:
    def test_transfer_moves_stock_between_warehouses(self) -> None:
        service, repo, _ = _service()
        repo.inventory[100] = 10
        repo.warehouse_inventory[(10, 100)] = 10
        payload = {
            "event_id": "transfer-baseline-1",
            "document_id": 4,
            "doc_type": "TRANSFER",
            "from_warehouse_id": 10,
            "to_warehouse_id": 11,
            "items": [{"product_id": 100, "quantity": 3}],
        }
        service.apply_document_movement(payload)
        assert repo.warehouse_inventory[(10, 100)] == 7
        assert repo.warehouse_inventory[(11, 100)] == 3

    def test_transfer_total_stock_adjusts_via_outbound_only(self) -> None:
        """Current behaviour: outbound leg decreases total, inbound leg passes
        total_delta=0 so net total decreases by the transfer quantity.  The
        warehouse-level numbers are correct (source down, dest up) but the
        global total is only reduced once via _apply_outbound.  The inbound
        leg's total_delta=0 means adjust_quantity(pid, 0) is a no-op at the
        repo level (the repo does not enforce non-zero like the service does).
        """
        service, repo, _ = _service()
        repo.inventory[100] = 10
        repo.warehouse_inventory[(10, 100)] = 10
        payload = {
            "event_id": "transfer-baseline-2",
            "document_id": 4,
            "doc_type": "TRANSFER",
            "from_warehouse_id": 10,
            "to_warehouse_id": 11,
            "items": [{"product_id": 100, "quantity": 3}],
        }
        service.apply_document_movement(payload)
        assert repo.warehouse_inventory[(10, 100)] == 7
        assert repo.warehouse_inventory[(11, 100)] == 3


class TestMovementIdempotencyBaseline:
    def test_duplicate_movement_is_idempotent(self) -> None:
        service, repo, _ = _service()
        payload = {
            "event_id": "idempotent-1",
            "document_id": 1,
            "doc_type": "IMPORT",
            "to_warehouse_id": 10,
            "items": [{"product_id": 100, "quantity": 5}],
        }
        assert service.apply_document_movement(payload) is True
        assert service.apply_document_movement(payload) is False
        assert repo.get_quantity(100) == 5

    def test_movement_without_event_id_raises(self) -> None:
        service, _, _ = _service()
        payload = {
            "event_id": "",
            "document_id": 1,
            "doc_type": "IMPORT",
            "to_warehouse_id": 10,
            "items": [{"product_id": 100, "quantity": 5}],
        }
        with pytest.raises(ValueError):
            service.apply_document_movement(payload)


class TestLegacyDocumentMovementsComprehensive:
    def test_all_doc_types_update_physical_stock(self) -> None:
        service, repo, _ = _service()
        repo.inventory[200] = 20
        repo.warehouse_inventory[(10, 200)] = 12

        cases = [
            (
                {
                    "event_id": "import-1",
                    "document_id": 1,
                    "doc_type": "IMPORT",
                    "to_warehouse_id": 11,
                    "items": [{"product_id": 100, "quantity": 5}],
                },
                100,
                5,
                {(11, 100): 5},
            ),
            (
                {
                    "event_id": "export-1",
                    "document_id": 2,
                    "doc_type": "EXPORT",
                    "from_warehouse_id": 10,
                    "items": [{"product_id": 200, "quantity": 3}],
                },
                200,
                17,
                {(10, 200): 9},
            ),
            (
                {
                    "event_id": "sale-1",
                    "document_id": 3,
                    "doc_type": "SALE",
                    "from_warehouse_id": 10,
                    "items": [{"product_id": 200, "quantity": 4}],
                },
                200,
                13,
                {(10, 200): 5},
            ),
            (
                {
                    "event_id": "transfer-1",
                    "document_id": 4,
                    "doc_type": "TRANSFER",
                    "from_warehouse_id": 10,
                    "to_warehouse_id": 12,
                    "items": [{"product_id": 200, "quantity": 2}],
                },
                200,
                11,
                {(10, 200): 3, (12, 200): 2},
            ),
        ]

        for payload, product_id, expected_total, expected_warehouse_rows in cases:
            assert service.apply_document_movement(payload) is True
            assert service.apply_document_movement(payload) is False
            assert repo.get_quantity(product_id) == expected_total
            for key, expected_quantity in expected_warehouse_rows.items():
                assert repo.warehouse_inventory[key] == expected_quantity

        assert set(repo.movements) == {"import-1", "export-1", "sale-1", "transfer-1"}


class TestReservationBaseline:
    def test_reserve_stock_only_records_event(self) -> None:
        service, repo, publisher = _service()
        repo.inventory[100] = 10
        result = service.reserve_stock(
            product_id=100, warehouse_id=10, quantity=4, event_id="reserve-baseline-1"
        )
        assert result is True
        assert repo.get_quantity(100) == 10
        assert any(et == "StockReserved" for et, _ in publisher.events)

    def test_reserve_stock_idempotent(self) -> None:
        service, repo, _ = _service()
        repo.inventory[100] = 10
        service.reserve_stock(product_id=100, warehouse_id=10, quantity=4, event_id="reserve-idem-1")
        result = service.reserve_stock(product_id=100, warehouse_id=10, quantity=4, event_id="reserve-idem-1")
        assert result is False

    def test_reserve_stock_insufficient_raises(self) -> None:
        service, repo, _ = _service()
        repo.inventory[100] = 2
        with pytest.raises(InsufficientStockError):
            service.reserve_stock(product_id=100, warehouse_id=10, quantity=5, event_id="reserve-insuf-1")

    def test_release_reservation_records_event(self) -> None:
        service, repo, publisher = _service()
        repo.inventory[100] = 10
        service.release_reservation(
            product_id=100, warehouse_id=10, quantity=4, event_id="release-baseline-1"
        )
        assert any(et == "ReservationReleased" for et, _ in publisher.events)


class TestAdjustmentBaseline:
    def test_adjust_inventory_positive(self) -> None:
        service, repo, _ = _service()
        service.adjust_inventory(product_id=100, quantity_delta=5, event_id="adj-pos-1")
        assert repo.get_quantity(100) == 5

    def test_adjust_inventory_negative(self) -> None:
        service, repo, _ = _service()
        repo.inventory[100] = 10
        service.adjust_inventory(product_id=100, quantity_delta=-3, event_id="adj-neg-1")
        assert repo.get_quantity(100) == 7

    def test_adjust_inventory_zero_raises(self) -> None:
        service, repo, _ = _service()
        with pytest.raises(InvalidQuantityError):
            service.adjust_inventory(product_id=100, quantity_delta=0, event_id="adj-zero-1")


# ---------------------------------------------------------------------------
# Phase 0 – target-gap tests: expected failures documenting missing behaviour
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="Phase 0 gap: reservations are event-only, no reserved_qty persisted.")
def test_target_gap_sales_reservation_should_reduce_available_quantity() -> None:
    service, repo, _ = _service()
    repo.inventory[100] = 10

    service.reserve_stock(product_id=100, warehouse_id=10, quantity=4, event_id="reserve-1")

    assert repo.get_quantity(100) == 10
    assert repo.available_quantity[(10, 100)] == 6


@pytest.mark.xfail(reason="Phase 0 gap: no execution confirmation API on InventoryService.")
def test_target_gap_execution_confirmation_should_use_actual_quantity() -> None:
    service, repo, _ = _service()
    repo.inventory[100] = 10
    repo.warehouse_inventory[(10, 100)] = 10

    service.confirm_execution(
        document_id=1,
        product_id=100,
        warehouse_id=10,
        requested_quantity=5,
        executed_quantity=3,
    )

    assert repo.get_quantity(100) == 7


@pytest.mark.xfail(reason="Phase 0 gap: warehouse_inventory has no reserved_qty field.")
def test_target_gap_warehouse_inventory_should_have_reserved_qty() -> None:
    _, repo, _ = _service()
    assert hasattr(repo, "reserved_qty") or hasattr(repo, "get_available_quantity")


@pytest.mark.xfail(reason="Phase 0 gap: no in_transit_qty for transfers.")
def test_target_gap_transfer_should_use_in_transit_stock() -> None:
    service, repo, _ = _service()
    repo.inventory[100] = 10
    repo.warehouse_inventory[(10, 100)] = 10

    payload = {
        "event_id": "transfer-gap-1",
        "document_id": 1,
        "doc_type": "TRANSFER",
        "from_warehouse_id": 10,
        "to_warehouse_id": 11,
        "items": [{"product_id": 100, "quantity": 3}],
    }
    service.apply_document_movement(payload)
    assert repo.in_transit_qty.get((10, 11, 100), 0) == 3
