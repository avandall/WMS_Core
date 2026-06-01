"""Transaction support for SQLAlchemy repository operations."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from app.shared.core.logging import get_logger

logger = get_logger(__name__)


@contextmanager
def transaction_scope(session: Session) -> Generator[Session, None, None]:
    try:
        logger.debug("Transaction started")
        yield session
        session.commit()
        logger.debug("Transaction committed successfully")
    except Exception as e:
        logger.error(f"Transaction failed, rolling back: {type(e).__name__}: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()


class TransactionalRepository:
    """Base repository with optional transaction management following LSP."""

    def __init__(self, session: Session, auto_commit: bool = False):
        self.session = session
        self._auto_commit = auto_commit

    def set_auto_commit(self, enabled: bool) -> None:
        """Enable or disable auto-commit for this repository."""
        self._auto_commit = enabled
        logger.debug(f"Auto-commit set to: {enabled}")

    def _commit_if_auto(self) -> None:
        """Commit only if auto-commit is enabled - follows LSP by not forcing behavior."""
        if self._auto_commit:
            self.session.commit()
            logger.debug("Auto-committed transaction")
