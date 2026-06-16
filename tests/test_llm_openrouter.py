from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from core.config import Settings
import core.llm as llm_pkg
from core.llm import get_provider
from core.llm import openrouter as openrouter_module
from core.llm.base import (
    LLMAuthError,
    LLMError,
    LLMJSONError,
    LLMRequestError,
)
from core.llm.openrouter import (
    DEFAULT_TIMEOUT_SEC,
    OPENROUTER_ENDPOINT,
    OpenRouterProvider,
)


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload=None,
        *,
        text=None,
        raise_json: bool = False,
    ):
        self.status_code = status_code
        self._payload = payload
        self._text = text
        self._raise_json = raise_json

    def json(self):
        if self._raise_json or self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self._i = 0
        self.calls = []  # list of (url, headers, payload)
        self.closed = False
        self.raise_on_post = None  # an exception to raise from post(), if set

    def post(self, url, *, headers=None, json=None, timeout=None):
        if self.raise_on_post is not None:
            raise self.raise_on_post
        self.calls.append((url, dict(headers or {}), dict(json or {})))
        resp = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return resp

    def close(self):
        self.closed = True


CONFIG_YAML = Path(__file__).resolve().parent.parent / "config.yaml"


def _settings_with_key(key: str = "sk-test") -> Settings:
    s = Settings()
    s.openrouter_api_key = key
    return s


def test_complete_success_returns_content():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "hello"}}]})]
    )
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    assert p.complete([{"role": "user", "content": "hi"}]) == "hello"


def test_complete_correct_url():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    p.complete([{"role": "user", "content": "hi"}])
    assert fake.calls[0][0] == OPENROUTER_ENDPOINT


def test_complete_payload_model_messages_temperature():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    s = _settings_with_key()
    p = OpenRouterProvider(settings=s, client=fake)
    p.complete([{"role": "user", "content": "hi"}])
    payload = fake.calls[0][2]
    assert payload["model"] == s.llm.model
    assert "messages" in payload
    assert payload["temperature"] == s.llm.temperature


def test_complete_authorization_header():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    p = OpenRouterProvider(settings=_settings_with_key("sk-test"), client=fake)
    p.complete([{"role": "user", "content": "hi"}])
    headers = fake.calls[0][1]
    assert headers["Authorization"] == "Bearer sk-test"
    assert "sk-test" in headers["Authorization"]


def test_complete_forwards_max_tokens_kwarg():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    p.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    payload = fake.calls[0][2]
    assert payload["max_tokens"] == 16


def test_key_from_settings_not_config_yaml():
    s = Settings()
    s.openrouter_api_key = "sk-from-settings"
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    p = OpenRouterProvider(settings=s, client=fake)
    p.complete([{"role": "user", "content": "hi"}])
    headers = fake.calls[0][1]
    assert headers["Authorization"] == "Bearer sk-from-settings"

    # config.yaml must never contain an api_key entry — secrets stay in .env
    config_text = CONFIG_YAML.read_text(encoding="utf-8").lower()
    assert "api_key" not in config_text


def test_missing_key_raises_auth_error():
    s = Settings()
    s.openrouter_api_key = None
    with pytest.raises(LLMAuthError):
        OpenRouterProvider(settings=s)


def test_401_raises_auth_error():
    fake = FakeClient([FakeResponse(401)])
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMAuthError):
        p.complete([{"role": "user", "content": "hi"}])


def test_403_raises_auth_error():
    fake = FakeClient([FakeResponse(403)])
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMAuthError):
        p.complete([{"role": "user", "content": "hi"}])


def test_429_raises_request_error():
    fake = FakeClient([FakeResponse(429)])
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "hi"}])


def test_500_raises_request_error():
    fake = FakeClient([FakeResponse(500)])
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "hi"}])


def test_other_non_200_raises_request_error():
    fake = FakeClient([FakeResponse(418)])
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "hi"}])


def test_transport_error_raises_request_error():
    fake = FakeClient([FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})])
    fake.raise_on_post = httpx.ConnectError("boom")
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "hi"}])


def test_broken_choices_structure_raises_request_error():
    fake = FakeClient([FakeResponse(200, {"choices": []})])
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "hi"}])


def test_missing_choices_raises_request_error():
    fake = FakeClient([FakeResponse(200, {"nope": 1})])
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "hi"}])


def test_non_json_body_raises_request_error():
    fake = FakeClient([FakeResponse(200, raise_json=True)])
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "hi"}])


def test_key_not_in_exception_message():
    fake = FakeClient([FakeResponse(401)])
    p = OpenRouterProvider(settings=_settings_with_key("sk-test"), client=fake)
    with pytest.raises(LLMAuthError) as excinfo:
        p.complete([{"role": "user", "content": "hi"}])
    assert "sk-test" not in str(excinfo.value)


def test_close_does_not_close_injected_client():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    with OpenRouterProvider(settings=_settings_with_key(), client=fake) as p:
        pass
    assert fake.closed is False


def test_json_retries_default_is_three():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "{}"}}]})]
    )
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    assert p._json_retries == 3


def test_complete_json_via_inherited_openrouter():
    fake = FakeClient(
        [
            FakeResponse(
                200,
                {
                    "choices": [
                        {"message": {"content": "```json\n{\"answer\": 42}\n```"}}
                    ]
                },
            )
        ]
    )
    p = OpenRouterProvider(settings=_settings_with_key(), client=fake)
    assert p.complete_json([{"role": "user", "content": "q"}]) == {"answer": 42}


def _patch_keys(monkeypatch, key: str = "sk-test"):
    # get_provider reads core.llm.default_settings (imported into __init__.py)
    monkeypatch.setattr(
        llm_pkg.default_settings,
        "openrouter_api_key",
        key,
    )
    # OpenRouterProvider() reads core.llm.openrouter.default_settings
    monkeypatch.setattr(
        openrouter_module.default_settings,
        "openrouter_api_key",
        key,
    )


def test_get_provider_openrouter_returns_instance(monkeypatch):
    _patch_keys(monkeypatch)
    assert isinstance(get_provider("openrouter"), OpenRouterProvider)


def test_get_provider_none_uses_config_default(monkeypatch):
    _patch_keys(monkeypatch)
    # config.yaml llm.provider == "openrouter"
    assert isinstance(get_provider(None), OpenRouterProvider)


def test_get_provider_unknown_raises_llm_error():
    with pytest.raises(LLMError):
        get_provider("zai")
    with pytest.raises(LLMError):
        get_provider("groq")


@pytest.mark.live
def test_openrouter_complete_live():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("OPENROUTER_API_KEY is not set")
    with OpenRouterProvider() as p:
        text = p.complete([{"role": "user", "content": "Reply with the single word: OK"}])
    assert isinstance(text, str) and text.strip()
