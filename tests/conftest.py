"""
Pytest configuration and fixtures for WMS tests.
Sets up common fixtures for testing.
"""

import pytest
import os
from typing import Any
import requests

# Lazy load app to avoid DB connection during SQL tests
APP_AVAILABLE = True
app = None

# Enable auth bypass for TestClient-driven tests.
os.environ.setdefault("TESTING", "true")


@pytest.fixture
def token():
    """
    Access token for tests that hit a live API at localhost:8000.
    If the API is not reachable, dependent tests are skipped.
    """
    base_url = os.getenv("TEST_API_BASE_URL", "http://localhost:8000")
    email = "admin@example.com"
    password = "admin123"

    try:
        login_resp = requests.post(
            f"{base_url}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
    except requests.RequestException:
        pytest.skip("Live API is not reachable on localhost:8000")

    if login_resp.status_code != 200:
        register_resp = requests.post(
            f"{base_url}/auth/register",
            json={
                "email": email,
                "password": password,
                "role": "admin",
                "full_name": "Test Admin",
            },
            timeout=10,
        )
        if register_resp.status_code not in {200, 201, 400, 409}:
            pytest.skip("Unable to create/login test admin user")

        login_resp = requests.post(
            f"{base_url}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )

    if login_resp.status_code != 200:
        pytest.skip(f"Unable to authenticate test admin user: {login_resp.status_code}")

    return login_resp.json()["access_token"]


def lazy_load_app():
    """Lazy load app imports to avoid DB connection during SQL tests."""
    global app, APP_AVAILABLE
    if app is not None:
        return
    try:
        from app.api import app as _app

        app = _app
    except (ImportError, ModuleNotFoundError):
        APP_AVAILABLE = False
        raise


# SQL test fixtures for unit/repo tests
@pytest.fixture(scope="function")
def test_engine():
    """Create a fresh test database engine for each test."""
    from sqlalchemy import create_engine
    from app.core.database import Base

    # Use environment variable for test database or default to in-memory SQLite
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        future=True,
    )

    # Import all models before creating tables
    from app.infrastructure.persistence.models import import_all_models
    import_all_models()
    
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)
    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Drop all tables after test
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create a fresh database session for each test."""
    from sqlalchemy.orm import sessionmaker

    TestSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, future=True
    )
    session = TestSessionLocal()

    yield session

    session.close()


@pytest.fixture(autouse=True, scope="function")
def reset_db_for_integration_tests(request):
    """
    Auto-cleanup fixture for integration tests.
    Drops and recreates all tables once per test function.
    Seeds database with initial warehouses for tests that expect them.
    """
    fspath = str(request.fspath)

    # Keep state for sequential end-to-end integration script.
    if "tests/integration/test_integration.py" in fspath:
        yield
        return

    # Apply to integration tests and explicit DB isolation tests only.
    if "integration" not in fspath and "test_db_isolation" not in fspath:
        yield
        return

    # Import only when needed for integration tests
    from app.core.settings import settings
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.infrastructure.persistence.models import WarehouseModel, ProductModel
    from app.infrastructure.persistence.models import import_all_models

    # Create engine for integration test cleanup
    # Use environment variable or default to SQLite for testing to avoid PostgreSQL dependency
    test_db_url = os.getenv("TEST_DATABASE_URL", "sqlite:///test.db")
    engine = create_engine(test_db_url)

    # Import all models to ensure proper table creation
    import_all_models()
    
    # Drop and recreate all tables before each test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed database with initial data for tests
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        # Create warehouses for tests that expect them
        warehouses = [
            WarehouseModel(warehouse_id=1, location="Test Warehouse 1"),
            WarehouseModel(warehouse_id=2, location="Test Warehouse 2"),
            WarehouseModel(warehouse_id=3, location="Test Warehouse 3"),
        ]
        for wh in warehouses:
            db.add(wh)

        # Create products for tests that expect them
        products = [
            ProductModel(
                product_id=101, name="Laptop", price=1500.00, description="Test laptop"
            ),
            ProductModel(
                product_id=102, name="Mouse", price=99.99, description="Test mouse"
            ),
            ProductModel(
                product_id=103,
                name="Keyboard",
                price=150.00,
                description="Test keyboard",
            ),
        ]
        for prod in products:
            db.add(prod)

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    yield

    # Cleanup
    engine.dispose()


@pytest.fixture
def client() -> Any:
    """FastAPI test client for integration tests."""
    from starlette.testclient import TestClient
    
    # Set testing mode to use environment variable or default to SQLite
    import os
    os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///test.db")
    os.environ["TESTING"] = "true"

    lazy_load_app()
    if not APP_AVAILABLE or app is None:
        pytest.skip("App dependencies not available")

    return TestClient(app)


@pytest.fixture
def sample_product():
    """Fixture for a sample product."""
    from app.domain.entities.product import Product

    return Product(
        product_id=1,
        name="Test Laptop",
        description="High-performance laptop",
        price=999.99,
    )


@pytest.fixture
def sample_warehouse():
    """Fixture for a sample warehouse."""
    from app.domain.entities.inventory import InventoryItem
    from app.domain.entities.warehouse import Warehouse

    return Warehouse(
        warehouse_id=1,
        location="Main Warehouse",
        inventory=[
            InventoryItem(product_id=1, quantity=10),
            InventoryItem(product_id=2, quantity=5),
        ],
    )


@pytest.fixture
def sample_document():
    """Fixture for a sample inventory document."""
    from app.domain.entities.document import Document, DocumentProduct, DocumentType

    items = [
        DocumentProduct(product_id=1, quantity=10, unit_price=99.99),
        DocumentProduct(product_id=2, quantity=5, unit_price=49.99),
    ]
    return Document(
        document_id=1,
        doc_type=DocumentType.IMPORT,
        to_warehouse_id=1,
        items=items,
        created_by="Test User",
    )
