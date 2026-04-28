from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth_deps import get_current_user, require_permissions
from app.application.dtos.ai import ChatDBRequest, ChatDBResponse
from app.shared.core.permissions import Permission
from app.integrations.ai.chains import handle_customer_chat_with_db
from fastapi.concurrency import run_in_threadpool

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post(
    "/ai/chat-db",
    response_model=ChatDBResponse,
    dependencies=[Depends(require_permissions(Permission.VIEW_REPORTS))],
)
async def chat_db(payload: ChatDBRequest):
    import time
    start_time = time.time()
    
    try:
        # Enhanced processing with mode support
        result = await run_in_threadpool(handle_customer_chat_with_db, payload.message, payload.mode)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Prepare response with enhanced metadata
        response_data = {
            "answer": result.get("answer", ""),
            "sql": result.get("sql", ""),
            "rows": result.get("rows", None) if payload.include_rows else None,
            "mode": result.get("mode", "unknown"),
            "engine_info": result.get("engine_info"),
            "processing_time": processing_time
        }
        
        return ChatDBResponse(**response_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        detail = str(exc) or type(exc).__name__
        raise HTTPException(
            status_code=502,
            detail=f"AI engine error ({type(exc).__name__}): {detail}",
        )

