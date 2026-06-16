from __future__ import annotations

import os

import httpx
import pytest

from core.config import Settings
import core.llm as llm_pkg
from core.llm import get_provider
from core.llm import ollama as ollama_module
from core.llm.base import LLMError, LLMRequestError
from core.llm.ollama import DEFAULT_OLLAMA_BASE_URL, OllamaProvider
from tests.conftest import FakeClient, FakeResponse


def _settings_with_url(base_url: str | None = "http://localhost:11434") -> Settings:
    s = Settings()
    s.ollama_base_url = base_url
    return s


def test_complete_success_returns_content():
    fake = FakeClient(
        [FakeResponse(200, {"message": {"content": "hello"}})]
    )
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    assert p.complete([{"role": "user", "content": "q"}]) == "hello"


def test_complete_correct_url():
    fake = FakeClient(
        [FakeResponse(200, {"message": {"content": "x"}})]
    )
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    p.complete([{"role": "user", "content": "q"}])
    assert fake.calls[0][0] == "http://localhost:11434/api/chat"


def test_complete_payload_model_messages_stream_options():
    fake = FakeClient(
        [FakeResponse(200, {"message": {"content": "x"}})]
    )
    s = _settings_with_url()
    p = OllamaProvider(settings=s, client=fake)
    p.complete([{"role": "user", "content": "q"}])
    payload = fake.calls[0][2]
    assert payload["model"] == s.llm.model
    assert payload["messages"] == [{"role": "user", "content": "q"}]
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == s.llm.temperature


def test_complete_uses_custom_base_url():
    fake = FakeClient(
        [FakeResponse(200, {"message": {"content": "x"}})]
    )
    p = OllamaProvider(
        settings=_settings_with_url("http://ollama.local:11434"),
        client=fake,
    )
    p.complete([{"role": "user", "content": "q"}])
    assert fake.calls[0][0] == "http://ollama.local:11434/api/chat"


def test_default_base_url_when_settings_none():
    s = Settings()
    s.ollama_base_url = None
    fake = FakeClient([FakeResponse(200, {"message": {"content": "x"}})])
    p = OllamaProvider(settings=s, client=fake)
    p.complete([{"role": "user", "content": "q"}])
    assert fake.calls[0][0] == DEFAULT_OLLAMA_BASE_URL + "/api/chat"


def test_complete_forwards_max_tokens_kwarg():
    fake = FakeClient(
        [FakeResponse(200, {"message": {"content": "x"}})]
    )
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    p.complete([{"role": "user", "content": "q"}], max_tokens=16)
    payload = fake.calls[0][2]
    assert payload["max_tokens"] == 16


def test_400_raises_request_error():
    fake = FakeClient([FakeResponse(400)])
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_404_raises_request_error():
    fake = FakeClient([FakeResponse(404)])
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_429_raises_request_error():
    fake = FakeClient([FakeResponse(429)])
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_500_raises_request_error():
    fake = FakeClient([FakeResponse(500)])
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_other_non_200_raises_request_error():
    fake = FakeClient([FakeResponse(418)])
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_transport_error_raises_request_error():
    fake = FakeClient(
        [FakeResponse(200, {"message": {"content": "x"}})]
    )
    fake.raise_on_post = httpx.ConnectError("boom")
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_broken_message_structure_raises_request_error():
    fake = FakeClient([FakeResponse(200, {"message": {}})])
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_missing_message_raises_request_error():
    fake = FakeClient([FakeResponse(200, {"nope": 1})])
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_non_json_body_raises_request_error():
    fake = FakeClient([FakeResponse(200, raise_json=True)])
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    with pytest.raises(LLMRequestError):
        p.complete([{"role": "user", "content": "q"}])


def test_close_does_not_close_injected_client():
    fake = FakeClient(
        [FakeResponse(200, {"message": {"content": "x"}})]
    )
    with OllamaProvider(settings=_settings_with_url(), client=fake) as p:
        pass
    assert fake.closed is False


def test_complete_json_via_inherited_ollama():
    fake = FakeClient(
        [
            FakeResponse(
                200,
                {"message": {"content": "```json\n{\"ok\": true}\n```"}},
            )
        ]
    )
    p = OllamaProvider(settings=_settings_with_url(), client=fake)
    assert p.complete_json([{"role": "user", "content": "q"}]) == {"ok": True}


def _patch_url(monkeypatch, base_url: str = "http://localhost:11434"):
    monkeypatch.setattr(
        llm_pkg.default_settings, "ollama_base_url", base_url
    )
    monkeypatch.setattr(
        ollama_module.default_settings, "ollama_base_url", base_url
    )


def test_get_provider_ollama_returns_instance(monkeypatch):
    _patch_url(monkeypatch)
    assert isinstance(get_provider("ollama"), OllamaProvider)


def test_get_provider_unknown_raises_llm_error():
    with pytest.raises(LLMError):
        get_provider("unknown-provider")


@pytest.mark.live
def test_ollama_complete_live():
    base_url = os.environ.get("OLLAMA_BASE_URL")
    if not base_url:
        base_url = "http://localhost:11434"
    try:
        import urllib.request
        urllib.request.urlopen(base_url, timeout=2)
    except Exception:
        pytest.skip(f"Ollama is not reachable at {base_url}")
    with OllamaProvider() as p:
        text = p.complete([{"role": "user", "content": "Reply with the single word: OK"}])
    assert isinstance(text, str) and text.strip()
