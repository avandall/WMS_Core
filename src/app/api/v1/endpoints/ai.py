from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth_deps import get_current_user, require_permissions
from app.application.dtos.ai import ChatDBRequest, ChatDBResponse
from app.core.permissions import Permission
from app.infrastructure.ai import handle_customer_chat_with_db
from fastapi.concurrency import run_in_threadpool

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post(
    "/ai/chat-db",
    response_model=ChatDBResponse,
    dependencies=[Depends(require_permissions(Permission.VIEW_REPORTS))],
)
async def chat_db(payload: ChatDBRequest):
    try:
        result = await run_in_threadpool(handle_customer_chat_with_db, payload.message)
        if not payload.include_rows:
            result["rows"] = None
        return ChatDBResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        detail = str(exc) or type(exc).__name__
        raise HTTPException(
            status_code=502,
            detail=f"AI engine error ({type(exc).__name__}): {detail}",
        )

