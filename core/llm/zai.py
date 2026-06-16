from __future__ import annotations

import logging

import httpx

from core.config import Settings
from core.config import settings as default_settings
from core.llm.base import LLMAuthError
from core.llm.openai_compat import DEFAULT_TIMEOUT_SEC, OpenAICompatProvider

logger = logging.getLogger(__name__)

ZAI_ENDPOINT = "https://api.z.ai/v1/chat/completions"


class ZAIProvider(OpenAICompatProvider):
    endpoint = ZAI_ENDPOINT

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        *,
        json_retries: int = 3,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        resolved_settings = settings or default_settings
        api_key = resolved_settings.zai_api_key
        if not api_key:
            raise LLMAuthError("ZAI_API_KEY is not set")
        super().__init__(
            settings=resolved_settings,
            client=client,
            api_key=api_key,
            json_retries=json_retries,
            timeout=timeout,
        )


__all__ = ["ZAIProvider", "ZAI_ENDPOINT"]
