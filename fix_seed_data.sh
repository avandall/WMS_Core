#!/bin/bash

# Fix Seed Data Script
# This script loads all seed data manually

echo "🔧 Fixing WMS Seed Data..."
echo ""

# Check if containers are running
if ! docker compose ps | grep -q "Up"; then
    echo "❌ WMS containers are not running. Please start with: ./quick_start.sh dev"
    exit 1
fi

echo "📊 Creating login users..."
docker compose exec api python /app/src/app/data/seed_data/create_login_users.py

echo ""
echo "📦 Loading basic data..."
docker compose exec api python /app/src/app/data/seed_data/load_basic_data.py || echo "⚠️  Basic data may already exist"

echo ""
echo "📦 Loading warehouse inventory..."
docker compose exec api python /app/src/app/data/seed_data/load_inventory.py

echo ""
echo "🌱 Generating additional development data..."
docker compose exec api python /app/src/app/data/seed_data/generate_dev_data.py || echo "⚠️  Dev data generation skipped"

echo ""
echo "✅ Seed data fix complete!"
echo ""

# Show current data counts
echo "📊 Current Database Status:"
docker compose exec db psql -U wms_user -d warehouse_db -c "
SELECT 
    'users' as table_name, COUNT(*) as count FROM users
UNION ALL SELECT 'warehouses', COUNT(*) FROM warehouses
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'warehouse_inventory', COUNT(*) FROM warehouse_inventory
ORDER BY table_name;
" 2>/dev/null

echo ""
echo "🔑 Login Credentials:"
python3 show_login_credentials.py
