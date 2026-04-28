from __future__ import annotations

from functools import lru_cache

from app.shared.core.database import engine


@lru_cache(maxsize=1)
def get_langchain_db():
    """Connect LangChain to the WMS database via the existing SQLAlchemy engine."""

    try:
        from langchain_community.utilities import SQLDatabase
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Missing dependency: `langchain-community`.") from exc

    return SQLDatabase(
        engine,
        include_tables=[
            'products', 
            'inventory', 
            'warehouses', 
            'warehouse_inventory', 
            'documents', 
            'document_items'
        ],
        # Thêm mô tả chi tiết cho AI không hallucinate
        custom_table_info={
            "products": """
            Table containing product information.
            Columns: product_id (primary key), name, description, price
            Purpose: Master product catalog with pricing and descriptions.
            Relationships: Links to inventory, warehouse_inventory, document_items.
            Usage: Query product details, pricing, and catalog information.
            """,
            "inventory": """
            Table containing total inventory levels across all warehouses.
            Columns: product_id (foreign key to products), quantity
            Purpose: Master inventory tracking showing total stock for each product.
            Relationships: Links to products table.
            Usage: Query total stock levels, check for out-of-stock items.
            Note: quantity >= 0 constraint enforced.
            """,
            "warehouses": """
            Table containing warehouse locations and information.
            Columns: warehouse_id (primary key), location
            Purpose: Master warehouse directory with location details.
            Relationships: Links to warehouse_inventory, documents (from/to warehouses).
            Usage: Query warehouse locations, manage warehouse operations.
            Note: location field is unique and indexed.
            """,
            "warehouse_inventory": """
            Table containing inventory levels per warehouse.
            Columns: id (primary key), warehouse_id (foreign key), product_id (foreign key), quantity
            Purpose: Track stock levels for each product at each specific warehouse.
            Relationships: Links to warehouses and products tables.
            Usage: Query warehouse-specific stock, manage inventory distribution.
            Note: Unique constraint on (warehouse_id, product_id), quantity >= 0.
            """,
            "documents": """
            Table containing import/export documents and transactions.
            Columns: document_id (primary key), doc_type, status, from_warehouse_id, to_warehouse_id, 
                     created_by, approved_by, note, customer_id, created_at, posted_at, cancelled_at
            Purpose: Track all warehouse transactions (IMPORT/EXPORT documents).
            Relationships: Links to warehouses (from/to), customers, document_items.
            Usage: Query transaction history, document status, warehouse movements.
            Note: doc_type can be 'IMPORT' or 'EXPORT', status tracks document lifecycle.
            """,
            "document_items": """
            Table containing line items for each document.
            Columns: id (primary key), document_id (foreign key), product_id (foreign key), 
                     quantity, unit_price
            Purpose: Track individual products within each transaction document.
            Relationships: Links to documents and products tables.
            Usage: Query transaction details, calculate document values, track product movements.
            Note: Each document can have multiple items representing different products.
            """
        }
    )
