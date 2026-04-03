from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.auth_deps import get_current_user, require_permissions
from app.api.dependencies import get_report_service
from app.application.services.report_service import ReportService
from app.core.permissions import Permission

router = APIRouter(
    dependencies=[Depends(get_current_user), Depends(require_permissions(Permission.VIEW_REPORTS))]
)


@router.get("/inventory")
async def get_inventory_report(
    warehouse_id: Optional[int] = None,
    low_stock_threshold: int = 10,
    service: ReportService = Depends(get_report_service),
):
    return service.generate_inventory_report(
        warehouse_id=warehouse_id, low_stock_threshold=low_stock_threshold
    )


@router.get("/inventory/list")
async def get_inventory_list(service: ReportService = Depends(get_report_service)):
    return service.list_inventory_by_warehouse()


@router.get("/warehouse/{warehouse_id}")
async def get_warehouse_report(
    warehouse_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    service: ReportService = Depends(get_report_service),
):
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    return service.generate_warehouse_performance_report(
        warehouse_id=warehouse_id, start_date=start, end_date=end
    )


@router.get("/documents")
async def get_document_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    service: ReportService = Depends(get_report_service),
):
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    return service.list_documents_report(start_date=start, end_date=end)


@router.get("/product/{product_id}")
async def get_product_report(
    product_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    service: ReportService = Depends(get_report_service),
):
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    return service.generate_product_movement_report(product_id=product_id, start_date=start, end_date=end)


@router.get("/sales")
async def get_sales_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    salesperson: Optional[str] = None,
    service: ReportService = Depends(get_report_service),
):
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    return service.generate_sales_report(
        start_date=start,
        end_date=end,
        customer_id=customer_id,
        salesperson=salesperson,
    )
