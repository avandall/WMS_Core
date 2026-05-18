from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_warehouse_operations_service
from app.api.service_proxy import proxy_request
from app.modules.warehouses.application.services.warehouse_operations_service import WarehouseOperationsService
from app.shared.core.permissions import Permission

router = APIRouter(
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))]
)


@router.get("/system-overview")
async def get_system_overview(
    request: Request,
    service: WarehouseOperationsService = Depends(get_warehouse_operations_service),
):
    base = os.getenv("WAREHOUSE_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    return service.get_system_overview()


@router.get("/inventory-health")
async def get_inventory_health_report(
    request: Request,
    service: WarehouseOperationsService = Depends(get_warehouse_operations_service),
):
    base = os.getenv("WAREHOUSE_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    return service.get_inventory_health_report()


@router.get("/optimize-distribution/{product_id}")
async def optimize_inventory_distribution(
    product_id: int,
    request: Request,
    service: WarehouseOperationsService = Depends(get_warehouse_operations_service),
):
    base = os.getenv("WAREHOUSE_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    result = service.optimize_inventory_distribution(product_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/bulk-transfer")
async def bulk_transfer_products(
    transfers: List[Dict[str, Any]],
    request: Request,
    service: WarehouseOperationsService = Depends(get_warehouse_operations_service),
):
    base = os.getenv("WAREHOUSE_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    return service.bulk_transfer_products(transfers)
