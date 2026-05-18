from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatDBRequest(BaseModel):
    message: str = Field(..., min_length=1)
    include_rows: bool = False
    mode: Optional[str] = Field("auto", description="Processing mode: 'auto', 'rag', 'sql', 'hybrid'")


class ChatDBResponse(BaseModel):
    answer: str
    sql: str
    rows: list[dict[str, Any]] | None = None
    mode: Optional[str] = Field(None, description="Processing mode used: 'rag', 'sql', 'hybrid'")
    engine_info: Optional[str] = Field(None, description="Additional engine information")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")

