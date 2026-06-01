from __future__ import annotations

import json

import grpc

from app.modules.audit.infrastructure.repositories.audit_event_repo import AuditEventRepo
from app.shared.core.database import get_session

from audit_service.gen.wms.audit.v1 import audit_pb2, audit_pb2_grpc


class AuditServiceServicer(audit_pb2_grpc.AuditServiceServicer):
    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "x-request-id":
                return v
        return None

    def _repo(self) -> tuple[AuditEventRepo, object]:
        session_gen = get_session()
        db = next(session_gen)
        return AuditEventRepo(db), db

    @staticmethod
    def _to_proto(e) -> audit_pb2.AuditEvent:  # type: ignore[no-untyped-def]
        payload = getattr(e, "payload", None)
        try:
            payload_json = json.dumps(payload, ensure_ascii=False) if payload is not None else ""
        except Exception:
            payload_json = ""
        return audit_pb2.AuditEvent(
            id=int(getattr(e, "id", 0) or 0),
            request_id=str(getattr(e, "request_id", "") or ""),
            user_id=int(getattr(e, "user_id", 0) or 0),
            action=str(getattr(e, "action", "") or ""),
            entity_type=str(getattr(e, "entity_type", "") or ""),
            entity_id=str(getattr(e, "entity_id", "") or ""),
            warehouse_id=int(getattr(e, "warehouse_id", 0) or 0),
            payload_json=payload_json,
            created_at=str(getattr(e, "created_at", "") or ""),
        )

    def ListEvents(self, request: audit_pb2.ListEventsRequest, context: grpc.ServicerContext):
        repo, db = self._repo()
        try:
            _ = self._request_id(context)  # reserved for future structured logs
            events = repo.list_events(
                request_id=request.request_id or None,
                user_id=int(request.user_id) if request.user_id else None,
                action=request.action or None,
                entity_type=request.entity_type or None,
                entity_id=request.entity_id or None,
                warehouse_id=int(request.warehouse_id) if request.warehouse_id else None,
                created_from=None,
                created_to=None,
                limit=int(request.limit) if request.limit else 100,
                offset=int(request.offset) if request.offset else 0,
            )
            return audit_pb2.ListEventsResponse(events=[self._to_proto(e) for e in events])
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetEvent(self, request: audit_pb2.GetEventRequest, context: grpc.ServicerContext):
        repo, db = self._repo()
        try:
            _ = self._request_id(context)
            event = repo.get(int(request.id))
            if not event:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Audit event not found")
                return audit_pb2.AuditEvent()
            return self._to_proto(event)
        finally:
            try:
                db.close()
            except Exception:
                pass


add_AuditServiceServicer_to_server = audit_pb2_grpc.add_AuditServiceServicer_to_server
