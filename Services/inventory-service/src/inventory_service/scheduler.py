from __future__ import annotations

import asyncio
import logging
from typing import Optional

from inventory_service.jobs.expire_reservations import expire_expired_reservations

logger = logging.getLogger(__name__)


class ReservationExpiryScheduler:
    """
    Background job scheduler running every interval_seconds (default 5 min = 300s)
    to automatically expire stock reservations using Redis Distributed Lock.
    """

    def __init__(self, interval_seconds: float = 300.0) -> None:
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task[None]] = None
        self._stopping: bool = False

    async def _loop(self) -> None:
        logger.info(f"[ReservationExpiryScheduler] Started background scheduler (interval={self.interval_seconds}s)")
        while not self._stopping:
            try:
                expired = await asyncio.to_thread(expire_expired_reservations)
                if expired > 0:
                    logger.info(f"[ReservationExpiryScheduler] Expired {expired} reservations.")
            except Exception as e:
                logger.error(f"[ReservationExpiryScheduler] Error running expiry job: {e}", exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None


_scheduler: Optional[ReservationExpiryScheduler] = None


def start_reservation_expiry_scheduler(interval_seconds: float = 300.0) -> ReservationExpiryScheduler:
    global _scheduler
    _scheduler = ReservationExpiryScheduler(interval_seconds=interval_seconds)
    _scheduler.start()
    return _scheduler


async def stop_reservation_expiry_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        await _scheduler.stop()
        _scheduler = None
