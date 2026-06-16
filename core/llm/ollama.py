from __future__ import annotations

import logging

import httpx

from core.config import Settings
from core.config import settings as default_settings
from core.llm.base import LLMProvider, LLMRequestError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        *,
        json_retries: int = 3,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self._settings = settings or default_settings
        self._base_url = (
            self._settings.ollama_base_url or DEFAULT_OLLAMA_BASE_URL
        )
        self._model = self._settings.llm.model
        self._temperature = self._settings.llm.temperature
        self._owns_client = client is None
        self._client = (
            client if client is not None else httpx.Client(timeout=timeout)
        )
        self._timeout = timeout
        self._json_retries = json_retries

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _chat_url(self) -> str:
        return f"{self._base_url.rstrip('/')}/api/chat"

    def _request_payload(self, messages: list[dict], **kw) -> dict:
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._temperature,
            },
        }
        payload.update(kw)
        return payload

    def complete(self, messages: list[dict], **kw) -> str:
        url = self._chat_url()
        payload = self._request_payload(messages, **kw)
        try:
            resp = self._client.post(
                url,
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMRequestError(
                f"ollama transport error: {exc!r}"
            ) from exc

        status = resp.status_code
        if status in (400, 404):
            raise LLMRequestError(f"ollama HTTP {status}")
        if status == 429 or 500 <= status < 600:
            raise LLMRequestError(f"ollama HTTP {status}")
        if status != 200:
            raise LLMRequestError(f"ollama HTTP {status}")

        try:
            body = resp.json()
        except (ValueError, TypeError) as exc:
            raise LLMRequestError(
                f"ollama non-JSON response: {exc!r}"
            ) from exc

        try:
            return body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMRequestError(
                f"ollama unexpected response structure: {exc!r}"
            ) from exc


__all__ = [
    "OllamaProvider",
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_TIMEOUT_SEC",
]
