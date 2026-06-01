from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_warehouse_service
from app.modules.warehouses.application.dtos.warehouse import WarehouseCreate, WarehouseResponse
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.shared.core.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/", response_model=list[WarehouseResponse])
async def get_all_warehouses(service: WarehouseService = Depends(get_warehouse_service)):
    warehouses = service.get_all_warehouses()
    return [WarehouseResponse.from_domain(warehouse) for warehouse in warehouses]


@router.post(
    "/",
    response_model=WarehouseResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def create_warehouse(
    warehouse: WarehouseCreate,
    service: WarehouseService = Depends(get_warehouse_service),
):
    created_warehouse = service.create_warehouse(warehouse.name)
    return WarehouseResponse.from_domain(created_warehouse)


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(
    warehouse_id: int, service: WarehouseService = Depends(get_warehouse_service)
):
    warehouse = service.get_warehouse(warehouse_id)
    return WarehouseResponse.from_domain(warehouse)


@router.delete(
    "/{warehouse_id}",
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def delete_warehouse(
    warehouse_id: int, service: WarehouseService = Depends(get_warehouse_service)
):
    service.delete_warehouse(warehouse_id)
    return {"message": f"Warehouse {warehouse_id} deleted successfully"}
