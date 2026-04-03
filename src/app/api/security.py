"""API security and validation helpers."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import HTTPException, status

from app.core.logging import get_logger
from app.core.settings import settings

logger = get_logger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter (use Redis in production)."""

    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def check_rate_limit(self, client_ip: str, limit: Optional[int] = None) -> bool:
        if limit is None:
            limit = settings.rate_limit_per_minute

        async with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=1)
            self.requests[client_ip] = [
                t for t in self.requests[client_ip] if t > cutoff
            ]
            if len(self.requests[client_ip]) >= limit:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return False
            self.requests[client_ip].append(now)
            return True


rate_limiter = RateLimiter()


def validate_pagination_params(page: int = 1, page_size: int = 20, max_page_size: int = 100):
    if page < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page number must be >= 1")
    if page_size < 1 or page_size > max_page_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page size must be between 1 and {max_page_size}",
        )
    return page, page_size


def validate_id_parameter(entity_id: int, entity_name: str = "Entity"):
    if entity_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{entity_name} ID must be positive",
        )
    return entity_id

