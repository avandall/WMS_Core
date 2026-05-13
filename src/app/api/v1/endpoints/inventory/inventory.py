from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_inventory_service
from app.modules.products.application.dtos.product import InventoryItemResponse, WarehouseInventoryRowResponse
from app.modules.inventory.application.services.inventory_service import InventoryService
from app.shared.core.permissions import Permission

router = APIRouter(
    dependencies=[
        Depends(get_current_user),
        Depends(require_permissions(Permission.VIEW_INVENTORY)),
    ]
)


@router.get("/", response_model=List[InventoryItemResponse])
async def get_all_inventory(service: InventoryService = Depends(get_inventory_service)):
    items = service.get_all_inventory_items()
    return [InventoryItemResponse.from_domain(item) for item in items]


@router.get("/by-warehouse", response_model=List[WarehouseInventoryRowResponse])
async def get_inventory_by_warehouse(service: InventoryService = Depends(get_inventory_service)):
    rows = service.get_inventory_by_warehouse_rows()
    return [WarehouseInventoryRowResponse(**row) for row in rows]


@router.get("/{product_id}")
async def get_product_quantity(
    product_id: int, service: InventoryService = Depends(get_inventory_service)
):
    quantity = await service.get_total_quantity(product_id)
    return {"product_id": product_id, "quantity": quantity}
