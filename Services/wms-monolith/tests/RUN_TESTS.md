# How to Run WMS Tests

## Prerequisites

Make sure you have the required dependencies installed:

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock pytest-asyncio

# Install project dependencies
pip install -r requirements.txt
```

## Running Tests

### 1. Run All Tests

```bash
# Run all tests in the test suite
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html --cov-report=term
```

### 2. Run Specific Test Categories

#### Unit Tests
```bash
# Run all unit tests
pytest tests/unit/

# Run specific unit test file
pytest tests/unit/domain/test_product_entity.py

# Run specific test class
pytest tests/unit/services/test_product_service.py::TestProductService

# Run specific test method
pytest tests/unit/services/test_product_service.py::TestProductService::test_create_product
```

#### Integration Tests
```bash
# Run all integration tests
pytest tests/integration/

# Run specific integration test
pytest tests/integration/test_product_workflows.py::TestProductWorkflows::test_complete_product_crud_workflow
```

#### Functional Tests
```bash
# Run functional tests
pytest tests/functional/

# Run warehouse operations tests
pytest tests/functional/test_warehouse_operations.py -v
```

#### End-to-End Tests
```bash
# Run E2E tests
pytest tests/e2e/

# Run specific user journey
pytest tests/e2e/test_user_journeys.py::TestUserJourneysE2E::test_admin_complete_system_setup_journey
```

#### Performance Tests
```bash
# Run performance tests
pytest tests/performance/

# Run with performance output
pytest tests/performance/test_critical_operations.py -v -s
```

#### Security Tests
```bash
# Run security tests
pytest tests/security/

# Run specific security test
pytest tests/security/test_authentication_authorization.py::TestAuthenticationSecurity::test_valid_user_authentication
```

### 3. Run Tests with Different Options

#### With Coverage Report
```bash
# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html

# Generate terminal coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Coverage for specific module
pytest tests/unit/domain/ --cov=src/app/domain
```

#### With Markers
```bash
# Run only fast tests
pytest tests/ -m "not slow"

# Run only specific markers (if defined)
pytest tests/ -m "unit"
pytest tests/ -m "integration"
pytest tests/ -m "performance"
```

#### Parallel Execution
```bash
# Run tests in parallel (install pytest-xdist first)
pip install pytest-xdist

# Run with 4 workers
pytest tests/ -n 4

# Auto-detect CPU cores
pytest tests/ -n auto
```

#### Debug Mode
```bash
# Stop on first failure
pytest tests/ -x

# Show local variables on failure
pytest tests/ -l

# Enter debugger on failure
pytest tests/ --pdb

# Run with maximum verbosity
pytest tests/ -vv -s
```

### 4. Specific Test Examples

#### Run All Product-Related Tests
```bash
# Product entity tests
pytest tests/unit/domain/test_product_entity.py

# Product service tests
pytest tests/unit/services/test_product_service.py

# Product repository tests
pytest tests/unit/repositories/test_product_repo.py

# Product API tests
pytest tests/unit/api/test_products_endpoint.py

# Product workflow tests
pytest tests/integration/test_product_workflows.py
```

#### Run All Warehouse-Related Tests
```bash
# Warehouse entity tests
pytest tests/unit/domain/test_warehouse_entity.py

# Warehouse service tests
pytest tests/unit/services/test_warehouse_service.py

# Warehouse repository tests
pytest tests/unit/repositories/test_warehouse_repo.py

# Warehouse API tests
pytest tests/unit/api/test_warehouses_endpoint.py

# Warehouse operations tests
pytest tests/functional/test_warehouse_operations.py

# Warehouse workflow tests
pytest tests/integration/test_warehouse_workflows.py
```

### 5. Test Configuration

#### pytest.ini Configuration
Create a `pytest.ini` file in your project root:

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --strict-config
    --verbose
    --tb=short
    --cov=src
    --cov-report=html
    --cov-report=term-missing
markers =
    unit: Unit tests
    integration: Integration tests
    functional: Functional tests
    e2e: End-to-end tests
    performance: Performance tests
    security: Security tests
    slow: Slow running tests
```

#### Environment Variables
```bash
# Set test environment
export TESTING=true
export TEST_DATABASE_URL=sqlite:///test.db

# Run with environment
pytest tests/
```

### 6. Continuous Integration

#### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    - name: Run tests
      run: pytest tests/ --cov=src --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

### 7. Troubleshooting

#### Common Issues

1. **Import Errors**
   ```bash
   # Make sure you're in the project root
   cd /home/avandall1999/Projects/WMS
   
   # Install the project in development mode
   pip install -e .
   ```

2. **Module Not Found**
   ```bash
   # Add src to Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
   
   # Or run with Python path
   PYTHONPATH=src pytest tests/
   ```

3. **Database Connection Issues**
   ```bash
   # Use test database
   export DATABASE_URL=sqlite:///test.db
   
   # Or run with test configuration
   pytest tests/ --env=test
   ```

4. **Slow Tests**
   ```bash
   # Run only fast tests first
   pytest tests/ -m "not slow"
   
   # Run performance tests separately
   pytest tests/performance/ -v
   ```

#### Debug Mode
```bash
# Run with maximum debugging info
pytest tests/ -vv -s --tb=long --pdb

# Run specific failing test
pytest tests/unit/services/test_product_service.py::TestProductService::test_create_product -vv -s --pdb
```

### 8. Test Results Interpretation

#### Coverage Report
- **Lines**: Percentage of code lines executed
- **Branches**: Percentage of conditional branches tested
- **Functions**: Percentage of functions called
- **Statements**: Percentage of statements executed

#### Test Output
- **`.`**: Test passed
- **`F`**: Test failed
- **`E`**: Test error
- **`s`**: Test skipped
- **`x`**: Test expected to fail

### 9. Best Practices

1. **Run tests frequently** during development
2. **Write tests before fixing bugs** (TDD approach)
3. **Keep tests isolated** and independent
4. **Use descriptive test names**
5. **Mock external dependencies** properly
6. **Test edge cases and error conditions**
7. **Maintain high coverage** (aim for 95%+)
8. **Run performance tests** regularly
9. **Review security tests** after code changes
10. **Update tests** when requirements change

### 10. Quick Reference Commands

```bash
# Quick test run
pytest tests/ -v

# Full test with coverage
pytest tests/ --cov=src --cov-report=html

# Run only unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/functional/test_warehouse_operations.py -v

# Run with debugging
pytest tests/ -vv -s --pdb

# Run in parallel
pytest tests/ -n auto

# Run performance tests
pytest tests/performance/ -v -s
```

This guide should help you run and manage the comprehensive test suite effectively!
