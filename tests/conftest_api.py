"""
API test configuration with SQLite database.
"""

import pytest
import os
from starlette.testclient import TestClient

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


@pytest.fixture(scope="function")
def api_client():
    """Create a test FastAPI client with SQLite database."""
    # Set testing environment before any imports
    os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///test_api.db")
    os.environ["TESTING"] = "true"
    
    # Import and create app after setting environment
    from app.api import create_app
    from app.core.database import Base
    from sqlalchemy import create_engine
    from app.infrastructure.persistence.models import import_all_models
    
    # Create test database
    test_db_url = os.getenv("TEST_DATABASE_URL", "sqlite:///test_api.db")
    engine = create_engine(test_db_url, echo=False)
    import_all_models()
    Base.metadata.create_all(bind=engine)
    
    # Create app
    app = create_app()
    
    yield TestClient(app)
    
    # Cleanup
    os.remove("test_api.db")


@pytest.fixture(scope="function")
def api_client_with_data(api_client):
    """Create a test client with sample data."""
    # Add sample data through API endpoints
    response = api_client.post("/api/products", json={
        "product_id": 1,
        "name": "Test Product",
        "description": "Test Description",
        "price": 10.0
    })
    assert response.status_code == 201
    
    response = api_client.post("/api/warehouses", json={
        "warehouse_id": 1,
        "location": "Test Warehouse"
    })
    assert response.status_code == 201
    
    return api_client
