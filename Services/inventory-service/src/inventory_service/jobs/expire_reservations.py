from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import redis
from redis.lock import Lock
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.shared.core.database import get_db_session

logger = logging.getLogger(__name__)


def get_redis_client(redis_client: Optional[redis.Redis] = None) -> redis.Redis:
    """Return an active Redis client or create a new instance from environment."""
    if redis_client is not None:
        return redis_client
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(redis_url, decode_responses=False)


def expire_expired_reservations(
    db: Optional[Session] = None,
    redis_client: Optional[redis.Redis] = None,
    lock_timeout: int = 60,
) -> int:
    """
    Background job to automatically expire stock reservations past their expires_at timestamp.

    Key Features & Hardening Rules:
    1. Acquires a Redis Distributed Lock ('lock:reservation_expiry') to prevent duplicate work across multi-pod clusters.
    2. Enforces system-wide Lock Ordering Rule to prevent AB-BA deadlocks:
       - Lock `inventory_locations` & `warehouse_inventory` FIRST.
       - Lock `StockReservationModel` SECOND.
    3. Uses SQL `FOR UPDATE SKIP LOCKED` for lock acquisition.
    4. Updates status from 'RESERVED' to 'EXPIRED' and releases reserved stock.
    """
    r_client = get_redis_client(redis_client)
    # Instantiate Redis Distributed Lock as required: Lock(redis, name="lock:reservation_expiry", timeout=60)
    lock = Lock(r_client, name="lock:reservation_expiry", timeout=lock_timeout)

    acquired = lock.acquire(blocking=False)
    if not acquired:
        logger.info("[ExpireReservations] Could not acquire Redis lock 'lock:reservation_expiry', skipping execution.")
        return 0

    try:
        now = datetime.now(timezone.utc)

        def _process_expiry(session: Session) -> int:
            # 1. Query candidate expired reservations
            candidate_stmt = (
                select(
                    StockReservationModel.id,
                    StockReservationModel.product_id,
                    StockReservationModel.warehouse_id,
                )
                .where(
                    StockReservationModel.status == "RESERVED",
                    StockReservationModel.expires_at.isnot(None),
                    StockReservationModel.expires_at <= now,
                )
            )
            candidates = session.execute(candidate_stmt).all()
            if not candidates:
                return 0

            cand_ids = [c.id for c in candidates]
            product_wh_pairs = {(c.product_id, c.warehouse_id) for c in candidates}

            # 2. LOCK ORDERING RULE:
            # STEP A: Lock inventory_locations and warehouse_inventory FIRST (FOR UPDATE SKIP LOCKED)
            loc_conditions = [
                and_(
                    InventoryLocationModel.product_id == pid,
                    InventoryLocationModel.warehouse_id == wid,
                )
                for pid, wid in product_wh_pairs
            ]
            if loc_conditions:
                loc_stmt = (
                    select(InventoryLocationModel)
                    .where(or_(*loc_conditions))
                    .with_for_update(skip_locked=True)
                )
                session.execute(loc_stmt).scalars().all()

            wh_conditions = [
                and_(
                    WarehouseInventoryModel.product_id == pid,
                    WarehouseInventoryModel.warehouse_id == wid,
                )
                for pid, wid in product_wh_pairs
            ]
            wh_map: dict[tuple[int, int], WarehouseInventoryModel] = {}
            if wh_conditions:
                wh_stmt = (
                    select(WarehouseInventoryModel)
                    .where(or_(*wh_conditions))
                    .with_for_update(skip_locked=True)
                )
                locked_wh_rows = session.execute(wh_stmt).scalars().all()
                wh_map = {(wh.product_id, wh.warehouse_id): wh for wh in locked_wh_rows}

            # STEP B: Lock StockReservationModel SECOND (FOR UPDATE SKIP LOCKED)
            res_stmt = (
                select(StockReservationModel)
                .where(
                    StockReservationModel.id.in_(cand_ids),
                    StockReservationModel.status == "RESERVED",
                    StockReservationModel.expires_at.isnot(None),
                    StockReservationModel.expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
            locked_reservations = session.execute(res_stmt).scalars().all()

            expired_count = 0
            for reservation in locked_reservations:
                if reservation.status != "RESERVED":
                    continue

                qty_to_release = reservation.reserved_qty
                reservation.released_qty += qty_to_release
                reservation.reserved_qty = 0
                reservation.status = "EXPIRED"
                reservation.updated_at = datetime.now(timezone.utc)

                # Update warehouse reserved_qty
                key = (reservation.product_id, reservation.warehouse_id)
                wh = wh_map.get(key)
                if wh:
                    wh.reserved_qty = max(0, wh.reserved_qty - qty_to_release)
                    wh.updated_at = datetime.now(timezone.utc)

                expired_count += 1

            session.commit()
            return expired_count

        if db is not None:
            count = _process_expiry(db)
        else:
            with get_db_session() as session:
                count = _process_expiry(session)

        return count

    finally:
        try:
            lock.release()
        except Exception as e:
            logger.debug(f"[ExpireReservations] Redis lock release note (already released/expired): {e}")
