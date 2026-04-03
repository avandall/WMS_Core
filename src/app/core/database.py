"""Database configuration and helpers for the WMS application."""

import time
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from app.core.settings import settings
from app.core.logging import get_logger

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


def init_db() -> None:
    try:
        from app.infrastructure.persistence import models as persistence_models

        persistence_models.import_all_models()

        if engine.dialect.name == "postgresql":
            lock_id = 471999
            with engine.connect() as conn:
                conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
                try:
                    Base.metadata.create_all(bind=conn)
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
            Base.metadata.create_all(bind=engine)
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
