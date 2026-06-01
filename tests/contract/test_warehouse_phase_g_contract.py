from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict


ROOT_DIR = Path(__file__).resolve().parents[2]
WAREHOUSE_SRC = ROOT_DIR / "Services/warehouse-service/src"
sys.path.insert(0, str(WAREHOUSE_SRC))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from app.modules.positions.application.services.position_service import PositionService
from app.modules.positions.domain.entities.position import Position
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.modules.warehouses.domain.value_objects import BinCode, PositionType, WarehouseLocation
from app.shared.domain.business_exceptions import EntityAlreadyExistsError


class InMemoryWarehouseRepo:
    def __init__(self) -> None:
        self.warehouses: Dict[int, Warehouse] = {}

    def create_warehouse(self, warehouse: Warehouse) -> None:
        self.warehouses[warehouse.warehouse_id] = warehouse

    def save(self, warehouse: Warehouse) -> None:
        self.warehouses[warehouse.warehouse_id] = warehouse

    def get(self, warehouse_id: int) -> Warehouse | None:
        return self.warehouses.get(warehouse_id)

    def get_all(self) -> Dict[int, Warehouse]:
        return dict(self.warehouses)

    def delete(self, warehouse_id: int) -> None:
        self.warehouses.pop(warehouse_id, None)

    def location_exists(self, location: str, *, excluding_warehouse_id: int | None = None) -> bool:
        return any(
            warehouse.location == location and warehouse.warehouse_id != excluding_warehouse_id
            for warehouse in self.warehouses.values()
        )


class InMemoryPositionRepo:
    def __init__(self) -> None:
        self.positions: dict[tuple[int, str], Position] = {}

    def ensure_default_positions(self, warehouse_id: int) -> None:
        for code, pos_type in [
            ("RECEIVING", "RECEIVING"),
            ("STORAGE", "STORAGE"),
            ("SHIPPING", "SHIPPING"),
            ("UNASSIGNED", "SYSTEM"),
        ]:
            self.positions.setdefault(
                (warehouse_id, code),
                Position(
                    id=len(self.positions) + 1,
                    warehouse_id=warehouse_id,
                    code=code,
                    type=pos_type,
                ),
            )

    def create_position(
        self,
        *,
        warehouse_id: int,
        code: str,
        type: str = "STORAGE",
        description: str | None = None,
    ) -> Position:
        position = Position(
            id=len(self.positions) + 1,
            warehouse_id=warehouse_id,
            code=code,
            type=type,
            description=description,
        )
        self.positions[(warehouse_id, position.code)] = position
        return position

    def list_positions(self, warehouse_id: int, *, include_inactive: bool = False) -> list[Position]:
        _ = include_inactive
        return [
            position
            for (row_warehouse_id, _), position in self.positions.items()
            if row_warehouse_id == warehouse_id
        ]

    def get_position(self, warehouse_id: int, code: str) -> Position:
        return self.positions[(warehouse_id, BinCode(code).value)]

    def get_position_model(self, warehouse_id: int, code: str):
        return self.get_position(warehouse_id, code)


def test_warehouse_location_and_bin_value_objects_normalize_inputs() -> None:
    assert WarehouseLocation("  Main   Warehouse ").value == "Main Warehouse"
    assert BinCode(" a-01 ").value == "A-01"
    assert PositionType("storage").value == "STORAGE"


def test_warehouse_service_exposes_creation_update_and_lookup_use_cases() -> None:
    repo = InMemoryWarehouseRepo()
    next_id = iter([1, 2]).__next__
    service = WarehouseService(repo, id_generator=next_id)

    warehouse = service.create_warehouse("  Main   Warehouse ")
    updated = service.update_warehouse_location(warehouse.warehouse_id, " Secondary ")

    assert warehouse.warehouse_id == 1
    assert updated.location == "Secondary"
    assert service.get_warehouse_location_metadata(1) == {
        "warehouse_id": 1,
        "location": "Secondary",
        "owns_inventory_quantity": False,
    }


def test_warehouse_service_rejects_duplicate_locations() -> None:
    repo = InMemoryWarehouseRepo()
    service = WarehouseService(repo, id_generator=iter([1, 2]).__next__)
    service.create_warehouse("Main")

    try:
        service.create_warehouse(" Main ")
    except EntityAlreadyExistsError:
        pass
    else:
        raise AssertionError("duplicate location was accepted")


def test_position_service_models_bins_without_inventory_quantities() -> None:
    repo = InMemoryPositionRepo()
    service = PositionService(repo)

    position = service.create_position(warehouse_id=1, code=" pick-01 ", type="picking")

    assert position.code == "PICK-01"
    assert position.type == "PICKING"
    assert not hasattr(position, "quantity")


def test_warehouse_runtime_does_not_import_inventory_repositories() -> None:
    service_source = (
        ROOT_DIR / "Services/warehouse-service/src/app/modules/warehouses/application/services/warehouse_service.py"
    ).read_text()
    repo_source = (
        ROOT_DIR / "Services/warehouse-service/src/app/modules/warehouses/infrastructure/repositories/warehouse_repo.py"
    ).read_text()

    assert "InventoryRepo" not in service_source
    assert "WarehouseInventory" not in repo_source
