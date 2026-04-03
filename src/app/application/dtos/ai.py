from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatDBRequest(BaseModel):
    message: str = Field(..., min_length=1)
    include_rows: bool = False


class ChatDBResponse(BaseModel):
    answer: str
    sql: str
    rows: list[dict[str, Any]] | None = None

