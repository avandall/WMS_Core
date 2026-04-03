# PMKT Warehouse Management System - Tests

This directory contains comprehensive tests for the PMKT Warehouse Management System, organized according to Clean Architecture principles.

## Test Structure

```
tests/
├── requirements-test.txt    # Test dependencies
├── pytest.ini              # Pytest configuration
├── conftest.py             # Shared fixtures and configuration
├── run_tests.py            # Test runner script
├── unit/                   # Unit tests
│   ├── domain/            # Domain entity tests
│   ├── services/          # Service layer tests
│   └── repo/              # Repository tests
├── integration/           # Integration tests
│   └── api/               # API endpoint tests
└── functional/            # End-to-end functional tests
```

## Running Tests

### All Tests
```bash
python run_tests.py
```

### Specific Test Types
```bash
# Unit tests only
python run_tests.py unit

# Integration tests only
python run_tests.py integration

# Functional tests only
python run_tests.py functional
```

### With Options
```bash
# Skip coverage
python run_tests.py --no-coverage

# Verbose output
python run_tests.py -v

# Combine options
python run_tests.py unit -v --no-coverage
```

### Using pytest directly
```bash
# Run all tests with coverage
pytest --cov=PMKT --cov-report=term-missing

# Run specific test file
pytest tests/unit/domain/test_product.py -v

# Run tests with markers
pytest -m "slow"  # Run slow tests
pytest -m "not slow"  # Skip slow tests
```

## Test Categories

### Unit Tests
- **Domain Tests**: Validate entity business rules and invariants
- **Service Tests**: Test business logic in isolation using mocks
- **Repository Tests**: Test data access layer with in-memory implementations

### Integration Tests
- **API Tests**: Test FastAPI endpoints with real database connections
- **Repository Integration**: Test actual database operations

### Functional Tests
- **End-to-End**: Complete warehouse management workflows
- **User Scenarios**: Real-world usage patterns

## Test Fixtures

Shared fixtures are defined in `conftest.py`:
- `sample_product`: Sample Product entity
- `sample_warehouse`: Sample Warehouse entity
- `sample_document`: Sample InventoryDocument entity
- `mock_product_repo`: Mock ProductRepository
- `mock_warehouse_repo`: Mock WarehouseRepository
- `mock_document_repo`: Mock DocumentRepository
- `product_service`: ProductService instance with mocks
- `inventory_service`: InventoryService instance with mocks

## Coverage Requirements

- Minimum coverage: 80%
- Domain layer: 100% coverage required
- Service layer: 90% coverage required
- Repository layer: 85% coverage required
- API layer: 80% coverage required

## Writing Tests

### Unit Test Example
```python
import pytest
from PMKT.domain.product import Product

def test_product_creation():
    product = Product(
        id="PROD-001",
        name="Test Product",
        description="A test product",
        price=29.99,
        category="Test"
    )

    assert product.id == "PROD-001"
    assert product.name == "Test Product"
    assert product.price == 29.99
```

### Service Test Example
```python
import pytest
from PMKT.services.product_service import ProductService

def test_create_product(product_service, sample_product):
    result = product_service.create_product(sample_product)

    assert result.id == sample_product.id
    assert result.name == sample_product.name
```

### Integration Test Example
```python
import pytest
from fastapi.testclient import TestClient
from PMKT.api.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_get_products(client):
    response = client.get("/api/products")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

## Mocking Strategy

- Use `unittest.mock` for service layer isolation
- Mock external dependencies (database, APIs, file systems)
- Use `faker` for realistic test data generation
- Use `freezegun` for time-sensitive tests

## Continuous Integration

Tests are configured to run in CI/CD pipelines with:
- Coverage reporting to external services
- JUnit XML output for test results
- HTML coverage reports for review

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Descriptive Names**: Test names should describe what they test
3. **Arrange-Act-Assert**: Follow AAA pattern in test structure
4. **Mock External Dependencies**: Don't test external systems
5. **Test Edge Cases**: Include boundary conditions and error scenarios
6. **Keep Tests Fast**: Unit tests should run in milliseconds
7. **Use Fixtures**: Reuse common test setup with pytest fixtures

## Dependencies

Test dependencies are listed in `requirements-test.txt`:
- pytest: Testing framework
- pytest-cov: Coverage reporting
- pytest-asyncio: Async test support
- faker: Fake data generation
- freezegun: Time mocking
- httpx: HTTP client for API tests