"""Unit of Work pattern for centralized transaction management."""

from typing import Protocol

from sqlalchemy.orm import Session

from app.shared.core.logging import get_logger

logger = get_logger(__name__)


class RepositoryContainer(Protocol):
    """Generic container for repositories - no module-specific imports."""
    
    def __getattr__(self, name: str):
        """Dynamic access to repositories."""
        ...


class UnitOfWork:
    """Unit of Work implementing transaction management following SRP.
    
    Manages transaction lifecycle only. Repository access via .repos property.
    """

    def __init__(self, session: Session, repositories: RepositoryContainer, read_only: bool = False):
        self.session = session
        self._repositories = repositories
        self._committed = False
        self._read_only = read_only
        self._events = []

    @property
    def repos(self) -> RepositoryContainer:
        """Access to repository container."""
        return self._repositories

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        elif not self._committed and not self._read_only:
            self.commit()
        self._close_session()

    def _close_session(self) -> None:
        """Close the session to return connection to pool."""
        try:
            self.session.close()
            logger.debug("Session closed successfully")
        except Exception as e:
            logger.error(f"Session close failed: {type(e).__name__}: {str(e)}")

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

    def add_event(self, event: dict) -> None:
        """Add audit event to be saved on commit."""
        self._events.append(event)
