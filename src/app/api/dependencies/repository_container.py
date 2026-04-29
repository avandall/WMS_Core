"""Container for all repository instances following DIP principle with lazy loading."""

from sqlalchemy.orm import Session

from app.shared.application.unit_of_work.unit_of_work import RepositoryContainer


class RepositoryContainerImpl(RepositoryContainer):
    """Implementation of repository container with lazy loading."""

    def __init__(self, session: Session):
        self._session = session
        self._repos = {}

    def __getattr__(self, name: str):
        """Dynamic lazy loading of repositories."""
        if name not in self._repos:
            repo = self._create_repository(name)
            if repo is None:
                raise AttributeError(f"Repository '{name}' not found")
            self._repos[name] = repo
        return self._repos[name]

    def _create_repository(self, name: str):
        """Create repository instance on-demand with local imports."""
        if name == "product_repo":
            from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
            return ProductRepo(self._session)
        elif name == "inventory_repo":
            from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
            return InventoryRepo(self._session)
        elif name == "warehouse_repo":
            from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo
            return WarehouseRepo(self._session)
        elif name == "document_repo":
            from app.modules.documents.infrastructure.repositories.document_repo import DocumentRepo
            return DocumentRepo(self._session)
        elif name == "customer_repo":
            from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
            return CustomerRepo(self._session)
        elif name == "position_repo":
            from app.modules.positions.infrastructure.repositories.position_repo import PositionRepo
            return PositionRepo(self._session)
        elif name == "audit_event_repo":
            from app.modules.audit.infrastructure.repositories.audit_event_repo import AuditEventRepo
            return AuditEventRepo(self._session)
        elif name == "user_repo":
            from app.modules.users.infrastructure.repositories.user_repo import UserRepo
            return UserRepo(self._session)
        return None
