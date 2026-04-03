"""Transaction support for SQLAlchemy repository operations."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from app.core.logging import get_logger

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
    def __init__(self, session: Session):
        self.session = session
        self._auto_commit = True

    def set_auto_commit(self, enabled: bool) -> None:
        self._auto_commit = enabled
        logger.debug(f"Auto-commit set to: {enabled}")

    def _commit_if_auto(self) -> None:
        if self._auto_commit:
            self.session.commit()
            logger.debug("Auto-committed transaction")
