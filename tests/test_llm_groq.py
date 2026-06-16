from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from core.config import Settings
import core.llm as llm_pkg
from core.llm import get_provider
from core.llm import groq as groq_module
from core.llm.base import LLMAuthError, LLMError, LLMRequestError
from core.llm.groq import GROQ_ENDPOINT, GroqProvider
from tests.conftest import CONFIG_YAML, FakeClient, FakeResponse


def _settings_with_key(key: str = "sk-groq") -> Settings:
    s = Settings()
    s.groq_api_key = key
    return s


def test_complete_success_returns_content():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "hi"}}]})]
    )
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    assert p.complete([{"role": "user", "content": "q"}]) == "hi"


def test_complete_correct_url():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    p.complete([{"role": "user", "content": "q"}])
    assert fake.calls[0][0] == GROQ_ENDPOINT


def test_complete_payload_model_messages_temperature():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    s = _settings_with_key()
    p = GroqProvider(settings=s, client=fake)
    p.complete([{"role": "user", "content": "q"}])
    payload = fake.calls[0][2]
    assert payload["model"] == s.llm.model
    assert payload["messages"] == [{"role": "user", "content": "q"}]
    assert payload["temperature"] == s.llm.temperature


def test_complete_authorization_header():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    p = GroqProvider(settings=_settings_with_key("sk-test"), client=fake)
    p.complete([{"role": "user", "content": "q"}])
    headers = fake.calls[0][1]
    assert headers["Authorization"] == "Bearer sk-test"


def test_complete_forwards_max_tokens_kwarg():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    p.complete([{"role": "user", "content": "q"}], max_tokens=16)
    payload = fake.calls[0][2]
    assert payload["max_tokens"] == 16


def test_key_from_settings_not_config_yaml():
    s = Settings()
    s.groq_api_key = "sk-from-settings"
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    p = GroqProvider(settings=s, client=fake)
    p.complete([{"role": "user", "content": "q"}])
    headers = fake.calls[0][1]
    assert headers["Authorization"] == "Bearer sk-from-settings"
    config_text = CONFIG_YAML.read_text(encoding="utf-8").lower()
    assert "api_key" not in config_text


def test_missing_key_raises_auth_error():
    s = Settings()
    s.groq_api_key = None
    with pytest.raises(LLMAuthError):
        GroqProvider(settings=s)


def test_401_raises_auth_error():
    fake = FakeClient([FakeResponse(401)])
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMAuthError):
        p.complete([{"role": "user", "content": "q"}])


def test_403_raises_auth_error():
    fake = FakeClient([FakeResponse(403)])
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMAuthError):
        p.complete([{"role": "user", "content": "q"}])


def test_429_raises_request_error():
    fake = FakeClient([FakeResponse(429)])
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_500_raises_request_error():
    fake = FakeClient([FakeResponse(500)])
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_other_non_200_raises_request_error():
    fake = FakeClient([FakeResponse(418)])
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_transport_error_raises_request_error():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    fake.raise_on_post = httpx.ConnectError("boom")
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_broken_choices_structure_raises_request_error():
    fake = FakeClient([FakeResponse(200, {"choices": []})])
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_missing_choices_raises_request_error():
    fake = FakeClient([FakeResponse(200, {"nope": 1})])
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_non_json_body_raises_request_error():
    fake = FakeClient([FakeResponse(200, raise_json=True)])
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_key_not_in_exception_message():
    fake = FakeClient([FakeResponse(401)])
    p = GroqProvider(settings=_settings_with_key("sk-test"), client=fake)
    with pytest.raises(LLMAuthError) as excinfo:
        p.complete([{"role": "user", "content": "q"}])
    assert "sk-test" not in str(excinfo.value)


def test_close_does_not_close_injected_client():
    fake = FakeClient(
        [FakeResponse(200, {"choices": [{"message": {"content": "x"}}]})]
    )
    with GroqProvider(settings=_settings_with_key(), client=fake) as p:
        pass
    assert fake.closed is False


def test_complete_json_via_inherited_groq():
    fake = FakeClient(
        [
            FakeResponse(
                200,
                {
                    "choices": [
                        {"message": {"content": "```json\n{\"ok\": true}\n```"}}
                    ]
                },
            )
        ]
    )
    p = GroqProvider(settings=_settings_with_key(), client=fake)
    assert p.complete_json([{"role": "user", "content": "q"}]) == {"ok": True}


def _patch_key(monkeypatch, key: str = "sk-groq"):
    monkeypatch.setattr(llm_pkg.default_settings, "groq_api_key", key)
    monkeypatch.setattr(groq_module.default_settings, "groq_api_key", key)


def test_get_provider_groq_returns_instance(monkeypatch):
    _patch_key(monkeypatch)
    assert isinstance(get_provider("groq"), GroqProvider)


def test_get_provider_groq_alias_not_different_provider():
    # groq has no alias, just sanity: unknown still errors without key
    with pytest.raises(LLMError):
        get_provider("groq-unknown")


@pytest.mark.live
def test_groq_complete_live():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        pytest.skip("GROQ_API_KEY is not set")
    with GroqProvider() as p:
        text = p.complete([{"role": "user", "content": "Reply with the single word: OK"}])
    assert isinstance(text, str) and text.strip()
