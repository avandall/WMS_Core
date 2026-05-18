from __future__ import annotations

import json

import grpc

from ai_engine.core.engine import ProcessingMode, WMSEngine

from ai_service.gen.wms.ai.v1 import ai_pb2, ai_pb2_grpc


class AIServiceServicer(ai_pb2_grpc.AIServiceServicer):
    # Lazy init: engine may require API keys; keep process alive even if missing.
    _engine: WMSEngine | None = None

    @classmethod
    def _get_engine(cls) -> WMSEngine:
        if cls._engine is None:
            cls._engine = WMSEngine(mode=ProcessingMode.RAG)
        return cls._engine

    def Query(self, request: ai_pb2.QueryRequest, context: grpc.ServicerContext):
        mode = (request.mode or "rag").lower()
        try:
            engine = self._get_engine()
            pmode = ProcessingMode(mode) if mode in {"rag", "agent", "hybrid"} else ProcessingMode.RAG
            result = engine.process_query(request.question, mode=pmode)
            return ai_pb2.QueryResponse(
                success=bool(result.get("success", False)),
                mode=str(result.get("mode", "")),
                response=str(result.get("response", "")),
                error=str(result.get("error", "")),
            )
        except Exception as exc:
            return ai_pb2.QueryResponse(success=False, mode=mode, response="", error=str(exc))

    def Status(self, request: ai_pb2.StatusRequest, context: grpc.ServicerContext):
        try:
            engine = self._get_engine()
            info = engine.get_engine_info()
            return ai_pb2.StatusResponse(json=json.dumps(info, ensure_ascii=False, default=str))
        except Exception as exc:
            return ai_pb2.StatusResponse(json=json.dumps({"error": str(exc)}, ensure_ascii=False))


add_AIServiceServicer_to_server = ai_pb2_grpc.add_AIServiceServicer_to_server

