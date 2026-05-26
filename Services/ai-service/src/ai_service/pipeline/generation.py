from __future__ import annotations

from dataclasses import dataclass

from ai_service.pipeline.providers import AIProvider
from ai_service.pipeline.retrieval import RetrievalPipeline


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
    ):
        self.provider = provider
        self.retrieval = retrieval or RetrievalPipeline()

    def answer(self, *, question: str, mode: str) -> QueryResult:
        context = self.retrieval.build_context(question=question, mode=mode)
        return self.provider.generate(question=context.query, mode=context.mode)

    def status(self) -> dict[str, object]:
        return self.provider.status()
