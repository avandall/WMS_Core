"""Unit of Work pattern for centralized transaction management."""

from contextlib import contextmanager
from typing import Generator, Protocol

from sqlalchemy.orm import Session

from app.shared.core.logging import get_logger
from app.shared.domain.audit_event_repo import IAuditEventRepo
from app.modules.customers.domain.interfaces.customer_repo import ICustomerRepo
from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo
from app.modules.positions.domain.interfaces.position_repo import IPositionRepo
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.modules.users.domain.interfaces.user_repo import IUserRepo
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo

logger = get_logger(__name__)


class RepositoryContainer(Protocol):
    """Container for all repositories."""
    
    @property
    def product_repo(self) -> IProductRepo: ...
    @property
    def inventory_repo(self) -> IInventoryRepo: ...
    @property
    def warehouse_repo(self) -> IWarehouseRepo: ...
    @property
    def document_repo(self) -> IDocumentRepo: ...
    @property
    def customer_repo(self) -> ICustomerRepo: ...
    @property
    def position_repo(self) -> IPositionRepo: ...
    @property
    def audit_event_repo(self) -> IAuditEventRepo: ...
    @property
    def user_repo(self) -> IUserRepo: ...


class UnitOfWork:
    """Unit of Work implementing transaction management following SRP."""

    def __init__(self, session: Session, repositories: RepositoryContainer):
        self.session = session
        self.repositories = repositories
        self._committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        elif not self._committed:
            self.commit()

    def commit(self) -> None:
        """Commit the transaction."""
        try:
            self.session.commit()
            self._committed = True
            logger.debug("Transaction committed successfully")
        except Exception as e:
            logger.error(f"Commit failed: {type(e).__name__}: {str(e)}")
            self.rollback()
            raise

    def rollback(self) -> None:
        """Rollback the transaction."""
        try:
            self.session.rollback()
            logger.debug("Transaction rolled back")
        except Exception as e:
            logger.error(f"Rollback failed: {type(e).__name__}: {str(e)}")
            raise

    @property
    def products(self) -> IProductRepo:
        return self.repositories.product_repo

    @property
    def inventory(self) -> IInventoryRepo:
        return self.repositories.inventory_repo

    @property
    def warehouses(self) -> IWarehouseRepo:
        return self.repositories.warehouse_repo

    @property
    def documents(self) -> IDocumentRepo:
        return self.repositories.document_repo

    @property
    def customers(self) -> ICustomerRepo:
        return self.repositories.customer_repo

    @property
    def positions(self) -> IPositionRepo:
        return self.repositories.position_repo

    @property
    def audit_events(self) -> IAuditEventRepo:
        return self.repositories.audit_event_repo

    @property
    def users(self) -> IUserRepo:
        return self.repositories.user_repo


@contextmanager
def unit_of_work(session: Session, repositories: RepositoryContainer) -> Generator[UnitOfWork, None, None]:
    """Context manager for Unit of Work pattern."""
    uow = UnitOfWork(session, repositories)
    try:
        yield uow
    except Exception:
        uow.rollback()
        raise
    finally:
        if not uow._committed:
            uow.commit()
