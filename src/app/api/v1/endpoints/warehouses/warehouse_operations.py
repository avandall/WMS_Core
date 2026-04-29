from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_warehouse_operations_service
from app.modules.warehouses.application.services.warehouse_operations_service import WarehouseOperationsService
from app.shared.core.permissions import Permission

router = APIRouter(
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))]
)


@router.get("/system-overview")
async def get_system_overview(service: WarehouseOperationsService = Depends(get_warehouse_operations_service)):
    return service.get_system_overview()


@router.get("/inventory-health")
async def get_inventory_health_report(service: WarehouseOperationsService = Depends(get_warehouse_operations_service)):
    return service.get_inventory_health_report()


@router.get("/optimize-distribution/{product_id}")
async def optimize_inventory_distribution(
    product_id: int,
    service: WarehouseOperationsService = Depends(get_warehouse_operations_service),
):
    result = service.optimize_inventory_distribution(product_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/bulk-transfer")
async def bulk_transfer_products(
    transfers: List[Dict[str, Any]],
    service: WarehouseOperationsService = Depends(get_warehouse_operations_service),
):
    return service.bulk_transfer_products(transfers)
