"""ID generation delegated to the database (PostgreSQL BIGSERIAL / autoincrement).

MIGRATION NOTE (TASK-001):
  The former _ThreadSafeCounter-based in-memory ID generator has been removed.
  Rationale: in-memory counters reset to 1 on container restart, causing
  UniqueConstraintViolationError in multi-replica / rolling-update deployments.

  All tables now rely on the database sequence (autoincrement=True on the
  primary-key column) to assign IDs.  Repositories must:
    1. Omit the primary-key field when inserting a new row (or pass None/0).
    2. After session.flush(), read the generated ID back from the ORM model and
       write it to the domain entity so callers receive the real DB-assigned ID.

  The helper functions below are kept for import-compatibility only.
  When no explicit id_generator is injected (production), services should call
  repository.create() and read back the assigned ID.
  When an explicit callable is injected (tests), that callable is used directly.
"""

from __future__ import annotations

import warnings
from typing import Callable


class IDGenerator:
    """Stub kept for import-compatibility. No longer manages in-memory counters."""

    @staticmethod
    def get_generator(name: str, start_id: int = 1) -> Callable[[], int]:
        """Deprecated: in-memory ID generation removed. Returns a no-op stub."""
        warnings.warn(
            f"IDGenerator.get_generator('{name}') is deprecated and no longer "
            "provides unique IDs. Configure the table's primary key as "
            "autoincrement=True and let the database assign IDs instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Return a callable that always returns 0 (sentinel = "not yet assigned").
        # Repositories must detect 0/None and omit the PK on INSERT.
        return lambda: 0

    @staticmethod
    def reset_generator(name: str, start_id: int = 1) -> None:
        """No-op stub. Previously reset the in-memory counter."""
        # No-op: counter no longer exists; DB sequence cannot be reset from here.
        return


# ---------------------------------------------------------------------------
# Module-level generator factories — kept for import compatibility.
# In production code these should NOT be called; the DB assigns IDs.
# In unit tests an explicit callable may be injected instead.
# ---------------------------------------------------------------------------

def document_id_generator() -> Callable[[], int]:
    """Deprecated factory. Use DB autoincrement instead."""
    return IDGenerator.get_generator("document", 1)


def warehouse_id_generator() -> Callable[[], int]:
    """Deprecated factory. Use DB autoincrement instead."""
    return IDGenerator.get_generator("warehouse", 1)


def product_id_generator() -> Callable[[], int]:
    """Deprecated factory. Use DB autoincrement instead."""
    return IDGenerator.get_generator("product", 1)
