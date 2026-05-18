from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_audit_event_repo
from app.modules.audit.application.dtos.audit_event import AuditEventResponse
from app.shared.core.permissions import Permission
from app.modules.audit.infrastructure.repositories.audit_event_repo import AuditEventRepo

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get(
    "/",
    response_model=list[AuditEventResponse],
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
)
async def list_audit_events(
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    warehouse_id: Optional[int] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repo: AuditEventRepo = Depends(get_audit_event_repo),
):
    events = repo.list_events(
        request_id=request_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        warehouse_id=warehouse_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )
    return [
        AuditEventResponse(
            id=e.id,
            request_id=e.request_id,
            user_id=e.user_id,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            warehouse_id=e.warehouse_id,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get(
    "/{event_id}",
    response_model=AuditEventResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
)
async def get_audit_event(event_id: int, repo: AuditEventRepo = Depends(get_audit_event_repo)):
    event = repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Audit event {event_id} not found")
    return AuditEventResponse(
        id=event.id,
        request_id=event.request_id,
        user_id=event.user_id,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        warehouse_id=event.warehouse_id,
        payload=event.payload,
        created_at=event.created_at,
    )
