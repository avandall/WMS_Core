from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_warehouse_service
from app.modules.products.application.dtos.product import (
    InventoryItemResponse,
    TransferInventoryRequest,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseTransferResponse,
)
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.shared.core.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/", response_model=list[WarehouseResponse])
async def get_all_warehouses(service: WarehouseService = Depends(get_warehouse_service)):
    warehouses = await service.get_all_warehouses()
    result = []
    for warehouse in warehouses:
        inventory = await service.get_warehouse_inventory(warehouse.warehouse_id)
        result.append(
            WarehouseResponse(
                warehouse_id=warehouse.warehouse_id,
                name=warehouse.location,
                location=warehouse.location,
                inventory=[InventoryItemResponse.from_domain(item) for item in inventory],
            )
        )
    return result


@router.post(
    "/",
    response_model=WarehouseResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def create_warehouse(
    warehouse: WarehouseCreate,
    service: WarehouseService = Depends(get_warehouse_service),
):
    created_warehouse = await service.create_warehouse(warehouse.name)
    return WarehouseResponse.from_domain(created_warehouse)


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(
    warehouse_id: int, service: WarehouseService = Depends(get_warehouse_service)
):
    warehouse = await service.get_warehouse(warehouse_id)
    inventory = await service.get_warehouse_inventory(warehouse_id)
    return WarehouseResponse(
        warehouse_id=warehouse.warehouse_id,
        name=warehouse.location,
        location=warehouse.location,
        inventory=[InventoryItemResponse.from_domain(item) for item in inventory],
    )


@router.delete(
    "/{warehouse_id}",
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def delete_warehouse(
    warehouse_id: int, service: WarehouseService = Depends(get_warehouse_service)
):
    await service.delete_warehouse(warehouse_id)
    return {"message": f"Warehouse {warehouse_id} deleted successfully"}


@router.post(
    "/{warehouse_id}/transfer",
    response_model=WarehouseTransferResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def transfer_all_inventory(
    warehouse_id: int,
    transfer_request: TransferInventoryRequest,
    service: WarehouseService = Depends(get_warehouse_service),
):
    transferred_items = await service.transfer_all_inventory(
        warehouse_id, transfer_request.to_warehouse_id
    )
    return WarehouseTransferResponse(
        from_warehouse_id=warehouse_id,
        to_warehouse_id=transfer_request.to_warehouse_id,
        transferred_items=[InventoryItemResponse.from_domain(item) for item in transferred_items],
        message=f"Successfully transferred {len(transferred_items)} product(s) from warehouse {warehouse_id} to {transfer_request.to_warehouse_id}",
    )

