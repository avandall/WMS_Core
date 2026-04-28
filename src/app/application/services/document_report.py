"""Document Report classes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.modules.documents.domain.entities.document import DocumentStatus, DocumentType


@dataclass
class DocumentReportItem:
    document_id: int
    doc_type: DocumentType
    status: DocumentStatus
    date: datetime
    from_warehouse_id: Optional[int]
    to_warehouse_id: Optional[int]
    total_items: int
    total_quantity: int
    total_value: float
    created_by: str
    approved_by: Optional[str]


@dataclass
class DocumentReport:
    filters: Dict[str, Any]
    documents: List[DocumentReportItem]
    type_summary: Dict[str, int]
    status_summary: Dict[str, int]
    generated_at: datetime

    @property
    def total_documents(self) -> int:
        return len(self.documents)

    @property
    def total_value(self) -> float:
        return sum(doc.total_value for doc in self.documents)

