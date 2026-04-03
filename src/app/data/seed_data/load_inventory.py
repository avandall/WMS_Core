#!/usr/bin/env python3
"""
Load warehouse inventory with correct IDs.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

try:
    from app.core.settings import settings
except ImportError:
    print("Error: Could not import WMS settings.")
    sys.exit(1)

def load_inventory():
    """Load warehouse inventory."""
    try:
        # Connect to database
        engine = create_engine(settings.database_url)
        
        with engine.connect() as conn:
            # Get actual warehouse IDs
            result = conn.execute(text("SELECT warehouse_id FROM warehouses ORDER BY warehouse_id"))
            warehouse_ids = [row[0] for row in result]
            print(f"Found warehouse IDs: {warehouse_ids}")
            
            # Get actual product IDs (first 22 products)
            result = conn.execute(text("SELECT product_id FROM products ORDER BY product_id LIMIT 22"))
            product_ids = [row[0] for row in result]
            print(f"Found product IDs: {product_ids}")
            
            # Insert warehouse inventory with correct IDs
            print("📦 Loading warehouse inventory...")
            inventory_data = [
                (warehouse_ids[0], product_ids[0], 100),  # Pallet Gỗ in Kho Q1
                (warehouse_ids[0], product_ids[1], 5),    # Xe nâng in Kho Q1
                (warehouse_ids[0], product_ids[2], 500),  # Thùng carton in Kho Q1
                (warehouse_ids[0], product_ids[3], 200),  # Màng bọc in Kho Q1
                (warehouse_ids[1], product_ids[4], 50),   # Kệ sắt in Kho Thủ Đức
                (warehouse_ids[1], product_ids[5], 20),   # Xe đẩy in Kho Thủ Đức
                (warehouse_ids[2], product_ids[6], 1000), # Bao tải in Kho Bình Tân
                (warehouse_ids[2], product_ids[7], 300),  # Dây đeo in Kho Hóc Môn
                (warehouse_ids[3], product_ids[8], 150),  # Thùng nhựa in Kho Bình Chánh
                (warehouse_ids[3], product_ids[9], 100), # Kẹp chì in Kho Q1
                (warehouse_ids[4], product_ids[10], 3),  # Máy in mã vạch in Kho Thủ Đức
                (warehouse_ids[4], product_ids[11], 800), # Băng keo in Kho Bình Tân
                (warehouse_ids[0], product_ids[12], 200), # Giấy in hóa đơn in Kho Hóc Môn
                (warehouse_ids[0], product_ids[13], 50),  # Bút laser in Kho Bình Chánh
                (warehouse_ids[1], product_ids[14], 25),  # Đồng hồ in Kho Q1
                (warehouse_ids[1], product_ids[15], 15),  # Bàn làm việc in Kho Thủ Đức
                (warehouse_ids[2], product_ids[16], 30),  # Ghế văn phòng in Kho Bình Tân
                (warehouse_ids[2], product_ids[17], 10),  # Laptop in Kho Hóc Môn
                (warehouse_ids[3], product_ids[18], 20),  # Máy tính để bàn in Kho Bình Chánh
                (warehouse_ids[3], product_ids[19], 35),  # Màn hình in Kho Q1
                (warehouse_ids[4], product_ids[20], 60),  # Bàn phím cơ in Kho Thủ Đức
                (warehouse_ids[4], product_ids[21], 100)  # Chuột không dây in Kho Bình Tân
            ]
            
            for warehouse_id, product_id, quantity in inventory_data:
                conn.execute(text("""
                    INSERT INTO warehouse_inventory (warehouse_id, product_id, quantity) 
                    VALUES (:warehouse_id, :product_id, :quantity)
                """), {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": quantity})
            
            conn.commit()
        
        print("✅ Warehouse inventory loaded successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error loading inventory: {e}")
        return False

if __name__ == '__main__':
    load_inventory()
