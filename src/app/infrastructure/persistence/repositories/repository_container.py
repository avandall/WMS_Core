"""Container for all repository instances following DIP principle."""

from sqlalchemy.orm import Session

from app.application.unit_of_work.unit_of_work import RepositoryContainer
from app.infrastructure.persistence.repositories.audit_event_repo import AuditEventRepo
from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
from app.modules.documents.infrastructure.repositories.document_repo import DocumentRepo
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.positions.infrastructure.repositories.position_repo import PositionRepo
from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.modules.warehouses.infrastructure.repositories.warehouse_repo import WarehouseRepo


class RepositoryContainerImpl(RepositoryContainer):
    """Implementation of repository container for dependency injection."""

    def __init__(self, session: Session):
        self.session = session
        self._product_repo = None
        self._inventory_repo = None
        self._warehouse_repo = None
        self._document_repo = None
        self._customer_repo = None
        self._position_repo = None
        self._audit_event_repo = None
        self._user_repo = None

    @property
    def product_repo(self):
        if self._product_repo is None:
            self._product_repo = ProductRepo(self.session)
        return self._product_repo

    @property
    def inventory_repo(self):
        if self._inventory_repo is None:
            self._inventory_repo = InventoryRepo(self.session)
        return self._inventory_repo

    @property
    def warehouse_repo(self):
        if self._warehouse_repo is None:
            self._warehouse_repo = WarehouseRepo(self.session)
        return self._warehouse_repo

    @property
    def document_repo(self):
        if self._document_repo is None:
            self._document_repo = DocumentRepo(self.session)
        return self._document_repo

    @property
    def customer_repo(self):
        if self._customer_repo is None:
            self._customer_repo = CustomerRepo(self.session)
        return self._customer_repo

    @property
    def position_repo(self):
        if self._position_repo is None:
            self._position_repo = PositionRepo(self.session)
        return self._position_repo

    @property
    def audit_event_repo(self):
        if self._audit_event_repo is None:
            self._audit_event_repo = AuditEventRepo(self.session)
        return self._audit_event_repo

    @property
    def user_repo(self):
        if self._user_repo is None:
            self._user_repo = UserRepo(self.session)
        return self._user_repo
