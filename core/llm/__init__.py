from __future__ import annotations

from core.config import settings as default_settings
from core.llm.base import (
    LLMAuthError,
    LLMError,
    LLMJSONError,
    LLMProvider,
    LLMRequestError,
)
from core.llm.groq import GroqProvider
from core.llm.ollama import OllamaProvider
from core.llm.openrouter import OpenRouterProvider
from core.llm.zai import ZAIProvider


def get_provider(name: str | None = None) -> LLMProvider:
    if name is None:
        name = default_settings.llm.provider
    normalized = str(name).strip().lower()
    if normalized == "openrouter":
        return OpenRouterProvider()
    if normalized in ("zai", "z.ai", "glm"):
        return ZAIProvider()
    if normalized == "groq":
        return GroqProvider()
    if normalized == "ollama":
        return OllamaProvider()
    raise LLMError(f"unknown LLM provider: {name!r}")


__all__ = [
    "get_provider",
    "LLMProvider",
    "LLMError",
    "LLMAuthError",
    "LLMRequestError",
    "LLMJSONError",
    "OpenRouterProvider",
    "ZAIProvider",
    "GroqProvider",
    "OllamaProvider",
]
