from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger, request_id_ctx
from app.core.transaction import TransactionalRepository
from app.infrastructure.persistence.models import AuditEventModel

logger = get_logger(__name__)


class AuditEventRepo(TransactionalRepository):
    """Repository for domain audit events (business-level audit trail)."""

    def __init__(self, session: Session):
        super().__init__(session)

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
        event = AuditEventModel(
            request_id=request_id_ctx.get(),
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            warehouse_id=warehouse_id,
            payload=payload,
        )
        self.session.add(event)
        self._commit_if_auto()
        logger.info(
            f"Audit event: action={action} entity_type={entity_type} entity_id={entity_id} warehouse_id={warehouse_id}"
        )
        return event.id

    def get(self, event_id: int) -> Optional[AuditEventModel]:
        return self.session.get(AuditEventModel, event_id)

    def list_events(
        self,
        *,
        request_id: Optional[str] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        warehouse_id: Optional[int] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventModel]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))

        stmt = select(AuditEventModel)
        if request_id:
            stmt = stmt.where(AuditEventModel.request_id == request_id)
        if user_id is not None:
            stmt = stmt.where(AuditEventModel.user_id == user_id)
        if action:
            stmt = stmt.where(AuditEventModel.action == action)
        if entity_type:
            stmt = stmt.where(AuditEventModel.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditEventModel.entity_id == entity_id)
        if warehouse_id is not None:
            stmt = stmt.where(AuditEventModel.warehouse_id == warehouse_id)
        if created_from is not None:
            stmt = stmt.where(AuditEventModel.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(AuditEventModel.created_at <= created_to)

        rows = (
            self.session.execute(
                stmt.order_by(AuditEventModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows)
