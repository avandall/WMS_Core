"""
Pytest configuration and fixtures for WMS tests.
Sets up common fixtures for testing.
"""

import sys
import os
from pathlib import Path

# Add src to Python path for all tests
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
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
        APP_AVAILABLE = True # Nhớ gán lại True nếu thành công
    except (ImportError, ModuleNotFoundError) as e:
        print(f"\n[CRITICAL] Lazy load failed: {e}") # In lỗi thật ra đây
        APP_AVAILABLE = False
        raise


# SQL test fixtures for unit/repo tests
@pytest.fixture(scope="function")
def test_engine():
    """Create a fresh test database engine for each test."""
    from sqlalchemy import create_engine
    from app.shared.core.database import Base

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
    from app.shared.core.settings import settings
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.shared.core.database import Base
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
    from app.modules.products.domain.entities.product import Product

    return Product(
        product_id=1,
        name="Test Laptop",
        description="High-performance laptop",
        price=999.99,
    )


@pytest.fixture
def sample_warehouse():
    """Fixture for a sample warehouse."""
    from app.modules.inventory.domain.entities.inventory import InventoryItem
    from app.modules.warehouses.domain.entities.warehouse import Warehouse

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
    from app.modules.documents.domain.entities.document import Document, DocumentProduct, DocumentType

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


# ============================================================================
# SOLID PATTERN FIXTURES
# ============================================================================

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.application.commands.product_commands import CreateProductCommand, UpdateProductCommand, DeleteProductCommand
from app.application.queries.product_queries import GetProductQuery, GetAllProductsQuery
from app.application.validation.product_validators import ProductValidator
from app.application.unit_of_work.unit_of_work import UnitOfWork, RepositoryContainer
from app.modules.products.domain.entities.product import Product
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo
from app.infrastructure.persistence.repositories.repository_container import RepositoryContainerImpl
# Import ProductAuthorizer conditionally to avoid FastAPI dependency issues
try:
    from app.api.authorization.product_authorizers import ProductAuthorizer
except ImportError:
    ProductAuthorizer = None
# Import ServiceFactory conditionally to avoid import issues
try:
    from app.api.dependencies.service_factory import ServiceFactory
except ImportError:
    # Create a mock ServiceFactory for testing if import fails
    class ServiceFactory:
        def __init__(self, session):
            self.session = session
        def get_product_service(self):
            return Mock()
        def get_unit_of_work(self):
            return Mock()


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session for testing."""
    session = Mock(spec=Session)
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


@pytest.fixture
def mock_product_repo():
    """Mock product repository for testing."""
    repo = Mock(spec=IProductRepo)
    repo.save = Mock()
    repo.get = Mock()
    repo.get_all = Mock()
    repo.get_price = Mock()
    repo.delete = Mock()
    return repo


@pytest.fixture
def mock_inventory_repo():
    """Mock inventory repository for testing."""
    repo = Mock(spec=IInventoryRepo)
    repo.save = Mock()
    repo.get = Mock()
    repo.get_all = Mock()
    repo.update_quantity = Mock()
    return repo


@pytest.fixture
def sample_product():
    """Sample product entity for testing."""
    return Product(
        id=1,
        name="Test Product",
        description="Test Description",
        price=99.99,
        sku="TEST-001",
        stock_quantity=100
    )


@pytest.fixture
def create_product_command():
    """CreateProductCommand fixture for testing."""
    return CreateProductCommand(
        product_id=None,
        name="Test Product",
        description="Test Description",
        price=99.99
    )


@pytest.fixture
def update_product_command():
    """UpdateProductCommand fixture for testing."""
    return UpdateProductCommand(
        product_id=1,
        name="Updated Product",
        description="Updated Description",
        price=149.99
    )


@pytest.fixture
def delete_product_command():
    """DeleteProductCommand fixture for testing."""
    return DeleteProductCommand(product_id=1)


@pytest.fixture
def get_product_query():
    """GetProductQuery fixture for testing."""
    return GetProductQuery(product_id=1)


@pytest.fixture
def get_all_products_query():
    """GetAllProductsQuery fixture for testing."""
    return GetAllProductsQuery()


@pytest.fixture
def product_validator():
    """ProductValidator fixture for testing."""
    return ProductValidator()


@pytest.fixture
def repository_container(mock_session, mock_product_repo, mock_inventory_repo):
    """Repository container fixture for Unit of Work testing."""
    container = Mock(spec=RepositoryContainer)
    container.product_repo = mock_product_repo
    container.inventory_repo = mock_inventory_repo
    return container


@pytest.fixture
def unit_of_work(mock_session, repository_container):
    """Unit of Work fixture for testing."""
    return UnitOfWork(mock_session, repository_container)


@pytest.fixture
def product_authorizer():
    """ProductAuthorizer fixture for testing."""
    return ProductAuthorizer()


@pytest.fixture
def service_factory(mock_session, mock_product_repo, mock_inventory_repo):
    """ServiceFactory fixture for testing."""
    factory = Mock(spec=ServiceFactory)
    factory.get_product_service = Mock()
    factory.get_unit_of_work = Mock()
    return factory


@pytest.fixture
def mock_product_service():
    """Mock ProductService for testing."""
    service = Mock()
    service.create_product = Mock()
    service.update_product = Mock()
    service.delete_product = Mock()
    service.get_product = Mock()
    service.get_all_products = Mock()
    return service


@pytest.fixture
def test_products_list():
    """List of test products for testing."""
    return [
        Product(id=1, name="Product 1", description="Description 1", price=10.0, sku="P1", stock_quantity=50),
        Product(id=2, name="Product 2", description="Description 2", price=20.0, sku="P2", stock_quantity=30),
        Product(id=3, name="Product 3", description="Description 3", price=30.0, sku="P3", stock_quantity=20)
    ]


@pytest.fixture
def performance_test_data():
    """Data for performance testing."""
    return {
        'batch_size': 100,
        'iterations': 10,
        'products_count': 1000
    }
