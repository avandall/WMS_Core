"""
Pytest configuration and fixtures for SQL database tests.
Uses a separate test database (SQLite in-memory or PostgreSQL test DB).
"""

import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import Base from app.core.database (same Base used by models)
from app.core.database import Base

from app.infrastructure.persistence.repositories.product_repo import ProductRepo
from app.infrastructure.persistence.repositories.inventory_repo import InventoryRepo
from app.infrastructure.persistence.repositories.warehouse_repo import WarehouseRepo
from app.infrastructure.persistence.repositories.document_repo import DocumentRepo


# Use environment variable for test database or default to in-memory SQLite
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(scope="function")
def test_engine():
    """Create a fresh test database engine for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        future=True,
    )
    
    # Import all models before creating tables
    from app.infrastructure.persistence.models import import_all_models
    import_all_models()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Drop all tables after test
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create a fresh database session for each test."""
    TestSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, future=True
    )
    session = TestSessionLocal()

    yield session

    # Clean up
    session.rollback()
    session.close()


@pytest.fixture
def product_repo_sql(test_session: Session):
    """Fixture for SQL product repository."""
    return ProductRepo(test_session)


@pytest.fixture
def inventory_repo_sql(test_session: Session):
    """Fixture for SQL inventory repository."""
    return InventoryRepo(test_session)


@pytest.fixture
def warehouse_repo_sql(test_session: Session):
    """Fixture for SQL warehouse repository."""
    return WarehouseRepo(test_session)


@pytest.fixture
def document_repo_sql(test_session: Session):
    """Fixture for SQL document repository."""
    return DocumentRepo(test_session)
