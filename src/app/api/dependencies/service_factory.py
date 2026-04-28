"""Service factory implementing DIP principle."""

from sqlalchemy.orm import Session

from app.modules.products.application.services.product_service import ProductService
from app.application.unit_of_work.unit_of_work import UnitOfWork
from app.infrastructure.persistence.repositories.repository_container import RepositoryContainerImpl


class ServiceFactory:
    """Factory for creating services following DIP principle."""

    def __init__(self, session: Session):
        self.session = session
        self._repository_container = RepositoryContainerImpl(session)
        self._services = {}

    def get_product_service(self) -> ProductService:
        """Get product service with dependency injection."""
        if 'product_service' not in self._services:
            self._services['product_service'] = ProductService(
                product_repo=self._repository_container.product_repo,
                inventory_repo=self._repository_container.inventory_repo,
            )
        return self._services['product_service']

    def get_unit_of_work(self) -> UnitOfWork:
        """Get unit of work instance."""
        return UnitOfWork(self.session, self._repository_container)
