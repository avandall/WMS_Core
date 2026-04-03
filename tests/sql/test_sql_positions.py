from sqlalchemy import select

from app.infrastructure.persistence.repositories.audit_event_repo import AuditEventRepo
from app.infrastructure.persistence.repositories.position_repo import PositionRepo
from app.infrastructure.persistence.repositories.warehouse_repo import WarehouseRepo
from app.infrastructure.persistence.models import (
    AuditEventModel,
    PositionInventoryModel,
    PositionModel,
    ProductModel,
    WarehouseInventoryModel,
    WarehouseModel,
)
from app.application.services.stock_movement_service import StockMovementService


def _seed_basic(session, *, warehouse_id: int, location: str, product_id: int, qty: int):
    session.add(WarehouseModel(warehouse_id=warehouse_id, location=location))
    session.add(ProductModel(product_id=product_id, name="Test Product", price=0.0))
    if qty:
        session.add(
            WarehouseInventoryModel(
                warehouse_id=warehouse_id, product_id=product_id, quantity=qty
            )
        )
    session.commit()


def test_move_within_warehouse_reconciles_unassigned(test_session):
    _seed_basic(test_session, warehouse_id=1, location="W1", product_id=100, qty=10)

    pos_repo = PositionRepo(test_session)
    wh_repo = WarehouseRepo(test_session)
    audit_repo = AuditEventRepo(test_session)

    svc = StockMovementService(
        position_repo=pos_repo,
        warehouse_repo=wh_repo,
        session=test_session,
        audit_event_repo=audit_repo,
    )

    svc.move_within_warehouse(
        warehouse_id=1,
        product_id=100,
        quantity=4,
        from_position_code="UNASSIGNED",
        to_position_code="STORAGE",
    )

    unassigned = pos_repo.get_position_model(1, "UNASSIGNED")
    storage = pos_repo.get_position_model(1, "STORAGE")

    inv = {
        row.position_id: row.quantity
        for row in test_session.execute(select(PositionInventoryModel)).scalars().all()
    }
    assert inv[unassigned.id] == 6
    assert inv[storage.id] == 4

    events = test_session.execute(select(AuditEventModel)).scalars().all()
    assert any(e.action == "STOCK_MOVED" for e in events)


def test_transfer_between_warehouses_updates_totals_and_positions(test_session):
    _seed_basic(test_session, warehouse_id=1, location="W1", product_id=100, qty=10)
    test_session.add(WarehouseModel(warehouse_id=2, location="W2"))
    test_session.commit()

    pos_repo = PositionRepo(test_session)
    wh_repo = WarehouseRepo(test_session)
    audit_repo = AuditEventRepo(test_session)
    svc = StockMovementService(
        position_repo=pos_repo,
        warehouse_repo=wh_repo,
        session=test_session,
        audit_event_repo=audit_repo,
    )

    # Put away some stock so STORAGE has inventory.
    svc.move_within_warehouse(
        warehouse_id=1,
        product_id=100,
        quantity=5,
        from_position_code="UNASSIGNED",
        to_position_code="STORAGE",
    )

    result = svc.transfer_between_warehouses(
        from_warehouse_id=1,
        to_warehouse_id=2,
        product_id=100,
        quantity=3,
        from_position_code="STORAGE",
        to_position_code="RECEIVING",
    )
    assert result["quantity"] == 3

    # Warehouse-level totals
    w1_qty = test_session.execute(
        select(WarehouseInventoryModel.quantity).where(
            WarehouseInventoryModel.warehouse_id == 1,
            WarehouseInventoryModel.product_id == 100,
        )
    ).scalar_one()
    assert w1_qty == 7

    w2_qty = test_session.execute(
        select(WarehouseInventoryModel.quantity).where(
            WarehouseInventoryModel.warehouse_id == 2,
            WarehouseInventoryModel.product_id == 100,
        )
    ).scalar_one()
    assert w2_qty == 3

    # Position-level totals (sum across bins == warehouse totals)
    def _sum_positions(warehouse_id: int) -> int:
        rows = (
            test_session.execute(
                select(PositionInventoryModel)
                .join(PositionModel, PositionModel.id == PositionInventoryModel.position_id)
                .where(PositionModel.warehouse_id == warehouse_id, PositionInventoryModel.product_id == 100)
            )
            .scalars()
            .all()
        )
        return sum(r.quantity for r in rows)

    assert _sum_positions(1) == 7
    assert _sum_positions(2) == 3

