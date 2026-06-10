from __future__ import annotations

from dataclasses import dataclass

from ai_service.pipeline.backend_query import (
    BackendQueryClient,
    default_backend_query_client,
    render_backend_response,
)
from ai_service.pipeline.providers import AIProvider
from ai_service.pipeline.retrieval import RetrievalPipeline
from ai_service.pipeline.routing import HeuristicQueryRouter, QueryRouter
from ai_service.pipeline.templates import (
    QueryTemplateExtractor,
    SafeQueryTemplateExtractor,
    extractor_source,
)


@dataclass(frozen=True, slots=True)
class QueryResult:
    success: bool
    mode: str
    response: str
    error: str = ""


class AIQueryPipeline:
    def __init__(
        self,
        *,
        provider: AIProvider,
        retrieval: RetrievalPipeline | None = None,
        router: QueryRouter | None = None,
        template_extractor: QueryTemplateExtractor | None = None,
        backend_query: BackendQueryClient | None = None,
    ):
        self.provider = provider
        self.retrieval = retrieval or RetrievalPipeline()
        self.router = router or HeuristicQueryRouter()
        self.template_extractor = template_extractor or SafeQueryTemplateExtractor()
        self.backend_query = backend_query or default_backend_query_client()

    def answer(self, *, question: str, mode: str) -> QueryResult:
        decision = self.router.route(question=question, requested_mode=mode)
        if decision.route == "data_query":
            template = self.template_extractor.extract(question=question)
            # Unknown intent with no filters = conversational question, answer with Groq directly
            if template.intent == "unknown" and not template.filters:
                return self._groq_chat(question)
            backend_response = self.backend_query.execute(template=template)
            return QueryResult(
                success=backend_response.success,
                mode="data_query",
                response=render_backend_response(backend_response),
                error=backend_response.error,
            )

        context = self.retrieval.build_context(question=question, mode="rag")
        return self.provider.generate(question=context.query, mode=context.mode)

    def _groq_chat(self, question: str) -> QueryResult:
        try:
            from ai_engine.config import settings
            from langchain_groq import ChatGroq
            from langchain_core.messages import HumanMessage, SystemMessage
            llm = ChatGroq(model=settings.LLM_MODEL, temperature=0.7)
            response = llm.invoke([
                SystemMessage(content=(
                    "You are a helpful WMS (Warehouse Management System) assistant. "
                    "You help users with questions about inventory, products, warehouses, "
                    "documents, customers, and sales. Be concise and helpful."
                )),
                HumanMessage(content=question),
            ])
            return QueryResult(success=True, mode="chat", response=str(response.content))
        except Exception as exc:
            return QueryResult(success=False, mode="chat", response="", error=str(exc))

    def status(self) -> dict[str, object]:
        status = self.provider.status()
        status["query_router"] = self.router.__class__.__name__
        status["template_extractor"] = self.template_extractor.__class__.__name__
        status["template_extractor_source"] = extractor_source(self.template_extractor)
        status["fine_tuned_template_extractor_enabled"] = (
            extractor_source(self.template_extractor) == "fine_tuned"
        )
        status["backend_query"] = self.backend_query.__class__.__name__
        return status
