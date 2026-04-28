#!/usr/bin/env python3
"""
Load basic seed data into the database.
This script loads only the essential data that works with the current schema.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

try:
    from app.shared.core.settings import settings
except ImportError:
    print("Error: Could not import WMS settings.")
    sys.exit(1)

def load_basic_data():
    """Load basic seed data."""
    try:
        # Connect to database
        engine = create_engine(settings.database_url)
        
        with engine.connect() as conn:
            # Insert Warehouses
            print("📦 Loading warehouses...")
            conn.execute(text("""
                INSERT INTO warehouses (location) VALUES 
                ('123 Lê Lợi, Quận 1, HCM'),
                ('456 Võ Văn Ngân, Thủ Đức, HCM'),
                ('789 Tân Kỷ Tân, Bình Tân, HCM'),
                ('321 Quốc Lộ 1A, Hóc Môn, HCM'),
                ('656 Huỳnh Tấn Phát, Bình Chánh, HCM')
            """))
            conn.commit()
            
            # Insert Products
            print("📦 Loading products...")
            conn.execute(text("""
                INSERT INTO products (name, sku, price, description) VALUES 
                ('Pallet Gỗ tiêu chuẩn', 'PL-001', 150000, 'Pallet gỗ thông dụng 1200x1000mm'),
                ('Xe nâng điện', 'XL-002', 45000000, 'Xe nâng điện 1.5 tấn, loại mới'),
                ('Thùng carton 3 lớp', 'TC-003', 8500, 'Thùng carton 50x40x30cm'),
                ('Màng bọc PE', 'MB-004', 12000, 'Màng bọc PE dày 0.03mm, cuộn 1kg'),
                ('Kệ sắt V lỗ', 'KS-005', 750000, 'Kệ sắt V lỗ 1500x500x2000mm'),
                ('Xe đẩy hàng', 'XD-006', 2800000, 'Xe đẩy hàng inox 200kg'),
                ('Bao tải PP', 'BT-007', 3500, 'Bao tải PP 50kg màu trắng'),
                ('Dây đeo hàng', 'DD-008', 15000, 'Dây đeo hàng polyester 5m'),
                ('Thùng nhựa', 'TN-009', 45000, 'Thùng nhựa 60L có nắp'),
                ('Kẹp chì', 'KC-010', 2500, 'Kẹp chì nhôm 10mm'),
                ('Máy in mã vạch', 'MI-011', 8500000, 'Máy in mã vạch Zebra ZD220'),
                ('Băng keo', 'BK-012', 18000, 'Băng keo trong 100y'),
                ('Giấy in hóa đơn', 'GH-013', 12000, 'Giấy in hóa đơn 2 liên'),
                ('Bút laser', 'BL-014', 95000, 'Bút laser đo khoảng cách 50m'),
                ('Đồng hồ treo tường', 'DH-015', 150000, 'Đồng hồ treo tường 30cm'),
                ('Bàn làm việc', 'BL-016', 3200000, 'Bàn làm việc sắt 120x60cm'),
                ('Ghế văn phòng', 'GV-017', 1850000, 'Ghế văn phòng lưới lưng cao'),
                ('Laptop Dell', 'LD-018', 18500000, 'Laptop Dell Core i5 8GB RAM'),
                ('Máy tính để bàn', 'MT-019', 12500000, 'Máy tính để bàn Core i3 8GB RAM'),
                ('Màn hình LCD', 'MH-020', 4500000, 'Màn hình LCD 24 inch Full HD'),
                ('Bàn phím cơ', 'BP-021', 950000, 'Bàn phím cơ RGB'),
                ('Chuột không dây', 'CD-022', 450000, 'Chuột không dây Logitech')
            """))
            conn.commit()
            
            # Insert Users
            print("?? Loading users...")
            conn.execute(text("""
                INSERT INTO users (username, email, password_hash, role, is_active, created_at) VALUES 
                ('admin', 'admin@wms.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvO6', 'admin', true, NOW()),
                ('manager', 'manager@wms.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvO6', 'manager', true, NOW()),
                ('staff', 'staff@wms.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvO6', 'staff', true, NOW()),
                ('user', 'user@wms.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvO6', 'user', true, NOW())
            """))
            conn.commit()
            
            # Insert Customers
            print("👥 Loading customers...")
            conn.execute(text("""
                INSERT INTO customers (name, email, phone, address, debt_balance, created_at) VALUES 
                ('Công ty ABC', 'contact@abc.com', '0901234567', '123 Nguyễn Trãi, Q1, HCM', 0.0, NOW()),
                ('Công ty XYZ', 'info@xyz.vn', '0912345678', '456 Trần Hưng Đạo, Q5, HCM', 0.0, NOW()),
                ('Siêu thị Co.opmart', 'donhang@coopmart.vn', '0923456789', '789 Cộng Hòa, Tân Bình, HCM', 0.0, NOW()),
                ('Chuỗi cửa hàng Tiki', 'business@tiki.vn', '0934567890', '321 Võ Văn Kiệt, Q1, HCM', 0.0, NOW()),
                ('Cửa hàng tiện lợi 24/7', 'order@247store.vn', '0945678901', '656 Phạm Văn Đồng, Phú Nhuận, HCM', 0.0, NOW())
            """))
            conn.commit()
            
            # Insert Warehouse Inventory
            print("📦 Loading warehouse inventory...")
            conn.execute(text("""
                INSERT INTO warehouse_inventory (warehouse_id, product_id, quantity) VALUES 
                (1, 1, 100),  -- Pallet Gỗ in Kho Q1
                (1, 2, 5),    -- Xe nâng in Kho Q1
                (1, 3, 500),  -- Thùng carton in Kho Q1
                (1, 4, 200),  -- Màng bọc in Kho Q1
                (2, 5, 50),   -- Kệ sắt in Kho Thủ Đức
                (2, 6, 20),   -- Xe đẩy in Kho Thủ Đức
                (3, 7, 1000), -- Bao tải in Kho Bình Tân
                (3, 8, 300),  -- Dây đeo in Kho Hóc Môn
                (4, 9, 150),  -- Thùng nhựa in Kho Bình Chánh
                (4, 10, 100), -- Kẹp chì in Kho Q1
                (5, 11, 3),   -- Máy in mã vạch in Kho Thủ Đức
                (5, 12, 800), -- Băng keo in Kho Bình Tân
                (1, 13, 200), -- Giấy in hóa đơn in Kho Hóc Môn
                (1, 14, 50),  -- Bút laser in Kho Bình Chánh
                (2, 15, 25),  -- Đồng hồ in Kho Q1
                (2, 16, 15),  -- Bàn làm việc in Kho Thủ Đức
                (3, 17, 30),  -- Ghế văn phòng in Kho Bình Tân
                (3, 18, 10),  -- Laptop in Kho Hóc Môn
                (4, 19, 20),  -- Máy tính để bàn in Kho Bình Chánh
                (4, 20, 35),  -- Màn hình in Kho Q1
                (5, 21, 60),  -- Bàn phím cơ in Kho Thủ Đức
                (5, 22, 100)  -- Chuột không dây in Kho Bình Tân
            """))
            conn.commit()
        
        print("✅ Basic seed data loaded successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error loading basic data: {e}")
        return False

if __name__ == '__main__':
    load_basic_data()
