"""Service factory implementing DIP principle with UnitOfWork pattern."""

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
from app.shared.application.unit_of_work.unit_of_work import UnitOfWork
from app.api.dependencies.repository_container import RepositoryContainerImpl


class ServiceFactory:
    """Factory for creating services following DIP principle with UnitOfWork."""

    def __init__(self, session: Session):
        self.session = session
        self._repository_container = RepositoryContainerImpl(session)
        self._services = {}

    def get_unit_of_work(self, read_only: bool = False) -> UnitOfWork:
        """Get unit of work instance for transactional operations.
        
        Args:
            read_only: If True, no commit will be performed on exit (for read operations)
        """
        return UnitOfWork(self.session, self._repository_container, read_only=read_only)

    def get_product_service(self) -> ProductService:
        """Get product service with dependency injection."""
        if 'product_service' not in self._services:
            self._services['product_service'] = ProductService(
                product_repo=self._repository_container.product_repo,
                inventory_repo=self._repository_container.inventory_repo,
            )
        return self._services['product_service']

    def get_inventory_service(self) -> InventoryService:
        """Get inventory service with dependency injection."""
        if 'inventory_service' not in self._services:
            self._services['inventory_service'] = InventoryService(
                inventory_repo=self._repository_container.inventory_repo,
                product_repo=self._repository_container.product_repo,
                warehouse_repo=self._repository_container.warehouse_repo,
            )
        return self._services['inventory_service']

    def get_warehouse_service(self) -> WarehouseService:
        """Get warehouse service with dependency injection."""
        if 'warehouse_service' not in self._services:
            self._services['warehouse_service'] = WarehouseService(
                warehouse_repo=self._repository_container.warehouse_repo,
                product_repo=self._repository_container.product_repo,
                inventory_repo=self._repository_container.inventory_repo,
            )
        return self._services['warehouse_service']

    def get_document_service(self) -> DocumentService:
        """Get document service with dependency injection."""
        if 'document_service' not in self._services:
            self._services['document_service'] = DocumentService(
                document_repo=self._repository_container.document_repo,
                warehouse_repo=self._repository_container.warehouse_repo,
                product_repo=self._repository_container.product_repo,
                inventory_repo=self._repository_container.inventory_repo,
                customer_repo=self._repository_container.customer_repo,
                position_repo=self._repository_container.position_repo,
                audit_event_repo=self._repository_container.audit_event_repo,
                session=self.session,
            )
        return self._services['document_service']

    def get_position_service(self) -> PositionService:
        """Get position service with dependency injection."""
        if 'position_service' not in self._services:
            self._services['position_service'] = PositionService(
                position_repo=self._repository_container.position_repo,
                audit_event_repo=self._repository_container.audit_event_repo,
            )
        return self._services['position_service']

    def get_stock_movement_service(self) -> StockMovementService:
        """Get stock movement service with dependency injection."""
        if 'stock_movement_service' not in self._services:
            self._services['stock_movement_service'] = StockMovementService(
                position_repo=self._repository_container.position_repo,
                warehouse_repo=self._repository_container.warehouse_repo,
                session=self.session,
                audit_event_repo=self._repository_container.audit_event_repo,
            )
        return self._services['stock_movement_service']

    def get_report_service(self) -> ReportOrchestrator:
        """Get report orchestrator with dependency injection."""
        if 'report_service' not in self._services:
            self._services['report_service'] = ReportOrchestrator(
                product_repo=self._repository_container.product_repo,
                document_repo=self._repository_container.document_repo,
                warehouse_repo=self._repository_container.warehouse_repo,
                inventory_repo=self._repository_container.inventory_repo,
                customer_repo=self._repository_container.customer_repo,
            )
        return self._services['report_service']

    def get_customer_service(self) -> CustomerService:
        """Get customer service with dependency injection."""
        if 'customer_service' not in self._services:
            self._services['customer_service'] = CustomerService(
                customer_repo=self._repository_container.customer_repo,
            )
        return self._services['customer_service']

    def get_user_service(self) -> UserService:
        """Get user service with dependency injection."""
        if 'user_service' not in self._services:
            self._services['user_service'] = UserService(
                user_repo=self._repository_container.user_repo,
            )
        return self._services['user_service']

    def get_warehouse_operations_service(self) -> WarehouseOperationsService:
        """Get warehouse operations service with dependency injection."""
        if 'warehouse_operations_service' not in self._services:
            self._services['warehouse_operations_service'] = WarehouseOperationsService(
                warehouse_repo=self._repository_container.warehouse_repo,
                product_repo=self._repository_container.product_repo,
                inventory_repo=self._repository_container.inventory_repo,
                document_repo=self._repository_container.document_repo,
            )
        return self._services['warehouse_operations_service']
