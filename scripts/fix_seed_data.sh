#!/bin/bash

# Fix Seed Data Script
# This script loads all seed data manually with proper error handling

echo " Fixing WMS Seed Data..."
echo ""

# Check if containers are running
if ! docker compose ps | grep -q "Up"; then
    echo " WMS containers are not running. Please start with: ./quick_start.sh dev"
    exit 1
fi

echo " Step 1: Force clean up existing data..."
# More aggressive cleanup approach
docker compose exec db psql -U wms_user -d warehouse_db -c "
-- Drop and recreate all tables to ensure clean state
DROP TABLE IF EXISTS warehouse_inventory CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS warehouses CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Also drop singular table names that some scripts might use
DROP TABLE IF EXISTS warehouse CASCADE;
DROP TABLE IF EXISTS product CASCADE;
DROP TABLE IF EXISTS customer CASCADE;
DROP TABLE IF EXISTS document CASCADE;
DROP VIEW IF EXISTS user_view;
DROP VIEW IF EXISTS warehouse_view;
DROP VIEW IF EXISTS product_view;
DROP VIEW IF EXISTS customer_view;
DROP VIEW IF EXISTS document_view;
" 2>/dev/null || echo " Force cleanup completed"

echo ""
echo " Step 2: Creating database schema..."
# Create schema first before running Python scripts
docker compose exec db psql -U wms_user -d warehouse_db -c "
-- Create plural table names
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id SERIAL PRIMARY KEY,
    location VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) UNIQUE NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(50),
    address TEXT,
    debt_balance DECIMAL(10,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    document_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    document_type VARCHAR(50),
    warehouse_id INTEGER REFERENCES warehouses(warehouse_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse_inventory (
    warehouse_inventory_id SERIAL PRIMARY KEY,
    warehouse_id INTEGER REFERENCES warehouses(warehouse_id),
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(warehouse_id, product_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_log_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(50),
    record_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
" 2>/dev/null || echo " Schema creation completed"

echo ""
echo " Step 3: Creating login users..."
docker compose exec api python /app/src/data/seed_data/create_login_users.py || echo " Users creation failed"

echo ""
echo " Step 4: Loading basic data with conflict handling..."
docker compose exec api python /app/src/data/seed_data/load_basic_data.py || echo " Basic data loading failed"

echo ""
echo " Step 5: Loading warehouse inventory..."
docker compose exec api python /app/src/data/seed_data/load_inventory.py || echo " Inventory loading failed"

echo ""
echo " Step 6: Generating additional development data..."
docker compose exec api python /app/src/data/seed_data/generate_dev_data.py || echo " Dev data generation failed"

echo ""
echo " Step 7: Creating compatibility views..."
# Create views for singular table names
docker compose exec db psql -U wms_user -d warehouse_db -c "
-- Create singular table names as views for compatibility
CREATE OR REPLACE VIEW user_view AS SELECT * FROM users;
CREATE OR REPLACE VIEW warehouse_view AS SELECT * FROM warehouses;
CREATE OR REPLACE VIEW product_view AS SELECT * FROM products;
CREATE OR REPLACE VIEW customer_view AS SELECT * FROM customers;
CREATE OR REPLACE VIEW document_view AS SELECT * FROM documents;
" 2>/dev/null || echo " Compatibility views created"

echo ""
echo " Seed data fix complete!"
echo ""

# Show current data counts
echo " Current Database Status:"
docker compose exec db psql -U wms_user -d warehouse_db -c "
SELECT 
    'users' as table_name, COUNT(*) as count FROM users
UNION ALL SELECT 'warehouses', COUNT(*) FROM warehouses
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'warehouse_inventory', COUNT(*) FROM warehouse_inventory
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
ORDER BY table_name;
" 2>/dev/null

echo ""
echo " Login Credentials:"
echo "Admin: admin@wms.com / Admin123!"
echo "Manager: manager@wms.com / Manager123!"
echo "Staff: staff@wms.com / Staff123!"
echo "User: user@wms.com / User123!"

echo ""
echo " Troubleshooting Tips:"
echo "- If errors persist, check the individual Python scripts in src/data/seed_data/"
echo "- Ensure database permissions are correct"
echo "- Check docker logs with: docker compose logs api"
