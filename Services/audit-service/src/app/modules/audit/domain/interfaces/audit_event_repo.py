from abc import ABC, abstractmethod
from typing import Any, Optional


class IAuditEventRepo(ABC):
    @abstractmethod
    def create_event(
        self,
        *,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        warehouse_id: Optional[int] = None,
        payload: Optional[dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> int:
        pass
