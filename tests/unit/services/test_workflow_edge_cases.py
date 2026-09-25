from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.application.services.cycle_count_service import CycleCountService
from app.modules.documents.domain.entities.document import Document, DocumentStatus
from app.modules.documents.domain.entities.cycle_count import CycleCountItem
from app.modules.documents.domain.exceptions import InvalidDocumentStatusError
from app.modules.inventory.application.services.allocation_service import AllocationService
from app.modules.inventory.application.services.inventory_service import InventoryService


class InMemoryDocumentRepo:
    def __init__(self):
        self._docs = {}

    def save(self, doc: Document) -> None:
        if doc.document_id == 0:
            doc.document_id = len(self._docs) + 1
        self._docs[doc.document_id] = doc

    def get(self, doc_id: int) -> Document | None:
        return self._docs.get(doc_id)

    def get_all(self, status=None):
        if status:
            return [d for d in self._docs.values() if d.status == status]
        return list(self._docs.values())


class InMemoryInventoryRepo:
    def __init__(self):
        self.reservations = {}
        self.locations = []
        self.location_adjustments = []

    def list_reservations(self, product_id=None, warehouse_id=None, status=None, document_id=None):
        result = []
        for r_id, res in self.reservations.items():
            if product_id and res.get("product_id") != product_id:
                continue
            if warehouse_id and res.get("warehouse_id") != warehouse_id:
                continue
            if status and res.get("status") != status:
                continue
            if document_id and res.get("document_id") != document_id:
                continue
            result.append(res)
        return result

    def release_reservation(self, reservation_id: int, released_qty: int | None = None) -> None:
        if reservation_id in self.reservations:
            res = self.reservations[reservation_id]
            qty = released_qty if released_qty is not None else res["reserved_qty"]
            res["reserved_qty"] = max(0, res["reserved_qty"] - qty)
            if res["reserved_qty"] == 0:
                res["status"] = "RELEASED"

    def adjust_location_quantity(self, warehouse_id, position_id, product_id, quantity_delta, allocated_delta=0, lpn="", status="AVAILABLE", lot_number="", mfg_date=None, expiry_date=None):
        adj = {
            "warehouse_id": warehouse_id,
            "position_id": position_id,
            "product_id": product_id,
            "quantity_delta": quantity_delta,
            "allocated_delta": allocated_delta,
            "lot_number": lot_number,
        }
        self.location_adjustments.append(adj)
        return {
            "id": 1,
            "warehouse_id": warehouse_id,
            "position_id": position_id,
            "product_id": product_id,
            "lpn": lpn,
            "lot_number": lot_number,
            "mfg_date": mfg_date,
            "expiry_date": expiry_date,
            "allocated_qty": allocated_delta,
            "status": status,
        }

    def get_inventory_locations(self, warehouse_id=None, product_id=None, status=None, for_update=False):
        self.last_for_update = for_update
        return [loc for loc in self.locations if (warehouse_id is None or loc["warehouse_id"] == warehouse_id) and (product_id is None or loc["product_id"] == product_id)]

    def get_low_stock_items(self, threshold=10):
        mock_item = MagicMock()
        mock_item.product_id = 99
        mock_item.quantity = 3
        return [mock_item]


def test_sale_execution_enforces_reservation():
    """FLOW-02: SALE order requires reservation before starting execution."""
    doc_repo = InMemoryDocumentRepo()
    service = DocumentService(document_repo=doc_repo)

    doc = service.create_sale_document(
        from_warehouse_id=1,
        items=[{"product_id": 101, "quantity": 5, "unit_price": 10.0}],
        created_by="tester",
    )
    service.approve_request(doc.document_id, approved_by="manager")

    # Attempt execution without reservation must fail
    with pytest.raises(InvalidDocumentStatusError, match="must have active reservation"):
        service.start_execution(doc.document_id)

    # Set item reserved_qty > 0 to simulate active reservation
    doc.items[0].reserved_qty = 5
    service.start_execution(doc.document_id)
    assert doc.status == DocumentStatus.IN_PROGRESS


def test_partial_fulfillment_releases_remainder():
    """EDGE-01: Partial fulfillment automatically releases surplus reservation."""
    doc_repo = InMemoryDocumentRepo()
    inv_repo = InMemoryInventoryRepo()
    service = DocumentService(document_repo=doc_repo, inventory_repo=inv_repo)

    doc = service.create_sale_document(
        from_warehouse_id=1,
        items=[{"product_id": 101, "quantity": 100, "unit_price": 10.0}],
        created_by="tester",
    )
    doc.items[0].reserved_qty = 100
    inv_repo.reservations[10] = {
        "id": 10,
        "product_id": 101,
        "warehouse_id": 1,
        "document_id": doc.document_id,
        "reserved_qty": 100,
        "status": "RESERVED",
    }

    doc.status = DocumentStatus.IN_PROGRESS
    doc_repo.save(doc)

    # Confirm partial execution of 80 out of 100
    service.confirm_execution(
        doc.document_id,
        items=[{"product_id": 101, "quantity": 80}],
    )

    # Surplus 20 should be released
    assert inv_repo.reservations[10]["reserved_qty"] == 80
    assert doc.items[0].reserved_qty == 80
    assert doc.status == DocumentStatus.EXECUTED


def test_cycle_count_auto_adjusts_inventory():
    """FLOW-04: Cycle count approval automatically adjusts inventory locations."""
    from app.shared.core.database import Base, import_all_models
    from app.modules.documents.infrastructure.models.cycle_count_sheet import CycleCountSheetModel
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    import_all_models()
    Base.metadata.create_all(bind=engine)
    CycleCountSheetModel.__table__.create(bind=engine, checkfirst=True)
    session = sessionmaker(bind=engine)()

    inv_repo = InMemoryInventoryRepo()
    cc_service = CycleCountService(session=session, inventory_repo=inv_repo)

    item = CycleCountItem(
        item_id="ITEM-1",
        product_id=50,
        location_id="1",
        lot_number="LOT-ABC",
        system_qty=10,
    )
    sheet = cc_service.create_cycle_count_sheet(
        cycle_count_id="CC-101",
        warehouse_id=1,
        title="Test Cycle Count",
        items=[item],
    )
    cc_service.start_cycle_count("CC-101", assigned_to="counter1")
    cc_service.record_counts("CC-101", {"ITEM-1": 12})
    cc_service.submit_counts("CC-101")
    cc_service.approve_cycle_count("CC-101", supervisor_id="boss")

    assert len(inv_repo.location_adjustments) == 1
    adj = inv_repo.location_adjustments[0]
    assert adj["product_id"] == 50
    assert adj["quantity_delta"] == 2
    assert adj["lot_number"] == "LOT-ABC"


def test_allocate_fefo_uses_row_locking():
    """EDGE-03: FEFO allocation requests row locking via for_update=True."""
    inv_repo = InMemoryInventoryRepo()
    inv_repo.locations = [
        {
            "id": 1,
            "warehouse_id": 1,
            "position_id": 10,
            "product_id": 100,
            "available_qty": 20,
            "status": "AVAILABLE",
            "expiry_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }
    ]
    alloc_service = AllocationService(inventory_repo=inv_repo)
    result = alloc_service.allocate_fefo(warehouse_id=1, product_id=100, quantity=10)

    assert len(result) == 1
    assert inv_repo.last_for_update is True


def test_get_low_stock_products_uses_sql_filter():
    """EDGE-09: Low stock query delegates to repository SQL filter."""
    inv_repo = InMemoryInventoryRepo()
    inv_service = InventoryService(inventory_repo=inv_repo)

    low_stock = inv_service.get_low_stock_products(threshold=10)
    assert len(low_stock) == 1
    assert low_stock[0]["product_id"] == 99
    assert low_stock[0]["current_quantity"] == 3
