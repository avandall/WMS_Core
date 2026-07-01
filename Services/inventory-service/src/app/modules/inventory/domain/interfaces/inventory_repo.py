from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from app.modules.inventory.domain.entities.inventory import InventoryItem


class IInventoryRepo(ABC):
    @abstractmethod
    def save(self, inventory_item: "InventoryItem") -> None:
        pass

    @abstractmethod
    def add_quantity(self, product_id: int, quantity: int) -> None:
        pass

    @abstractmethod
    def get_quantity(self, product_id: int) -> int:
        pass

    @abstractmethod
    def get_all(self) -> List["InventoryItem"]:
        pass

    @abstractmethod
    def delete(self, product_id: int) -> None:
        pass

    @abstractmethod
    def remove_quantity(self, product_id: int, quantity: int) -> None:
        pass

    @abstractmethod
    def get_inventory_by_warehouse_rows(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_warehouse_distribution(self, product_id: int) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_warehouse_summary(self) -> dict[int, dict[str, Any]]:
        pass

    @abstractmethod
    def adjust_quantity(self, product_id: int, quantity_delta: int) -> None:
        pass

    @abstractmethod
    def adjust_warehouse_quantity(
        self, product_id: int, warehouse_id: int, quantity_delta: int
    ) -> None:
        pass

    @abstractmethod
    def has_movement_event(self, event_id: str) -> bool:
        pass

    @abstractmethod
    def record_movement_event(
        self,
        *,
        event_id: str,
        movement_type: str,
        document_id: int | None,
        payload: dict[str, Any],
    ) -> None:
        pass

    # Phase 4: Reservation methods
    @abstractmethod
    def create_reservation(
        self,
        *,
        source_type: str,
        source_id: int | None,
        document_id: int | None,
        product_id: int,
        warehouse_id: int,
        requested_qty: int,
        created_by: str | None,
        idempotency_key: str | None,
        expires_at: datetime | None,
    ) -> int:
        pass

    @abstractmethod
    def release_reservation(self, reservation_id: int, released_qty: int | None = None) -> None:
        pass

    @abstractmethod
    def consume_reservation(self, reservation_id: int, consumed_qty: int) -> None:
        pass

    @abstractmethod
    def list_reservations(
        self, product_id: int | None = None, warehouse_id: int | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def calculate_available_stock(self, product_id: int, warehouse_id: int) -> dict[str, Any]:
        pass

    # Phase 9: Inventory transaction ledger methods
    @abstractmethod
    def write_transaction(
        self,
        transaction_type: str,
        product_id: int,
        warehouse_id: int,
        quantity: int,
        physical_qty_before: int | None = None,
        physical_qty_after: int | None = None,
        reserved_qty_before: int | None = None,
        reserved_qty_after: int | None = None,
        available_qty_before: int | None = None,
        available_qty_after: int | None = None,
        document_id: int | None = None,
        document_line_id: int | None = None,
        user_id: str | None = None,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def list_transactions(
        self,
        document_id: int | None = None,
        product_id: int | None = None,
        warehouse_id: int | None = None,
        transaction_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        pass


# Alias for backward compatibility
InventoryRepo = IInventoryRepo
