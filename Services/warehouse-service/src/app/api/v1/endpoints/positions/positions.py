from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_position_service
from app.modules.positions.application.dtos.position import (
    PositionCreate,
    PositionResponse,
)
from app.modules.positions.application.services.position_service import PositionService
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

