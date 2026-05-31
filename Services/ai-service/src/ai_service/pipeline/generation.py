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
from ai_service.pipeline.templates import QueryTemplateExtractor, SafeQueryTemplateExtractor


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
            backend_response = self.backend_query.execute(template=template)
            return QueryResult(
                success=backend_response.success,
                mode="data_query",
                response=render_backend_response(backend_response),
                error=backend_response.error,
            )

        context = self.retrieval.build_context(question=question, mode="rag")
        return self.provider.generate(question=context.query, mode=context.mode)

    def status(self) -> dict[str, object]:
        status = self.provider.status()
        status["query_router"] = self.router.__class__.__name__
        status["template_extractor"] = self.template_extractor.__class__.__name__
        status["backend_query"] = self.backend_query.__class__.__name__
        return status
