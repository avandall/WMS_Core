"""Database configuration and helpers for the WMS application."""

import os
import time
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


def _schema_bootstrap_enabled() -> bool:
    return _truthy_env("LOCAL_DB_BOOTSTRAP_ENABLED") or _truthy_env("SERVICE_MIGRATION_MODE")


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
        "app.modules.customers.infrastructure.models.customer",
        "app.modules.customers.infrastructure.models.customer_purchase",
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
            Base.metadata.create_all(bind=engine, tables=_init_db_tables())
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
