from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
INVENTORY_SRC = ROOT_DIR / "Services/inventory-service/src"
sys.path.insert(0, str(INVENTORY_SRC))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.shared.domain.business_exceptions import InsufficientStockError


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

    def get_inventory_by_warehouse_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "warehouse_name": str(warehouse_id),
                "quantity": quantity,
            }
            for (warehouse_id, product_id), quantity in self.warehouse_inventory.items()
        ]

    def get_warehouse_distribution(self, product_id: int) -> list[dict[str, Any]]:
        return [
            {
                "warehouse_id": warehouse_id,
                "warehouse_name": str(warehouse_id),
                "quantity": quantity,
            }
            for (warehouse_id, row_product_id), quantity in self.warehouse_inventory.items()
            if row_product_id == product_id
        ]

    def get_warehouse_summary(self) -> dict[int, dict[str, Any]]:
        return {}

    def adjust_warehouse_quantity(
        self, product_id: int, warehouse_id: int, quantity_delta: int
    ) -> None:
        key = (warehouse_id, product_id)
        next_quantity = self.warehouse_inventory.get(key, 0) + quantity_delta
        if next_quantity < 0:
            raise InsufficientStockError("insufficient warehouse stock")
        self.warehouse_inventory[key] = next_quantity

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


def test_apply_import_document_movement_is_idempotent() -> None:
    service, repo, publisher = _service()
    payload = {
        "event_id": "documents:1:inventory-movement-requested",
        "document_id": 1,
        "doc_type": "IMPORT",
        "to_warehouse_id": 10,
        "items": [{"product_id": 100, "quantity": 3}],
    }

    assert service.apply_document_movement(payload) is True
    assert service.apply_document_movement(payload) is False

    assert repo.get_quantity(100) == 3
    assert repo.warehouse_inventory[(10, 100)] == 3
    assert repo.movements[payload["event_id"]]["movement_type"] == "InventoryMovementApplied"
    assert [event_type for event_type, _ in publisher.events] == ["InventoryMovementApplied"]


def test_apply_sale_document_movement_rejects_insufficient_stock() -> None:
    service, _, _ = _service()
    payload = {
        "event_id": "documents:2:inventory-movement-requested",
        "document_id": 2,
        "doc_type": "SALE",
        "from_warehouse_id": 10,
        "items": [{"product_id": 100, "quantity": 3}],
    }

    try:
        service.apply_document_movement(payload)
    except InsufficientStockError:
        pass
    else:
        raise AssertionError("movement applied without stock")


def test_reserve_and_release_are_idempotent_use_cases() -> None:
    service, repo, publisher = _service()
    repo.inventory[100] = 5

    assert service.reserve_stock(product_id=100, quantity=2, event_id="reserve-1") is True
    assert service.reserve_stock(product_id=100, quantity=2, event_id="reserve-1") is False
    assert service.release_reservation(product_id=100, quantity=2, event_id="release-1") is True

    assert repo.get_quantity(100) == 5
    assert [event_type for event_type, _ in publisher.events] == [
        "StockReserved",
        "ReservationReleased",
    ]
