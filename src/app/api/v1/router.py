from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.audit_events import router as audit_events_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.customers import router as customers_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.inventory import router as inventory_router
from app.api.v1.endpoints.positions import router as positions_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.warehouse_operations import (
    router as warehouse_operations_router,
)
from app.api.v1.endpoints.warehouses import router as warehouses_router


router = APIRouter()
router.include_router(products_router, prefix="/products", tags=["products"])
router.include_router(warehouses_router, prefix="/warehouses", tags=["warehouses"])
router.include_router(inventory_router, prefix="/inventory", tags=["inventory"])
router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(reports_router, prefix="/reports", tags=["reports"])
router.include_router(customers_router, prefix="/customers", tags=["customers"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(ai_router, tags=["ai"])
router.include_router(positions_router, tags=["positions"])
router.include_router(audit_events_router, prefix="/audit-events", tags=["audit-events"])
router.include_router(
    warehouse_operations_router, prefix="/warehouse-operations", tags=["warehouse-operations"]
)

__all__ = ["router"]
