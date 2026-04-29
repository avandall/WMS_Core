from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: int
    request_id: Optional[str] = None
    user_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    warehouse_id: Optional[int] = None
    payload: Optional[dict[str, Any]] = None
    created_at: datetime

