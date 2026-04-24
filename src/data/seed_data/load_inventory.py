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
            # Clear existing inventory first to avoid duplicates
            print("?? Clearing existing inventory...")
            conn.execute(text("DELETE FROM warehouse_inventory"))
            conn.commit()
            
            # Get actual warehouse IDs
            result = conn.execute(text("SELECT warehouse_id FROM warehouses ORDER BY warehouse_id"))
            warehouse_ids = [row[0] for row in result]
            print(f"Found warehouse IDs: {warehouse_ids}")
            
            # Get actual product IDs (first 22 products)
            result = conn.execute(text("SELECT product_id FROM products ORDER BY product_id LIMIT 22"))
            product_ids = [row[0] for row in result]
            print(f"Found product IDs: {product_ids}")
            
            # Insert warehouse inventory with correct IDs
            print("?? Loading warehouse inventory...")
            inventory_data = [
                (warehouse_ids[0], product_ids[0], 100),  # Pallet G?? in Kho Q1
                (warehouse_ids[0], product_ids[1], 5),    # Xe n??ng in Kho Q1
                (warehouse_ids[0], product_ids[2], 500),  # Th??ng carton in Kho Q1
                (warehouse_ids[0], product_ids[3], 200),  # M??ng b??c in Kho Q1
                (warehouse_ids[1], product_ids[4], 50),   # K?? s??t in Kho Th?? ??c
                (warehouse_ids[1], product_ids[5], 20),   # Xe ??y in Kho Th?? ??c
                (warehouse_ids[2], product_ids[6], 1000), # Bao t??i in Kho B??nh T??n
                (warehouse_ids[2], product_ids[7], 300),  # D??y ??o in Kho H??c M??n
                (warehouse_ids[3], product_ids[8], 150),  # Th??ng nh??a in Kho B??nh Ch??nh
                (warehouse_ids[3], product_ids[9], 100), # K?p ch?? in Kho Q1
                (warehouse_ids[4], product_ids[10], 3),  # M??y in m?? v??ch in Kho Th?? ??c
                (warehouse_ids[4], product_ids[11], 800), # B??ng keo in Kho B??nh T??n
                (warehouse_ids[0], product_ids[12], 200), # Gi??y in h??a ??n in Kho H??c M??n
                (warehouse_ids[0], product_ids[13], 50),  # B??t laser in Kho B??nh Ch??nh
                (warehouse_ids[1], product_ids[14], 25),  # ??ng h?? in Kho Q1
                (warehouse_ids[1], product_ids[15], 15),  # B??n l??m vi??c in Kho Th?? ??c
                (warehouse_ids[2], product_ids[16], 30),  # Gh?? v??n ph??ng in Kho B??nh T??n
                (warehouse_ids[2], product_ids[17], 10),  # Laptop in Kho H??c M??n
                (warehouse_ids[3], product_ids[18], 20),  # M??y t??nh ?? b??n in Kho B??nh Ch??nh
                (warehouse_ids[3], product_ids[19], 35),  # M??n h??nh in Kho Q1
                (warehouse_ids[4], product_ids[20], 60),  # B??n ph??m c?? in Kho Th?? ??c
                (warehouse_ids[4], product_ids[21], 100)  # Chu??t kh??ng d??y in Kho B??nh T??n
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
