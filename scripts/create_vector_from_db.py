#!/usr/bin/env python3
"""
Create Vector Database from Actual Database Data

This script connects to the existing database and creates vector database
with real data from the WMS system (not test data)
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def create_documents_from_database():
    """Create documents from actual database records"""
    print("=== Creating Vector Database from Actual Database ===\n")
    
    try:
        # Import database models and engine
        from app.core.database import SessionLocal, engine
        from app.infrastructure.persistence.models import (
            WarehouseModel, ProductModel, CustomerModel, DocumentModel,
            DocumentItemModel, PositionModel, InventoryModel, UserModel
        )
        from sqlalchemy.orm import Session
        from sqlalchemy import text
        
        print("1. Connecting to database...")
        db = SessionLocal()
        
        print("2. Fetching real data from database...")
        documents = []
        metadatas = []
        
        # Get warehouses data
        print("   - Fetching warehouses...")
        warehouses = db.query(WarehouseModel).all()
        for wh in warehouses:
            doc_text = f"""
            Warehouse {wh.warehouse_id}: Located at {wh.location}
            This warehouse contains multiple storage positions and manages inventory operations.
            Warehouse ID: {wh.warehouse_id}
            Location: {wh.location}
            """.strip()
            documents.append(doc_text)
            metadatas.append({
                "source": "database", 
                "table": "warehouses", 
                "warehouse_id": wh.warehouse_id,
                "category": "warehouse_info"
            })
        
        # Get products data
        print("   - Fetching products...")
        products = db.query(ProductModel).limit(20).all()  # Limit to avoid too many docs
        for product in products:
            doc_text = f"""
            Product {product.product_id}: {product.name}
            Description: {product.description}
            Price: {product.price:,.2f} VND
            Product ID: {product.product_id}
            Name: {product.name}
            """.strip()
            documents.append(doc_text)
            metadatas.append({
                "source": "database",
                "table": "products", 
                "product_id": product.product_id,
                "category": "product_info"
            })
        
        # Get customers data
        print("   - Fetching customers...")
        customers = db.query(CustomerModel).limit(10).all()
        for customer in customers:
            doc_text = f"""
            Customer: {customer.name}
            Email: {customer.email}
            Phone: {customer.phone}
            Address: {customer.address}
            Debt Balance: {customer.debt_balance:,.2f} VND
            Customer ID: {customer.customer_id}
            """.strip()
            documents.append(doc_text)
            metadatas.append({
                "source": "database",
                "table": "customers", 
                "customer_id": customer.customer_id,
                "category": "customer_info"
            })
        
        # Get documents data
        print("   - Fetching documents...")
        docs = db.query(DocumentModel).limit(15).all()
        for doc in docs:
            doc_text = f"""
            Document {doc.document_id}: {doc.doc_type}
            Status: {doc.status}
            Created by: {doc.created_by}
            Created at: {doc.created_at}
            Customer ID: {doc.customer_id}
            From Warehouse: {doc.from_warehouse_id}
            To Warehouse: {doc.to_warehouse_id}
            Document Type: {doc.doc_type}
            """.strip()
            documents.append(doc_text)
            metadatas.append({
                "source": "database",
                "table": "documents", 
                "document_id": doc.document_id,
                "doc_type": doc.doc_type,
                "category": "document_info"
            })
        
        # Get positions data
        print("   - Fetching positions...")
        positions = db.query(PositionModel).limit(20).all()
        for pos in positions:
            doc_text = f"""
            Storage Position: {pos.code}
            Type: {pos.type}
            Warehouse ID: {pos.warehouse_id}
            Active: {pos.is_active}
            Position Code: {pos.code}
            Position Type: {pos.type}
            """.strip()
            documents.append(doc_text)
            metadatas.append({
                "source": "database",
                "table": "positions", 
                "position_id": pos.id,
                "warehouse_id": pos.warehouse_id,
                "category": "position_info"
            })
        
        # Get inventory summary
        print("   - Fetching inventory summary...")
        inventory_count = db.query(InventoryModel).count()
        doc_text = f"""
        Inventory Summary:
        Total inventory records: {inventory_count}
        Each product has quantity tracking at different levels:
        - Total inventory level
        - Warehouse inventory level  
        - Position inventory level
        This three-tier system ensures accurate stock management.
        """.strip()
        documents.append(doc_text)
        metadatas.append({
            "source": "database",
            "table": "inventory",
            "category": "inventory_summary"
        })
        
        db.close()
        
        print(f"3. Created {len(documents)} documents from real database")
        
        return documents, metadatas
        
    except Exception as e:
        print(f"Error fetching database data: {e}")
        return [], []

def create_vector_db_from_db():
    """Create vector database from actual database data"""
    try:
        # Import WMS engine
        from ai_engine.core import WMSEngine, ProcessingMode
        
        print("4. Initializing WMS Engine...")
        engine = WMSEngine(mode=ProcessingMode.RAG)
        
        print("5. Getting documents from database...")
        documents, metadatas = create_documents_from_database()
        
        if not documents:
            print("❌ No documents created from database")
            return False
            
        print("6. Adding documents to vector database...")
        success = engine.add_documents(documents, metadatas)
        
        if success:
            print("7. Vector database created successfully!")
            
            # Show database info
            info = engine.get_engine_info()
            print(f"\nDatabase Information:")
            print(f"- Path: {info['vector_db_path']}")
            print(f"- Embedding Model: {info['embedding_model']}")
            print(f"- Documents Added: {len(documents)}")
            print(f"- Sources: database tables (warehouses, products, customers, documents, positions, inventory)")
            
            # Test with sample queries
            print("\n8. Testing with real data queries...")
            test_queries = [
                "Show me information about warehouses",
                "What products do we have?",
                "List customer information",
                "Show recent documents",
                "What storage positions are available?"
            ]
            
            for i, query in enumerate(test_queries, 1):
                print(f"\nTest {i}: {query}")
                result = engine.process_query(query)
                if result.get('success', False):
                    response = result.get('response', 'No response')
                    print(f"Response: {response[:150]}...")
                else:
                    print(f"Error: {result.get('error', 'Unknown error')}")
            
            print("\n=== Vector Database Created from Real Data! ===")
            return True
        else:
            print("❌ Failed to add documents to vector database")
            return False
            
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you're in the project root directory")
        print("And all dependencies are installed")
        return False
        
    except Exception as e:
        print(f"Error creating vector database: {e}")
        print("\nTroubleshooting:")
        print("1. Check .env file has database connection string")
        print("2. Ensure database is accessible")
        print("3. Check all dependencies are installed")
        return False

if __name__ == "__main__":
    create_vector_db_from_db()
