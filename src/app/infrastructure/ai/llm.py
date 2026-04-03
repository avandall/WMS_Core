from __future__ import annotations

import os
from typing import Optional

from app.infrastructure.ai.settings import ai_engine_settings


def get_chat_model(*, temperature: Optional[float] = None):
    """Return a LangChain chat model based on `AI_PROVIDER` + `AI_MODEL`."""

    provider = ai_engine_settings.provider.strip().lower()
    model = ai_engine_settings.model
    effective_temperature = (
        ai_engine_settings.temperature if temperature is None else temperature
    )

    if provider == "groq":
        if not os.getenv("GROQ_API_KEY"):
            raise ValueError(
                "GROQ_API_KEY is not set. Set it in your environment or .env"
            )
        try:
            from langchain_groq import ChatGroq
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Missing dependency: `langchain-groq`.") from exc
        return ChatGroq(
            model=model,
            temperature=effective_temperature,
            max_tokens=ai_engine_settings.max_tokens,
        )

    if provider == "gemini":
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError(
                "GOOGLE_API_KEY is not set. Set it in your environment or .env"
            )
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Missing dependency: `langchain-google-genai`.") from exc
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=effective_temperature,
            max_tokens=ai_engine_settings.max_tokens,
        )

    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY is not set. Set it in your environment or .env"
            )
        try:
            from langchain_openai import ChatOpenAI
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Missing dependency: `langchain-openai`.") from exc
        return ChatOpenAI(
            model=model,
            temperature=effective_temperature,
            max_tokens=ai_engine_settings.max_tokens,
        )

    raise ValueError(f"Unsupported AI provider: {ai_engine_settings.provider!r}")

