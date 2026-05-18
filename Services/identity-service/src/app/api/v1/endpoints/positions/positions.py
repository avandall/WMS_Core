from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_position_service, get_stock_movement_service
from app.modules.positions.application.dtos.position import (
    PositionCreate,
    PositionInventoryItemResponse,
    PositionMoveRequest,
    PositionResponse,
    WarehouseTransferPositionRequest,
)
from app.modules.positions.application.services.position_service import PositionService
from app.modules.inventory.application.services.stock_movement_service import StockMovementService
from app.shared.core.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get(
    "/warehouses/{warehouse_id}/positions",
    response_model=list[PositionResponse],
)
async def list_positions(warehouse_id: int, service: PositionService = Depends(get_position_service)):
    positions = service.list_positions(warehouse_id)
    return [
        PositionResponse(
            id=p.id,
            warehouse_id=p.warehouse_id,
            code=p.code,
            type=p.type,
            description=p.description,
            is_active=p.is_active,
        )
        for p in positions
    ]


@router.post(
    "/warehouses/{warehouse_id}/positions",
    response_model=PositionResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def create_position(
    warehouse_id: int,
    data: PositionCreate,
    service: PositionService = Depends(get_position_service),
    current_user=Depends(get_current_user),
):
    pos = service.create_position(
        warehouse_id=warehouse_id,
        code=data.code,
        type=data.type,
        description=data.description,
        user_id=getattr(current_user, "user_id", None),
    )
    return PositionResponse(
        id=pos.id,
        warehouse_id=pos.warehouse_id,
        code=pos.code,
        type=pos.type,
        description=pos.description,
        is_active=pos.is_active,
    )


@router.get(
    "/warehouses/{warehouse_id}/positions/{code}/inventory",
    response_model=list[PositionInventoryItemResponse],
)
async def get_position_inventory(
    warehouse_id: int, code: str, service: PositionService = Depends(get_position_service)
):
    items = service.list_position_inventory(warehouse_id, code)
    return [PositionInventoryItemResponse(product_id=i.product_id, quantity=i.quantity) for i in items]


@router.post(
    "/warehouses/{warehouse_id}/positions/move",
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def move_stock_within_warehouse(
    warehouse_id: int,
    data: PositionMoveRequest,
    service: StockMovementService = Depends(get_stock_movement_service),
    current_user=Depends(get_current_user),
):
    return service.move_within_warehouse(
        warehouse_id=warehouse_id,
        product_id=data.product_id,
        quantity=data.quantity,
        from_position_code=data.from_position,
        to_position_code=data.to_position,
        user_id=getattr(current_user, "user_id", None),
    )


@router.post(
    "/warehouses/{warehouse_id}/pick",
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def pick(
    warehouse_id: int,
    data: PositionMoveRequest,
    service: StockMovementService = Depends(get_stock_movement_service),
    current_user=Depends(get_current_user),
):
    return service.pick(
        warehouse_id=warehouse_id,
        product_id=data.product_id,
        quantity=data.quantity,
        from_position_code=data.from_position,
        to_position_code=data.to_position,
        user_id=getattr(current_user, "user_id", None),
    )


@router.post(
    "/warehouses/{warehouse_id}/put-away",
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def put_away(
    warehouse_id: int,
    data: PositionMoveRequest,
    service: StockMovementService = Depends(get_stock_movement_service),
    current_user=Depends(get_current_user),
):
    return service.put_away(
        warehouse_id=warehouse_id,
        product_id=data.product_id,
        quantity=data.quantity,
        from_position_code=data.from_position,
        to_position_code=data.to_position,
        user_id=getattr(current_user, "user_id", None),
    )


@router.post(
    "/positions/transfer",
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def transfer_between_warehouses(
    data: WarehouseTransferPositionRequest,
    service: StockMovementService = Depends(get_stock_movement_service),
    current_user=Depends(get_current_user),
):
    return service.transfer_between_warehouses(
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        product_id=data.product_id,
        quantity=data.quantity,
        from_position_code=data.from_position,
        to_position_code=data.to_position,
        user_id=getattr(current_user, "user_id", None),
    )

