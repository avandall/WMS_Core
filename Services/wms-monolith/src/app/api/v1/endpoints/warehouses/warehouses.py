from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_warehouse_service
from app.api.grpc_warehouse_client import (
    create_warehouse as grpc_create_warehouse,
    delete_warehouse as grpc_delete_warehouse,
    get_warehouse as grpc_get_warehouse,
    list_warehouses as grpc_list_warehouses,
    transfer_all_inventory as grpc_transfer_all_inventory,
)
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
async def get_all_warehouses(request: Request, service: WarehouseService = Depends(get_warehouse_service)):
    if os.getenv("WAREHOUSE_GRPC", "1") == "1":
        data = grpc_list_warehouses()
        result = []
        for w in data:
            result.append(
                WarehouseResponse(
                    warehouse_id=w["warehouse_id"],
                    name=w["location"],
                    location=w["location"],
                    inventory=[
                        InventoryItemResponse(product_id=i["product_id"], quantity=i["quantity"])
                        for i in w.get("inventory", [])
                    ],
                )
            )
        return result
    warehouses = service.get_all_warehouses()
    result = []
    for warehouse in warehouses:
        inventory = service.get_warehouse_inventory(warehouse.warehouse_id)
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
    request: Request,
    service: WarehouseService = Depends(get_warehouse_service),
):
    if os.getenv("WAREHOUSE_GRPC", "1") == "1":
        w = grpc_create_warehouse(warehouse.name)
        return WarehouseResponse(
            warehouse_id=w["warehouse_id"],
            name=w["location"],
            location=w["location"],
            inventory=[],
        )
    created_warehouse = service.create_warehouse(warehouse.name)
    return WarehouseResponse.from_domain(created_warehouse)


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(
    warehouse_id: int,
    request: Request,
    service: WarehouseService = Depends(get_warehouse_service),
):
    if os.getenv("WAREHOUSE_GRPC", "1") == "1":
        w = grpc_get_warehouse(warehouse_id)
        if not w:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        return WarehouseResponse(
            warehouse_id=w["warehouse_id"],
            name=w["location"],
            location=w["location"],
            inventory=[
                InventoryItemResponse(product_id=i["product_id"], quantity=i["quantity"])
                for i in w.get("inventory", [])
            ],
        )
    warehouse = service.get_warehouse(warehouse_id)
    inventory = service.get_warehouse_inventory(warehouse_id)
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
    warehouse_id: int,
    request: Request,
    service: WarehouseService = Depends(get_warehouse_service),
):
    if os.getenv("WAREHOUSE_GRPC", "1") == "1":
        resp = grpc_delete_warehouse(warehouse_id)
        if not resp:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        return resp
    service.delete_warehouse(warehouse_id)
    return {"message": f"Warehouse {warehouse_id} deleted successfully"}


@router.post(
    "/{warehouse_id}/transfer",
    response_model=WarehouseTransferResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_WAREHOUSES))],
)
async def transfer_all_inventory(
    warehouse_id: int,
    transfer_request: TransferInventoryRequest,
    request: Request,
    service: WarehouseService = Depends(get_warehouse_service),
):
    if os.getenv("WAREHOUSE_GRPC", "1") == "1":
        resp = grpc_transfer_all_inventory(warehouse_id, transfer_request.to_warehouse_id)
        return WarehouseTransferResponse(
            from_warehouse_id=resp["from_warehouse_id"],
            to_warehouse_id=resp["to_warehouse_id"],
            transferred_items=[
                InventoryItemResponse(product_id=i["product_id"], quantity=i["quantity"])
                for i in resp["transferred_items"]
            ],
            message=resp["message"],
        )
    transferred_items = service.transfer_all_inventory(
        warehouse_id, transfer_request.to_warehouse_id
    )
    return WarehouseTransferResponse(
        from_warehouse_id=warehouse_id,
        to_warehouse_id=transfer_request.to_warehouse_id,
        transferred_items=[InventoryItemResponse.from_domain(item) for item in transferred_items],
        message=f"Successfully transferred {len(transferred_items)} product(s) from warehouse {warehouse_id} to {transfer_request.to_warehouse_id}",
    )
