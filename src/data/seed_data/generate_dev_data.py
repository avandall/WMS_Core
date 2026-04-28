#!/usr/bin/env python3
"""
Development Data Generator
Generates additional sample data using Faker for development environment.
"""

import os
import sys
import random
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

try:
    from app.shared.core.settings import settings
    from app.shared.core.database import Base
    from app.infrastructure.persistence.models import import_all_models
except ImportError:
    print("Error: Could not import WMS modules. Make sure you're in the correct directory.")
    sys.exit(1)

class DevDataGenerator:
    def __init__(self):
        # Initialize Faker with Vietnamese locale for realistic data
        self.fake = Faker('vi_VN')
        Faker.seed(42)  # For reproducible data
        
        # Connect to database
        self.engine = create_engine(settings.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Import all models
        import_all_models()
    
    def check_database_empty(self):
        """Check if database is empty (except for seed data)."""
        session = self.SessionLocal()
        try:
            # Check if we have more than seed data
            product_count = session.execute(text("SELECT COUNT(*) FROM products")).scalar()
            warehouse_count = session.execute(text("SELECT COUNT(*) FROM warehouses")).scalar()
            
            # Seed data has 22 products and 5 warehouses
            return product_count <= 22 and warehouse_count <= 5
        finally:
            session.close()
    
    def generate_warehouses(self, count=10):
        """Generate additional warehouses."""
        session = self.SessionLocal()
        try:
            warehouses = []
            cities = ['Hà Nội', 'TP. Hồ Chí Minh', 'Đà Nẵng', 'Hải Phòng', 'Cần Thơ', 
                     'Biên Hòa', 'Nha Trang', 'Buôn Ma Thuột', 'Huế', 'Rạch Giá']
            
            for i in range(count):
                city = random.choice(cities)
                street = self.fake.street_address()
                warehouse = {
                    'name': f'Kho {self.fake.company()} {city}',
                    'location': f'{street}, {city}'
                }
                warehouses.append(warehouse)
            
            # Insert warehouses
            for warehouse in warehouses:
                session.execute(text("""
                    INSERT INTO warehouses (location) 
                    VALUES (:location)
                """), warehouse)
            
            session.commit()
            print(f"✅ Generated {count} additional warehouses")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error generating warehouses: {e}")
        finally:
            session.close()
    
    def generate_products(self, count=100):
        """Generate additional products."""
        session = self.SessionLocal()
        try:
            products = []
            
            # Product categories
            categories = {
                'Vật tư kho': ['Pallet', 'Kệ', 'Xe đẩy', 'Thùng', 'Bao tải'],
                'Thiết bị văn phòng': ['Máy tính', 'Laptop', 'Màn hình', 'Bàn phím', 'Chuột'],
                'Công cụ': ['Dụng cụ cầm tay', 'Máy móc', 'Điện tử', 'Đo lường'],
                'Vật tư đóng gói': ['Carton', 'Màng bọc', 'Băng keo', 'Kẹp chì', 'Thùng nhựa'],
                'Thiết bị an toàn': ['Mũ bảo hiểm', 'Găng tay', 'Giày bảo hộ', 'Kính bảo hộ']
            }
            
            for i in range(count):
                category = random.choice(list(categories.keys()))
                product_type = random.choice(categories[category])
                
                # Generate SKU
                sku_prefix = ''.join(word[0].upper() for word in product_type.split())
                sku = f"{sku_prefix}-{str(i+1000).zfill(3)}"
                
                # Generate price based on category
                if 'Văn phòng' in category:
                    price = random.randint(500000, 20000000)
                elif 'Kho' in category:
                    price = random.randint(50000, 5000000)
                elif 'Công cụ' in category:
                    price = random.randint(100000, 10000000)
                else:
                    price = random.randint(10000, 1000000)
                
                product = {
                    'name': f'{product_type} {self.fake.word().title()}',
                    'sku': sku,
                    'price': price,
                    'description': f'{product_type} cao cấp, {self.fake.sentence()}'
                }
                products.append(product)
            
            # Insert products
            for product in products:
                session.execute(text("""
                    INSERT INTO products (name, sku, price, description) 
                    VALUES (:name, :sku, :price, :description)
                """), product)
            
            session.commit()
            print(f"✅ Generated {count} additional products")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error generating products: {e}")
        finally:
            session.close()
    
    def generate_customers(self, count=50):
        """Generate additional customers."""
        session = self.SessionLocal()
        try:
            customers = []
            
            for i in range(count):
                customer = {
                    'name': self.fake.company(),
                    'email': self.fake.company_email(),
                    'phone': self.fake.phone_number(),
                    'address': self.fake.address()
                }
                customers.append(customer)
            
            # Insert customers
            for customer in customers:
                session.execute(text("""
                    INSERT INTO customers (name, email, phone, address) 
                    VALUES (:name, :email, :phone, :address)
                """), customer)
            
            session.commit()
            print(f"✅ Generated {count} additional customers")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error generating customers: {e}")
        finally:
            session.close()
    
    def generate_inventory(self, count=200):
        """Generate inventory records."""
        session = self.SessionLocal()
        try:
            # Get existing products and warehouses
            products = session.execute(text("SELECT product_id FROM products ORDER BY product_id")).fetchall()
            warehouses = session.execute(text("SELECT warehouse_id FROM warehouses ORDER BY warehouse_id")).fetchall()
            
            if not products or not warehouses:
                print("❌ No products or warehouses found")
                return
            
            inventory_records = []
            
            for i in range(count):
                product_id = random.choice(products)[0]
                warehouse_id = random.choice(warehouses)[0]
                quantity = random.randint(0, 1000)
                
                inventory_records.append({
                    'product_id': product_id,
                    'warehouse_id': warehouse_id,
                    'quantity': quantity
                })
            
            # Insert inventory records
            for record in inventory_records:
                # Check if record already exists
                existing = session.execute(text("""
                    SELECT COUNT(*) FROM warehouse_inventory 
                    WHERE product_id = :product_id AND warehouse_id = :warehouse_id
                """), record).scalar()
                
                if existing == 0:
                    session.execute(text("""
                        INSERT INTO warehouse_inventory (product_id, warehouse_id, quantity) 
                        VALUES (:product_id, :warehouse_id, :quantity)
                    """), record)
            
            session.commit()
            print(f"✅ Generated {count} inventory records")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error generating inventory: {e}")
        finally:
            session.close()
    
    def generate_documents(self, count=50):
        """Generate sample documents."""
        session = self.SessionLocal()
        try:
            # Get existing data
            warehouses = session.execute(text("SELECT warehouse_id FROM warehouse ORDER BY warehouse_id")).fetchall()
            users = session.execute(text("SELECT user_id, email FROM users ORDER BY user_id")).fetchall()
            
            if not warehouses or not users:
                print("❌ No warehouses or users found")
                return
            
            documents = []
            document_items = []
            
            doc_types = ['IMPORT', 'EXPORT', 'TRANSFER', 'SALE']
            
            for i in range(count):
                doc_type = random.choice(doc_types)
                user_id = random.choice(users)[0]
                
                # Determine warehouses based on document type
                if doc_type == 'IMPORT':
                    from_warehouse = None
                    to_warehouse = random.choice(warehouses)[0]
                elif doc_type == 'EXPORT' or doc_type == 'SALE':
                    from_warehouse = random.choice(warehouses)[0]
                    to_warehouse = None
                else:  # TRANSFER
                    from_warehouse = random.choice(warehouses)[0]
                    to_warehouse = random.choice(warehouses)[0]
                    # Ensure different warehouses for transfer
                    while to_warehouse == from_warehouse:
                        to_warehouse = random.choice(warehouses)[0]
                
                # Generate document
                created_at = self.fake.date_time_between(start_date='-30d', end_date='now')
                total_value = random.randint(1000000, 50000000)
                
                document = {
                    'doc_type': doc_type,
                    'from_warehouse_id': from_warehouse,
                    'to_warehouse_id': to_warehouse,
                    'created_by': random.choice(users)[1],
                    'status': random.choice(['DRAFT', 'POSTED']),
                    'total_value': total_value,
                    'created_at': created_at
                }
                documents.append(document)
            
            # Insert documents
            doc_ids = []
            for doc in documents:
                result = session.execute(text("""
                    INSERT INTO documents (doc_type, from_warehouse_id, to_warehouse_id, created_by, status, total_value, created_at)
                    VALUES (:doc_type, :from_warehouse_id, :to_warehouse_id, :created_by, :status, :total_value, :created_at)
                    RETURNING document_id
                """), doc)
                doc_id = result.scalar()
                doc_ids.append(doc_id)
            
            # Generate document items
            products = session.execute(text("SELECT product_id, price FROM products ORDER BY product_id")).fetchall()
            
            for doc_id in doc_ids:
                num_items = random.randint(1, 5)
                selected_products = random.sample(products, min(num_items, len(products)))
                
                for product_id, price in selected_products:
                    quantity = random.randint(1, 100)
                    unit_price = price * random.uniform(0.9, 1.1)  # Slight price variation
                    
                    item = {
                        'document_id': doc_id,
                        'product_id': product_id,
                        'quantity': quantity,
                        'unit_price': int(unit_price)
                    }
                    document_items.append(item)
            
            # Insert document items
            for item in document_items:
                session.execute(text("""
                    INSERT INTO document_items (document_id, product_id, quantity, unit_price)
                    VALUES (:document_id, :product_id, :quantity, :unit_price)
                """), item)
            
            session.commit()
            print(f"✅ Generated {count} documents with {len(document_items)} items")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error generating documents: {e}")
        finally:
            session.close()
    
    def generate_all_data(self):
        """Generate all development data."""
        print("🚀 Starting development data generation...")
        print(f"📊 Database URL: {settings.database_url}")
        
        # Skip empty check - just generate data
        # if not self.check_database_empty():
        #     print("⚠️  Database already contains data. Skipping generation.")
        #     return
        
        print("📝 Database is empty. Generating sample data...")
        
        # Generate data in order of dependencies
        self.generate_warehouses(10)
        self.generate_products(100)
        self.generate_customers(50)
        self.generate_inventory(200)
        self.generate_documents(50)
        
        print("✅ Development data generation complete!")
        print("🎉 Your WMS now has rich sample data for testing!")

def main():
    """Main function to run the data generator."""
    # Check if we're in development mode
    if not getattr(settings, 'debug', False) or os.getenv('ENVIRONMENT') != 'development':
        print("⚠️  This script should only be run in development mode!")
        print("Set ENVIRONMENT=development and DEBUG=true in your environment.")
        return
    
    # Check if auto-seed is enabled
    auto_seed = os.getenv('AUTO_SEED_DATA', 'false').lower() == 'true'
    if not auto_seed:
        print("⚠️  Auto-seed data is disabled. Set AUTO_SEED_DATA=true to enable.")
        return
    
    generator = DevDataGenerator()
    generator.generate_all_data()

if __name__ == '__main__':
    main()
