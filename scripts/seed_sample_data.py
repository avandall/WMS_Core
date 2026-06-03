from __future__ import annotations

import argparse
from datetime import datetime
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine


SERVICE_OPTIONS = [
    "identity",
    "customers",
    "products",
    "warehouses",
    "inventory",
    "documents",
]

DEFAULT_DATABASE_URLS = {
    "identity": "sqlite:////tmp/wms-identity.db",
    "customers": "sqlite:////tmp/wms-customer.db",
    "products": "sqlite:////tmp/wms-product.db",
    "warehouses": "sqlite:////tmp/wms-warehouse.db",
    "inventory": "sqlite:////tmp/wms-inventory.db",
    "documents": "sqlite:////tmp/wms-documents.db",
}

SAMPLE_USERS = [
    {
        "user_id": 1,
        "email": "admin@wms.vn",
        "hashed_password": "placeholder-password-hash",
        "role": "admin",
        "full_name": "Administrator",
        "is_active": 1,
    },
    {
        "user_id": 2,
        "email": "warehouse@wms.vn",
        "hashed_password": "placeholder-password-hash",
        "role": "warehouse",
        "full_name": "Warehouse",
        "is_active": 1,
    },
    {
        "user_id": 3,
        "email": "sales@wms.vn",
        "hashed_password": "placeholder-password-hash",
        "role": "sales",
        "full_name": "Sales Representative",
        "is_active": 1,
    },
    {
        "user_id": 4,
        "email": "accountant@wms.vn",
        "hashed_password": "placeholder-password-hash",
        "role": "accountant",
        "full_name": "Accountant",
        "is_active": 1,
    },
]

SAMPLE_CUSTOMERS = [
    {
        "name": "Acme Corp",
        "email": "accounts@acme.example",
        "phone": "+1-555-0130",
        "address": "100 Market Street, Springfield",
        "debt_balance": 420.50,
    },
    {
        "name": "Beta Retail",
        "email": "orders@beta.example",
        "phone": "+1-555-0140",
        "address": "245 Commerce Ave, Centerville",
        "debt_balance": 0.0,
    },
]

SAMPLE_PRODUCTS = [
    {
        "product_id": 1001,
        "name": "Industrial Widget",
        "description": "High-quality widget for assembly lines.",
        "price": 12.99,
    },
    {
        "product_id": 1002,
        "name": "Packing Foam",
        "description": "Protective foam for fragile shipments.",
        "price": 4.5,
    },
    {
        "product_id": 1003,
        "name": "Forklift Battery",
        "description": "Heavy-duty battery for industrial forklifts.",
        "price": 199.0,
    },
]

SAMPLE_WAREHOUSES = [
    {"warehouse_id": 1, "location": "North Warehouse"},
    {"warehouse_id": 2, "location": "South Warehouse"},
]

SAMPLE_INVENTORY = [
    {"product_id": 1001, "quantity": 150},
    {"product_id": 1002, "quantity": 90},
    {"product_id": 1003, "quantity": 60},
]

SAMPLE_WAREHOUSE_INVENTORY = [
    {"warehouse_id": 1, "product_id": 1001, "quantity": 50},
    {"warehouse_id": 1, "product_id": 1002, "quantity": 30},
    {"warehouse_id": 1, "product_id": 1003, "quantity": 20},
    {"warehouse_id": 2, "product_id": 1001, "quantity": 100},
    {"warehouse_id": 2, "product_id": 1002, "quantity": 60},
    {"warehouse_id": 2, "product_id": 1003, "quantity": 40},
]

SAMPLE_DOCUMENTS = [
    {
        "document_id": 2001,
        "doc_type": "SALE",
        "status": "DRAFT",
        "from_warehouse_id": 1,
        "to_warehouse_id": None,
        "created_by": "sales@wms.vn",
        "approved_by": None,
        "note": "Customer order pending approval.",
        "customer_id": 1,
        "posted_at": None,
        "cancelled_at": None,
        "cancellation_reason": None,
        "items": [
            {"product_id": 1001, "quantity": 10, "unit_price": 12.99},
            {"product_id": 1002, "quantity": 5, "unit_price": 4.5},
        ],
    },
    {
        "document_id": 2002,
        "doc_type": "TRANSFER",
        "status": "POSTED",
        "from_warehouse_id": 1,
        "to_warehouse_id": 2,
        "created_by": "warehouse@wms.vn",
        "approved_by": "manager@wms.vn",
        "note": "Stock transfer to south warehouse.",
        "customer_id": None,
        "posted_at": "2024-01-15 09:30:00",
        "cancelled_at": None,
        "cancellation_reason": None,
        "items": [
            {"product_id": 1003, "quantity": 5, "unit_price": 199.0},
        ],
    },
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed sample data into local WMS service databases."
    )
    parser.add_argument(
        "--services",
        nargs="+",
        choices=SERVICE_OPTIONS,
        help="List of service databases to seed. Defaults to all services.",
    )
    for service in SERVICE_OPTIONS:
        parser.add_argument(
            f"--{service}-db-url",
            default=os.getenv(f"{service.upper()}_DATABASE_URL", DEFAULT_DATABASE_URLS[service]),
            help=f"Database URL for the {service} service.",
        )
    return parser.parse_args()


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


def _create_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, future=True)
    if database_url.startswith("sqlite:"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _row_exists(conn, query: str, params: dict[str, object] | None = None) -> bool:
    result = conn.execute(text(query), params or {})
    return result.scalar_one_or_none() is not None


def _create_identity_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                full_name TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _seed_identity(conn) -> int:
    inserted = 0
    for user in SAMPLE_USERS:
        if not _row_exists(conn, "SELECT 1 FROM users WHERE email = :email", {"email": user["email"]}):
            conn.execute(
                text(
                    """
                    INSERT INTO users (user_id, email, hashed_password, role, full_name, is_active, created_at)
                    VALUES (:user_id, :email, :hashed_password, :role, :full_name, :is_active, :created_at)
                    """
                ),
                {
                    **user,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
            inserted += 1
    return inserted


def _create_customers_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                debt_balance REAL NOT NULL DEFAULT 0.0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _seed_customers(conn) -> int:
    inserted = 0
    for customer in SAMPLE_CUSTOMERS:
        if not _row_exists(
            conn,
            "SELECT 1 FROM customers WHERE name = :name AND email = :email",
            {"name": customer["name"], "email": customer["email"]},
        ):
            conn.execute(
                text(
                    """
                    INSERT INTO customers (name, email, phone, address, debt_balance, created_at)
                    VALUES (:name, :email, :phone, :address, :debt_balance, :created_at)
                    """
                ),
                {
                    **customer,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
            inserted += 1
    return inserted


def _create_product_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL DEFAULT 0.0,
                CHECK (price >= 0)
            )
            """
        )
    )


def _seed_products(conn) -> int:
    inserted = 0
    for product in SAMPLE_PRODUCTS:
        if not _row_exists(
            conn,
            "SELECT 1 FROM products WHERE product_id = :product_id",
            {"product_id": product["product_id"]},
        ):
            conn.execute(
                text(
                    """
                    INSERT INTO products (product_id, name, description, price)
                    VALUES (:product_id, :name, :description, :price)
                    """
                ),
                product,
            )
            inserted += 1
    return inserted


def _create_warehouse_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS warehouses (
                warehouse_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT NOT NULL UNIQUE
            )
            """
        )
    )


def _seed_warehouses(conn) -> int:
    inserted = 0
    for warehouse in SAMPLE_WAREHOUSES:
        if not _row_exists(
            conn,
            "SELECT 1 FROM warehouses WHERE location = :location",
            {"location": warehouse["location"]},
        ):
            conn.execute(
                text(
                    """
                    INSERT INTO warehouses (warehouse_id, location)
                    VALUES (:warehouse_id, :location)
                    """
                ),
                warehouse,
            )
            inserted += 1
    return inserted


def _create_inventory_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                product_id INTEGER PRIMARY KEY,
                quantity INTEGER NOT NULL DEFAULT 0,
                CHECK (quantity >= 0)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS warehouse_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                UNIQUE (warehouse_id, product_id),
                CHECK (quantity >= 0)
            )
            """
        )
    )


def _seed_inventory(conn) -> int:
    inserted = 0
    for inventory in SAMPLE_INVENTORY:
        if not _row_exists(
            conn,
            "SELECT 1 FROM inventory WHERE product_id = :product_id",
            {"product_id": inventory["product_id"]},
        ):
            conn.execute(
                text(
                    """
                    INSERT INTO inventory (product_id, quantity)
                    VALUES (:product_id, :quantity)
                    """
                ),
                inventory,
            )
            inserted += 1
    for warehouse_inventory in SAMPLE_WAREHOUSE_INVENTORY:
        if not _row_exists(
            conn,
            "SELECT 1 FROM warehouse_inventory WHERE warehouse_id = :warehouse_id AND product_id = :product_id",
            {
                "warehouse_id": warehouse_inventory["warehouse_id"],
                "product_id": warehouse_inventory["product_id"],
            },
        ):
            conn.execute(
                text(
                    """
                    INSERT INTO warehouse_inventory (warehouse_id, product_id, quantity)
                    VALUES (:warehouse_id, :product_id, :quantity)
                    """
                ),
                warehouse_inventory,
            )
            inserted += 1
    return inserted


def _create_documents_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id INTEGER PRIMARY KEY,
                doc_type TEXT NOT NULL,
                status TEXT NOT NULL,
                from_warehouse_id INTEGER,
                to_warehouse_id INTEGER,
                created_by TEXT NOT NULL,
                approved_by TEXT,
                note TEXT,
                customer_id INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                posted_at DATETIME,
                cancelled_at DATETIME,
                cancellation_reason TEXT
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS document_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id)
            )
            """
        )
    )


def _seed_documents(conn) -> int:
    inserted = 0
    for document in SAMPLE_DOCUMENTS:
        if not _row_exists(
            conn,
            "SELECT 1 FROM documents WHERE document_id = :document_id",
            {"document_id": document["document_id"]},
        ):
            conn.execute(
                text(
                    """
                    INSERT INTO documents (
                        document_id,
                        doc_type,
                        status,
                        from_warehouse_id,
                        to_warehouse_id,
                        created_by,
                        approved_by,
                        note,
                        customer_id,
                        created_at,
                        posted_at,
                        cancelled_at,
                        cancellation_reason
                    ) VALUES (
                        :document_id,
                        :doc_type,
                        :status,
                        :from_warehouse_id,
                        :to_warehouse_id,
                        :created_by,
                        :approved_by,
                        :note,
                        :customer_id,
                        :created_at,
                        :posted_at,
                        :cancelled_at,
                        :cancellation_reason
                    )
                    """
                ),
                {
                    **document,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
            inserted += 1
            for item in document["items"]:
                conn.execute(
                    text(
                        """
                        INSERT INTO document_items (document_id, product_id, quantity, unit_price)
                        VALUES (:document_id, :product_id, :quantity, :unit_price)
                        """
                    ),
                    {
                        "document_id": document["document_id"],
                        **item,
                    },
                )
    return inserted


def _seed_service(service: str, database_url: str) -> tuple[int, str]:
    engine = _create_engine(database_url)
    with engine.begin() as conn:
        if service == "identity":
            _create_identity_tables(conn)
            count = _seed_identity(conn)
            return count, "users"
        if service == "customers":
            _create_customers_tables(conn)
            count = _seed_customers(conn)
            return count, "customers"
        if service == "products":
            _create_product_tables(conn)
            count = _seed_products(conn)
            return count, "products"
        if service == "warehouses":
            _create_warehouse_tables(conn)
            count = _seed_warehouses(conn)
            return count, "warehouses"
        if service == "inventory":
            _create_inventory_tables(conn)
            count = _seed_inventory(conn)
            return count, "inventory rows"
        if service == "documents":
            _create_documents_tables(conn)
            count = _seed_documents(conn)
            return count, "documents"
        raise ValueError(f"Unsupported service: {service}")


def main() -> int:
    args = _parse_args()
    selected_services = args.services or SERVICE_OPTIONS
    summary: list[str] = []

    for service in selected_services:
        database_url = getattr(args, f"{service}_db_url")
        print(f"Seeding {service} service database: {database_url}")
        try:
            inserted, target = _seed_service(service, database_url)
            summary.append(f"  {service}: inserted {inserted} {target}")
        except Exception as exc:  # pragma: no cover
            print(f"Failed to seed {service}: {exc}")
            return 1

    print("\nSeed result:")
    for line in summary:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
