"""
SQLite-based pytest configuration for testing without PostgreSQL dependency.
"""

import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.infrastructure.persistence.models import import_all_models, Base


@pytest.fixture(scope="session")
def sqlite_test_db():
    """Create a temporary SQLite database for testing."""
    # Create temporary file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    # Create engine using environment variable or default
    test_db_url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{db_path}")
    engine = create_engine(test_db_url, echo=False)
    
    # Create all tables
    import_all_models()
    Base.metadata.create_all(bind=engine)
    
    yield engine, db_path
    
    # Cleanup
    os.unlink(db_path)


@pytest.fixture(scope="function")
def sqlite_session(sqlite_test_db):
    """Create a SQLAlchemy session for testing."""
    engine, _ = sqlite_test_db
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def sqlite_test_engine(sqlite_test_db):
    """Get the test engine."""
    engine, _ = sqlite_test_db
    return engine


# Override the existing fixtures for SQLite testing
@pytest.fixture(scope="function")
def test_session():
    """Override test_session to use SQLite."""
    return sqlite_session()


@pytest.fixture(scope="function") 
def test_engine():
    """Override test_engine to use SQLite."""
    return sqlite_test_engine()


# Repository fixtures
@pytest.fixture
def product_repo_sql(sqlite_session):
    """Product repository with SQLite session."""
    from app.infrastructure.persistence.repositories.product_repo import ProductRepo
    return ProductRepo(sqlite_session)


@pytest.fixture
def warehouse_repo_sql(sqlite_session):
    """Warehouse repository with SQLite session."""
    from app.infrastructure.persistence.repositories.warehouse_repo import WarehouseRepo
    return WarehouseRepo(sqlite_session)


@pytest.fixture
def inventory_repo_sql(sqlite_session):
    """Inventory repository with SQLite session."""
    from app.infrastructure.persistence.repositories.inventory_repo import InventoryRepo
    return InventoryRepo(sqlite_session)


@pytest.fixture
def document_repo_sql(sqlite_session):
    """Document repository with SQLite session."""
    from app.infrastructure.persistence.repositories.document_repo import DocumentRepo
    return DocumentRepo(sqlite_session)


@pytest.fixture
def position_repo_sql(sqlite_session):
    """Position repository with SQLite session."""
    from app.infrastructure.persistence.repositories.position_repo import PositionRepo
    return PositionRepo(sqlite_session)


@pytest.fixture
def audit_event_repo_sql(sqlite_session):
    """Audit event repository with SQLite session."""
    from app.infrastructure.persistence.repositories.audit_event_repo import AuditEventRepo
    return AuditEventRepo(sqlite_session)
