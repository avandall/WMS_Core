from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
REPORTING_SRC = ROOT_DIR / "Services/reporting-service/src"
SHARED_UTILS_SRC = ROOT_DIR / "Libraries/shared-utils/src"
sys.path.insert(0, str(REPORTING_SRC))
sys.path.insert(0, str(SHARED_UTILS_SRC))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from shared_utils.events import build_event

from app.modules.reporting.infrastructure.repositories.read_model_repo import ReportingReadModelRepo


class FakeQuery:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.criteria: tuple[object, ...] = ()

    def filter(self, *args, **kwargs):
        _ = args, kwargs
        self.criteria = args
        return self

    def order_by(self, *args, **kwargs):
        _ = args, kwargs
        return self

    def all(self) -> list[object]:
        return self.rows

    def one_or_none(self):
        for criterion in self.criteria:
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            field = getattr(left, "key", None)
            value = getattr(right, "value", None)
            if field and value is not None:
                for row in self.rows:
                    if getattr(row, field, None) == value:
                        return row
                return None
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self) -> None:
        self.objects: dict[tuple[type, object], object] = {}

    def add(self, obj: object) -> None:
        key = self._key(obj)
        self.objects[key] = obj

    def get(self, model: type, identity: object):
        return self.objects.get((model, identity))

    def query(self, model: type) -> FakeQuery:
        rows = [obj for (obj_model, _), obj in self.objects.items() if obj_model is model]
        return FakeQuery(rows)

    @staticmethod
    def _key(obj: object) -> tuple[type, object]:
        for attr in ("event_id", "product_id", "document_id", "warehouse_id"):
            if hasattr(obj, attr):
                return (type(obj), getattr(obj, attr))
        raise AssertionError(f"Unsupported fake model: {obj!r}")


def test_reporting_projects_document_and_inventory_events() -> None:
    session = FakeSession()
    repo = ReportingReadModelRepo(session)  # type: ignore[arg-type]

    repo.record_event(
        stream_id="1-0",
        envelope=build_event(
            source="documents-service",
            event_type="DocumentUploaded",
            payload={
                "event_id": "doc-uploaded-1",
                "entity_type": "document",
                "entity_id": 1,
                "document_id": 1,
                "doc_type": "SALE",
                "status": "DRAFT",
                "customer_id": 7,
                "from_warehouse_id": 10,
                "items": [{"product_id": 100, "quantity": 2, "unit_price": 5}],
            },
        ),
    )
    repo.record_event(
        stream_id="2-0",
        envelope=build_event(
            source="inventory-service",
            event_type="InventoryMovementApplied",
            payload={
                "event_id": "movement-applied-1",
                "entity_type": "document",
                "entity_id": 1,
                "document_id": 1,
                "doc_type": "SALE",
                "from_warehouse_id": 10,
                "items": [{"product_id": 100, "quantity": 2}],
            },
        ),
    )

    documents = repo.documents_report()["documents"]
    inventory = repo.inventory_report()["items"]
    sales = repo.sales_report(customer_id=7, salesperson=None)["items"]
    warehouse = repo.warehouse_report(warehouse_id=10)["items"]

    assert documents[0]["status"] == "DRAFT"
    assert sales[0]["total_value"] == 10.0
    assert inventory[0]["product_id"] == 100
    assert inventory[0]["quantity"] == -2
    assert inventory[0]["warehouse_quantities"] == {"10": -2}
    assert warehouse[0]["movement_count"] == 1


def test_reporting_event_idempotency_skips_duplicate_projection() -> None:
    session = FakeSession()
    repo = ReportingReadModelRepo(session)  # type: ignore[arg-type]
    envelope = build_event(
        source="inventory-service",
        event_type="InventoryAdjusted",
        payload={
            "event_id": "adjust-1",
            "entity_type": "inventory",
            "entity_id": 100,
            "product_id": 100,
            "quantity_delta": 5,
        },
    )

    assert repo.record_event(stream_id="1-0", envelope=envelope) is True
    assert repo.record_event(stream_id="1-0", envelope=envelope) is False

    assert repo.inventory_report()["items"][0]["quantity"] == 5
