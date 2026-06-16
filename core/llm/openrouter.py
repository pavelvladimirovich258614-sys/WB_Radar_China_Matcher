from __future__ import annotations

import logging

import httpx

from core.config import Settings
from core.config import settings as default_settings
from core.llm.base import LLMAuthError, LLMProvider, LLMRequestError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 30.0
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(LLMProvider):
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        *,
        json_retries: int = 3,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self._settings = settings or default_settings
        self._api_key = self._settings.openrouter_api_key
        if not self._api_key:
            raise LLMAuthError("OPENROUTER_API_KEY is not set")
        self._owns_client = client is None
        self._client = (
            client if client is not None else httpx.Client(timeout=timeout)
        )
        self._timeout = timeout
        self._endpoint = OPENROUTER_ENDPOINT
        self._model = self._settings.llm.model
        self._temperature = self._settings.llm.temperature
        self._json_retries = json_retries

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def complete(self, messages: list[dict], **kw) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/local/wb-radar",
            "X-Title": "WB Radar",
        }
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        payload.update(kw)
        try:
            resp = self._client.post(
                self._endpoint,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"openrouter transport error: {exc!r}") from exc

        status = resp.status_code
        if status in (401, 403):
            raise LLMAuthError(f"openrouter HTTP {status}")
        if status == 429 or 500 <= status < 600:
            raise LLMRequestError(f"openrouter HTTP {status}")
        if status != 200:
            raise LLMRequestError(f"openrouter HTTP {status}")

        try:
            body = resp.json()
        except (ValueError, TypeError) as exc:
            raise LLMRequestError(
                f"openrouter non-JSON response: {exc!r}"
            ) from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRequestError(
                f"openrouter unexpected response structure: {exc!r}"
            ) from exc


__all__ = ["OpenRouterProvider", "OPENROUTER_ENDPOINT", "DEFAULT_TIMEOUT_SEC"]
