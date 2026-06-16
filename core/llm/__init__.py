from __future__ import annotations

from core.config import settings as default_settings
from core.llm.base import (
    LLMAuthError,
    LLMError,
    LLMJSONError,
    LLMProvider,
    LLMRequestError,
)
from core.llm.openrouter import OpenRouterProvider


def get_provider(name: str | None = None) -> LLMProvider:
    if name is None:
        name = default_settings.llm.provider
    normalized = str(name).strip().lower()
    if normalized == "openrouter":
        return OpenRouterProvider()
    raise LLMError(f"unknown LLM provider: {name!r} (not implemented yet)")


__all__ = [
    "get_provider",
    "LLMProvider",
    "LLMError",
    "LLMAuthError",
    "LLMRequestError",
    "LLMJSONError",
    "OpenRouterProvider",
]
