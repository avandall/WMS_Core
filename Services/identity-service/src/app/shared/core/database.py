"""Database configuration and helpers for the WMS application."""

import os
import time
from datetime import datetime
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from app.shared.core.settings import settings
from app.shared.core.logging import get_logger

logger = get_logger(__name__)

engine = create_engine(
    settings.database_url,
    future=True,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    poolclass=QueuePool,
    connect_args={
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000",
    }
    if "postgresql" in settings.database_url
    else {},
)

@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    logger.debug("Database connection established")


@event.listens_for(engine, "close")
def receive_close(dbapi_conn, connection_record):
    logger.debug("Database connection closed")


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if hasattr(context, "_query_start_time"):
        elapsed_ms = (time.perf_counter() - context._query_start_time) * 1000
        if elapsed_ms > 200:
            logger.warning(f"Slow query ({elapsed_ms:.1f} ms): {statement}")

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def _init_db_tables():
    configured = os.getenv("INIT_DB_TABLES", "")
    if configured.strip() == "__none__":
        return []
    table_names = [name.strip() for name in configured.split(",") if name.strip()]
    return [Base.metadata.tables[name] for name in table_names if name in Base.metadata.tables] or None


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _row_exists(conn, query: str, params: dict[str, object] | None = None) -> bool:
    result = conn.execute(text(query), params or {})
    return result.scalar_one_or_none() is not None


def _local_db_bootstrap_enabled() -> bool:
    return _truthy_env("LOCAL_DB_BOOTSTRAP_ENABLED")


def _schema_bootstrap_enabled() -> bool:
    return _local_db_bootstrap_enabled() or _truthy_env("SERVICE_MIGRATION_MODE")


def _seed_dev_users(conn) -> int:
    from app.shared.core.auth import hash_password

    dev_users = [
        {
            "user_id": 1,
            "email": "admin@wms.vn",
            "password": "admin123",
            "role": "admin",
            "full_name": "Administrator",
            "is_active": 1,
        },
        {
            "user_id": 2,
            "email": "warehouse@wms.vn",
            "password": "warehouse123",
            "role": "warehouse",
            "full_name": "Warehouse",
            "is_active": 1,
        },
        {
            "user_id": 3,
            "email": "sales@wms.vn",
            "password": "sales123",
            "role": "sales",
            "full_name": "Sales",
            "is_active": 1,
        },
        {
            "user_id": 4,
            "email": "accountant@wms.vn",
            "password": "account123",
            "role": "accountant",
            "full_name": "Accountant",
            "is_active": 1,
        },
    ]
    inserted = 0
    for user in dev_users:
        if not _row_exists(conn, "SELECT 1 FROM users WHERE email = :email", {"email": user["email"]}):
            conn.execute(
                text(
                    """
                    INSERT INTO users (user_id, email, hashed_password, role, full_name, is_active, created_at)
                    VALUES (:user_id, :email, :hashed_password, :role, :full_name, :is_active, :created_at)
                    """
                ),
                {
                    "user_id": user["user_id"],
                    "email": user["email"],
                    "hashed_password": hash_password(user["password"]),
                    "role": user["role"],
                    "full_name": user["full_name"],
                    "is_active": user["is_active"],
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
            inserted += 1
    return inserted


def get_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database session error: {type(e).__name__}: {str(e)}")
        db.rollback()
        raise
    finally:
        db.expunge_all()
        db.close()


def import_all_models():
    """Import all SQLAlchemy models from all modules for database initialization."""
    import importlib

    model_modules = [
        "app.modules.users.infrastructure.models.user",
    ]
    for module in model_modules:
        try:
            importlib.import_module(module)
        except ModuleNotFoundError:
            logger.debug("Skipping unavailable model module: %s", module)


def init_db() -> None:
    try:
        import_all_models()
        if not _schema_bootstrap_enabled():
            logger.info("Skipping runtime table bootstrap; run the service migration command before startup")
            return

        if engine.dialect.name == "postgresql":
            lock_id = 471999
            with engine.connect() as conn:
                conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
                try:
                    Base.metadata.create_all(bind=conn, tables=_init_db_tables())
                    if _local_db_bootstrap_enabled():
                        inserted = _seed_dev_users(conn)
                        if inserted:
                            logger.info(f"Seeded {inserted} local dev user(s) into identity DB")
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    try:
                        conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
                    except Exception:
                        conn.rollback()
                        conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
        else:
            with engine.begin() as conn:
                Base.metadata.create_all(bind=conn, tables=_init_db_tables())
                if _local_db_bootstrap_enabled():
                    inserted = _seed_dev_users(conn)
                    if inserted:
                        logger.info(f"Seeded {inserted} local dev user(s) into identity DB")
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False
