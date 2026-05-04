"""Dependency injection for API services (per-request DB session)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.customers.application.services.customer_service import CustomerService
from app.modules.documents.application.services.document_service import DocumentService
from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.positions.application.services.position_service import PositionService
from app.modules.products.application.services.product_service import ProductService
from app.shared.application.services.report_orchestrator import ReportOrchestrator
from app.modules.inventory.application.services.stock_movement_service import StockMovementService
from app.modules.users.application.services.user_service import UserService
from app.modules.warehouses.application.services.warehouse_operations_service import (
    WarehouseOperationsService,
)
from app.modules.warehouses.application.services.warehouse_service import WarehouseService
from app.shared.core.database import get_session
from app.api.dependencies.service_factory import RepositoryContainerImpl
from app.modules.audit.infrastructure.repositories.audit_event_repo import AuditEventRepo
from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
from app.modules.documents.infrastructure.repositories.document_repo import DocumentRepo
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.positions.infrastructure.repositories.position_repo import PositionRepo
from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo


def get_product_repo(db: Session = Depends(get_session)) -> ProductRepo:
    return ProductRepo(db)


def get_inventory_repo(db: Session = Depends(get_session)) -> InventoryRepo:
    return InventoryRepo(db)


def get_warehouse_repo(db: Session = Depends(get_session)) -> WarehouseRepo:
    return WarehouseRepo(db)


def get_document_repo(db: Session = Depends(get_session)) -> DocumentRepo:
    return DocumentRepo(db)


def get_customer_repo(db: Session = Depends(get_session)) -> CustomerRepo:
    return CustomerRepo(db)


def get_position_repo(db: Session = Depends(get_session)) -> PositionRepo:
    return PositionRepo(db)


def get_audit_event_repo(db: Session = Depends(get_session)) -> AuditEventRepo:
    return AuditEventRepo(db)


def get_user_repo(db: Session = Depends(get_session)) -> UserRepo:
    return UserRepo(db)


def get_product_service(db: Session = Depends(get_session)) -> ProductService:
    return ProductService(product_repo=ProductRepo(db), inventory_repo=InventoryRepo(db))


def get_inventory_service(db: Session = Depends(get_session)) -> InventoryService:
    return InventoryService(
        inventory_repo=InventoryRepo(db),
        product_repo=ProductRepo(db),
        warehouse_repo=WarehouseRepo(db),
    )


def get_warehouse_service(db: Session = Depends(get_session)) -> WarehouseService:
    return WarehouseService(
        warehouse_repo=WarehouseRepo(db),
        product_repo=ProductRepo(db),
        inventory_repo=InventoryRepo(db),
    )


def get_document_service(db: Session = Depends(get_session)) -> DocumentService:
    return DocumentService(
        document_repo=DocumentRepo(db),
        warehouse_repo=WarehouseRepo(db),
        product_repo=ProductRepo(db),
        inventory_repo=InventoryRepo(db),
        customer_repo=CustomerRepo(db),
        position_repo=PositionRepo(db),
        audit_event_repo=AuditEventRepo(db),
        session=db,
    )


def get_position_service(db: Session = Depends(get_session)) -> PositionService:
    return PositionService(position_repo=PositionRepo(db), audit_event_repo=AuditEventRepo(db))


def get_stock_movement_service(db: Session = Depends(get_session)) -> StockMovementService:
    return StockMovementService(
        position_repo=PositionRepo(db),
        warehouse_repo=WarehouseRepo(db),
        session=db,
        audit_event_repo=AuditEventRepo(db),
    )


def get_report_service(db: Session = Depends(get_session)) -> ReportOrchestrator:
    return ReportOrchestrator(
        product_repo=ProductRepo(db),
        document_repo=DocumentRepo(db),
        warehouse_repo=WarehouseRepo(db),
        inventory_repo=InventoryRepo(db),
        customer_repo=CustomerRepo(db),
    )


def get_customer_service(db: Session = Depends(get_session)) -> CustomerService:
    return CustomerService(customer_repo=CustomerRepo(db))


def get_user_service(db: Session = Depends(get_session)) -> UserService:
    return UserService(user_repo=UserRepo(db))




def get_repository_container(db: Session = Depends(get_session)) -> RepositoryContainerImpl:
    """Get repository container for Unit of Work pattern."""
    return RepositoryContainerImpl(db)


def get_warehouse_operations_service(db: Session = Depends(get_session)) -> WarehouseOperationsService:
    return WarehouseOperationsService(
        warehouse_repo=WarehouseRepo(db),
        product_repo=ProductRepo(db),
        inventory_repo=InventoryRepo(db),
        document_repo=DocumentRepo(db),
    )
