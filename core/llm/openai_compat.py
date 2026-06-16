from __future__ import annotations

import logging

import httpx

from core.config import Settings
from core.llm.base import LLMAuthError, LLMProvider, LLMRequestError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 30.0


class OpenAICompatProvider(LLMProvider):
    """Shared OpenAI-compatible chat-completion transport.

    Subclasses only define ``endpoint`` and how the API key is obtained.
    """

    endpoint: str = ""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        *,
        api_key: str | None = None,
        json_retries: int = 3,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self._settings = settings
        self._api_key = api_key
        self._owns_client = client is None
        self._client = (
            client if client is not None else httpx.Client(timeout=timeout)
        )
        self._timeout = timeout
        self._json_retries = json_retries
        self._model = self._settings.llm.model if self._settings else None
        self._temperature = (
            self._settings.llm.temperature if self._settings else None
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _request_payload(self, messages: list[dict], **kw) -> dict:
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        payload.update(kw)
        return payload

    def complete(self, messages: list[dict], **kw) -> str:
        if not self._api_key:
            raise LLMAuthError("API key is not set")

        headers = self._request_headers()
        payload = self._request_payload(messages, **kw)
        try:
            resp = self._client.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMRequestError(
                f"{self.provider_name} transport error: {exc!r}"
            ) from exc

        status = resp.status_code
        if status in (401, 403):
            raise LLMAuthError(f"{self.provider_name} HTTP {status}")
        if status == 429 or 500 <= status < 600:
            raise LLMRequestError(f"{self.provider_name} HTTP {status}")
        if status != 200:
            raise LLMRequestError(f"{self.provider_name} HTTP {status}")

        try:
            body = resp.json()
        except (ValueError, TypeError) as exc:
            raise LLMRequestError(
                f"{self.provider_name} non-JSON response: {exc!r}"
            ) from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRequestError(
                f"{self.provider_name} unexpected response structure: {exc!r}"
            ) from exc

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__.removesuffix("Provider").lower()


__all__ = ["OpenAICompatProvider", "DEFAULT_TIMEOUT_SEC"]
