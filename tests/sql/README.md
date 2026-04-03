"""
README for SQL Integration Tests

These tests validate SQL database operations using SQLAlchemy ORM with an in-memory SQLite database.

## Test Files:
- `conftest.py` - Fixtures for SQL testing with isolated database
- `test_sql_warehouse_repo.py` - Warehouse repository SQL tests (19 tests)
- `test_sql_product_repo.py` - Product repository SQL tests (16 tests)
- `test_sql_inventory_repo.py` - Inventory repository SQL tests (18 tests)
- `test_sql_document_repo.py` - Document repository SQL tests (17 tests)
- `test_warehouse_transfer_integration.py` - Transfer inventory integration tests (11 tests)

## Running SQL Tests:

### Run all SQL tests:
```bash
python -m pytest tests/sql/ -v
```

### Run with coverage disabled (faster):
```bash
python -m pytest tests/sql/ -v --no-cov
```

### Run specific test file:
```bash
python -m pytest tests/sql/test_sql_warehouse_repo.py -v
python -m pytest tests/sql/test_sql_product_repo.py -v
python -m pytest tests/sql/test_sql_inventory_repo.py -v
python -m pytest tests/sql/test_sql_document_repo.py -v
python -m pytest tests/sql/test_warehouse_transfer_integration.py -v
```

### Run specific test:
```bash
python -m pytest tests/sql/test_sql_warehouse_repo.py::TestWarehouseRepoSQL::test_delete_warehouse_with_inventory_cascades -v
```

### Run by marker:
```bash
python -m pytest -m sql -v
```

## What These Tests Cover:

### Warehouse Repository Tests:
- CRUD operations (create, read, update, delete)
- Get all warehouses
- CASCADE DELETE behavior (deleting warehouse deletes inventory)
- Add/remove products to/from warehouse
- Quantity accumulation
- Insufficient stock errors
- Empty warehouse handling
- Foreign key constraints

### Product Repository Tests:
- CRUD operations
- Get all products
- Price retrieval
- Product deletion with inventory cleanup
- Foreign key constraint protection
- Price precision
- NULL description handling

### Inventory Repository Tests:
- Save and update inventory
- Add/remove quantity operations
- Get all inventory
- Delete with zero quantity validation
- Negative quantity protection
- Insufficient stock protection
- Session persistence

### Document Repository Tests:
- CRUD operations for documents
- Document status updates
- CASCADE DELETE to document items
- Import/Export/Transfer document types
- Multiple products per document
- Metadata fields (approved_by, timestamps, notes)
- Foreign key constraints

### Transfer Integration Tests:
- Transfer all inventory between warehouses
- Empty warehouse transfers
- Quantity accumulation
- Deletion protection (can't delete warehouse with inventory)
- Complete workflow: transfer -> delete
- Multiple products transfer
- Same warehouse error handling

## Key Features Tested:

1. **CASCADE DELETE**: Deleting warehouse automatically deletes its inventory
2. **Foreign Key Constraints**: Proper validation of warehouse/product relationships
3. **Unique Constraints**: Warehouse-Product pair uniqueness
4. **Transaction Integrity**: All operations use proper commits/rollbacks
5. **Error Handling**: All business exceptions properly raised
6. **Data Persistence**: Cross-session data verification

## Notes:
- Uses SQLite in-memory database for fast isolated tests
- Each test gets fresh database instance
- No dependencies on external PostgreSQL during test execution
- Tests validate the new `transfer_all_inventory` feature
- Tests validate warehouse deletion protection
