import asyncio
import random
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.auth import hash_password
from app.core.database import Base, engine

# Import các model chính xác từ project của bạn
from app.infrastructure.persistence.models.user_table import UserModel
from app.infrastructure.persistence.models.warehouse_table import WarehouseModel, WarehouseInventoryModel
from app.infrastructure.persistence.models.product_table import ProductModel
from app.infrastructure.persistence.models.customer_table import CustomerModel
from app.infrastructure.persistence.models.document_table import DocumentModel
from app.infrastructure.persistence.models.document_item_table import DocumentItemModel
from app.infrastructure.persistence.models.position_table import PositionModel
from app.infrastructure.persistence.models.position_inventory_table import PositionInventoryModel
from app.infrastructure.persistence.models.inventory_table import InventoryModel
from app.infrastructure.persistence.models.audit_log_table import AuditLogModel
from app.infrastructure.persistence.models.audit_event_table import AuditEventModel
from app.infrastructure.persistence.models import *

from faker import Faker
fake = Faker(['vi_VN'])

async def run_seed():
    # 1. Đảm bảo bảng tồn tại (Sử dụng engine đồng bộ)
    print("🏗️  Đang khởi tạo cấu trúc bảng (Schema)...")
    from app.core.database import engine, Base
    
    # Quan trọng: Lệnh này sẽ tạo tất cả các bảng đã được import ở trên
    Base.metadata.create_all(bind=engine) 
    print("✅ Cấu trúc bảng đã sẵn sàng.")

    db = SessionLocal()
    try:
        print("🧹 Đang dọn dẹp dữ liệu cũ...")
        tables = [
            "position_inventory", "warehouse_inventory", "document_items", 
            "documents", "inventory", "positions", "products", 
            "customer_purchases", "customers", "warehouses", "users", "audit_logs", "audit_events"
        ]
        db.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        db.commit()

        # 1. TẠO USERS
        print("👤 Đang tạo tài khoản người dùng...")
        target_users = [
            {"email": "admin@wms.com", "name": "System Admin", "role": "admin"},
            {"email": "manager@wms.com", "name": "Warehouse Manager", "role": "warehouse"},
            {"email": "guest@wms.com", "name": "Guest User", "role": "user"}
        ]
        for u in target_users:
            db.add(UserModel(
                email=u["email"],
                full_name=u["name"],
                hashed_password=hash_password("admin123"),
                role=u["role"],
                is_active=1
            ))
        db.flush()

        # 2. TẠO WAREHOUSES & POSITIONS
        print("🏠 Đang tạo kho và vị trí kệ...")
        warehouses = []
        positions = []
        for i in range(2):
            wh = WarehouseModel(location=f"Kho {fake.city()} - Khu vực {i+1}")
            db.add(wh)
            db.flush()
            warehouses.append(wh)
            
            for shelf in ["A", "B"]:
                for b in range(1, 3):
                    pos = PositionModel(
                        warehouse_id=wh.warehouse_id,
                        code=f"{shelf}-{b:02d}",
                        type="STORAGE",
                        is_active=1
                    )
                    db.add(pos)
                    positions.append(pos)
        db.flush()

        # 3. TẠO CUSTOMERS
        print("🤝 Đang tạo khách hàng...")
        customers = []
        for _ in range(5):
            cust = CustomerModel(
                name=fake.company(),
                email=fake.email(),
                phone=fake.phone_number(),
                address=fake.address(),
                debt_balance=0.0
            )
            db.add(cust)
            db.flush()
            customers.append(cust)

        # 4. TẠO PRODUCTS (Khởi tạo danh sách 'products' tại đây để tránh lỗi undefined)
        print("📦 Đang tạo sản phẩm...")
        products = [] # Đã định nghĩa biến này
        for i in range(1, 11):
            p = ProductModel(
                product_id=2000 + i,
                name=fake.catch_phrase(),
                description=f"Sản phẩm công nghiệp {i}",
                price=random.uniform(100000, 1000000)
            )
            db.add(p)
            db.flush()
            products.append(p) # Lưu vào list để dùng cho bước sau

        # 5. TẠO INVENTORY & STOCK
        print("📉 Đang đổ hàng vào kho...")
        for p in products:
            # Tồn kho tổng
            db.add(InventoryModel(product_id=p.product_id, quantity=100))
            # Tồn kho tại kho cụ thể
            wh = random.choice(warehouses)
            db.add(WarehouseInventoryModel(warehouse_id=wh.warehouse_id, product_id=p.product_id, quantity=100))
            # Tồn kho tại vị trí cụ thể
            pos = random.choice([p_pos for p_pos in positions if p_pos.warehouse_id == wh.warehouse_id])
            db.add(PositionInventoryModel(position_id=pos.id, product_id=p.product_id, quantity=100))

        # 6. TẠO DOCUMENTS (Sửa lỗi Source Warehouse)
        print("📄 Đang tạo chứng từ nhập xuất...")
        for i in range(10):
            doc_type = "IMPORT" if i % 2 == 0 else "EXPORT"
            wh = random.choice(warehouses)
            cust = random.choice(customers)
            
            doc = DocumentModel(
                doc_type=doc_type,
                status="POSTED",
                created_by="admin@wms.com",
                customer_id=cust.customer_id,
                # EXPORT cần from_warehouse, IMPORT cần to_warehouse
                from_warehouse_id=wh.warehouse_id if doc_type == "EXPORT" else None,
                to_warehouse_id=wh.warehouse_id if doc_type == "IMPORT" else None,
                created_at=datetime.now()
            )
            db.add(doc)
            db.flush()
            
            # Chọn ngẫu nhiên sản phẩm từ danh sách 'products' đã tạo ở bước 4
            p_selected = random.choice(products)
            db.add(DocumentItemModel(
                document_id=doc.document_id,
                product_id=p_selected.product_id,
                quantity=random.randint(5, 20),
                unit_price=p_selected.price
            ))

        db.commit()
        print("\n" + "="*40)
        print("✨ SEED COMPLETED SUCCESSFULLY!")
        print(f"Tài khoản Admin: admin@wms.com / admin123")
        print("="*40)

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_seed())