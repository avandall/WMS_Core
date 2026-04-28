from __future__ import annotations

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class AIEngineSettings(BaseSettings):
    """Settings for the AI engine.

Values load from `.env` (and `../.env`) with the `AI_` prefix.
Example:
  AI_PROVIDER=groq
  AI_MODEL=llama-3.1-8b-instant
"""

    provider: str = "groq"  # groq | gemini | openai
    model: str = "llama-3.1-8b-instant"
    temperature: float = 0.0
    max_tokens: int | None = None

    db_max_rows: int = 50

    model_config = ConfigDict(
        env_prefix="AI_",
        env_file=(".env", "../.env"),
        case_sensitive=False,
        extra="ignore",
    )


ai_engine_settings = AIEngineSettings()

