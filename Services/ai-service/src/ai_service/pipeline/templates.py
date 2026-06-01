from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class QueryTemplate:
    intent: str
    target: str
    filters: dict[str, Any]
    metrics: tuple[str, ...] = ()
    limit: int | None = None
    raw_question: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class QueryTemplateExtractor(Protocol):
    def extract(self, *, question: str) -> QueryTemplate: ...


class GroqQueryTemplateExtractor:
    """
    Default template extractor backed by Groq.

    This is intentionally behind a small object boundary so it can be replaced
    with a local model later without changing AIQueryPipeline.
    """

    def __init__(self):
        from ai_engine.config import settings
        from langchain_groq import ChatGroq

        self.llm = ChatGroq(**settings.get_llm_config())

    def extract(self, *, question: str) -> QueryTemplate:
        from langchain_core.messages import HumanMessage

        prompt = f"""Extract a backend query template for a WMS question.

Return only valid JSON with this shape:
{{
  "intent": "inventory_lookup|order_status|report_lookup|unknown",
  "target": "inventory|orders|reporting|unknown",
  "filters": {{"key": "value"}},
  "metrics": ["quantity"],
  "limit": 20
}}

Question: {question}
"""
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return self._parse(question=question, content=response.content)

    def _parse(self, *, question: str, content: str) -> QueryTemplate:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            payload = json.loads(match.group(0)) if match else {}
        return _template_from_payload(question=question, payload=payload)


class HeuristicQueryTemplateExtractor:
    """Fallback extractor used when the Groq extractor cannot produce a template."""

    _sku_pattern = re.compile(r"\b([A-Z]{2,}-\d{2,})\b")

    def extract(self, *, question: str) -> QueryTemplate:
        sku = self._sku_pattern.search(question)
        filters: dict[str, Any] = {}
        if sku:
            filters["sku"] = sku.group(1)
        return QueryTemplate(
            intent="inventory_lookup" if filters else "unknown",
            target="inventory" if filters else "unknown",
            filters=filters,
            metrics=("quantity", "location") if filters else (),
            raw_question=question,
        )


class SafeQueryTemplateExtractor:
    def __init__(self, primary: QueryTemplateExtractor | None = None, fallback: QueryTemplateExtractor | None = None):
        self.primary = primary or GroqQueryTemplateExtractor()
        self.fallback = fallback or HeuristicQueryTemplateExtractor()

    def extract(self, *, question: str) -> QueryTemplate:
        try:
            template = self.primary.extract(question=question)
            if template.intent != "unknown" or template.filters:
                return template
        except Exception:
            pass
        return self.fallback.extract(question=question)


def _template_from_payload(*, question: str, payload: dict[str, Any]) -> QueryTemplate:
    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), list) else []
    limit = payload.get("limit")
    return QueryTemplate(
        intent=str(payload.get("intent") or "unknown"),
        target=str(payload.get("target") or "unknown"),
        filters=filters,
        metrics=tuple(str(metric) for metric in metrics),
        limit=int(limit) if isinstance(limit, int) else None,
        raw_question=question,
    )
