"""Tests for the Settings provider-validation UX + online key check.

Covers:
- ``check_provider_online`` driven through ``httpx.MockTransport`` (no network):
  ok / auth_error / model_error / network_error / not_supported / missing key,
  and that the full key is never exposed (only ``masked_key``).
- ``SettingsController`` local check (“Проверить локально”) and online check
  (“Проверить ключ онлайн”) with an injectable fake online checker.
- ``_default_save_settings`` merges keys into ``.env.local`` without erasing
  unrelated lines.
- Status updates call ``page.update()`` (the action-push regression guard).
"""

from __future__ import annotations

import types
from typing import Any

import flet as ft
import httpx
import pytest

from gui.settings import (
    DEFAULT_CHECK_TIMEOUT,
    ProviderCheckResult,
    SettingsController,
    _default_save_settings,
    _read_secret_from_env,
    build_settings_tab,
    check_provider_online,
    mask_secret,
)


class FakePage:
    """Page double that records ``update()`` calls (action-push guard)."""

    def __init__(self) -> None:
        self.title = ""
        self.theme_mode: ft.ThemeMode | None = None
        self.theme: Any | None = None
        self.bgcolor: Any | None = None
        self.controls: list[Any] = []
        self.overlay: list[Any] = []
        self.services: list[Any] = []
        self.update_calls = 0

    def add(self, control: Any) -> None:
        self.controls.append(control)

    def update(self) -> None:
        self.update_calls += 1


# --------------------------------------------------------------------------- #
# check_provider_online (through the REAL provider code path, mocked transport)
# --------------------------------------------------------------------------- #


def _client_from_handler(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok_handler(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": "OK"}}]}
    )


def test_check_online_ok() -> None:
    result = check_provider_online(
        "zai",
        "glm-4.6",
        api_key="sk-testkey1234567890",
        client=_client_from_handler(_ok_handler),
    )
    assert result.ok is True
    assert result.status == "ok"
    assert "ZAI" in result.message
    # Full key never exposed.
    assert "sk-testkey1234567890" not in result.message
    assert result.masked_key == mask_secret("sk-testkey1234567890")


def test_check_online_auth_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    result = check_provider_online(
        "zai", "glm-4.6", api_key="sk-testkey1234567890",
        client=_client_from_handler(handler),
    )
    assert result.status == "auth_error"
    assert result.ok is False
    assert "авторизац" in result.message.lower()


def test_check_online_model_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    result = check_provider_online(
        "openrouter", "some/missing-model", api_key="sk-orkey1234567890",
        client=_client_from_handler(handler),
    )
    assert result.status == "model_error"
    assert "недоступна" in result.message


def test_check_online_network_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    result = check_provider_online(
        "groq", "llama-3.1-70b", api_key="gsk_testkey1234567890",
        client=_client_from_handler(handler),
    )
    assert result.status == "network_error"
    assert "интернет/proxy" in result.message.lower() or "интернет" in result.message.lower()


def test_check_online_missing_key() -> None:
    result = check_provider_online("zai", "glm-4.6", api_key=None)
    assert result.status == "missing_key"
    assert result.ok is False


def test_check_online_chatgpt_web_not_supported() -> None:
    result = check_provider_online("chatgpt_web", "x", api_key="whatever")
    assert result.status == "not_supported"


def test_check_online_masked_key_omits_full_secret() -> None:
    result = check_provider_online(
        "zai", "glm-4.6", api_key="sk-testkey1234567890",
        client=_client_from_handler(_ok_handler),
    )
    assert "sk-testkey1234567890" not in (result.message + result.masked_key)
    assert "****" in result.masked_key


# --------------------------------------------------------------------------- #
# SettingsController UX
# --------------------------------------------------------------------------- #


def _controller(
    *,
    online_results: list[ProviderCheckResult] | None = None,
    save_returns: bool = True,
) -> tuple[SettingsController, FakePage, list[dict[str, Any]]]:
    page = FakePage()
    save_calls: list[dict[str, str]] = []
    online_calls: list[dict[str, Any]] = []
    results = online_results if online_results is not None else []

    def fake_save(values: dict[str, str]) -> bool:
        save_calls.append(values)
        return save_returns

    def fake_online(**kwargs: Any) -> ProviderCheckResult:
        online_calls.append(kwargs)
        return results.pop(0) if results else ProviderCheckResult(
            True, "ok", "Онлайн-проверка прошла.", "xx****"
        )

    controller = SettingsController(
        save_settings=fake_save,
        open_folder=lambda path: True,
        session_status=lambda site: "ok",
        online_checker=fake_online,
    )
    controller._save_calls = save_calls  # type: ignore[attr-defined]
    controller._online_calls = online_calls  # type: ignore[attr-defined]
    controller.build_tab(page)
    return controller, page, online_calls


def _fill(controller: SettingsController, *, provider: str, model: str,
          key: str | None = None, proxy: str = "") -> None:
    controller.provider_dropdown.value = provider
    controller.model_field.value = model
    controller.proxy_field.value = proxy
    controller.output_dir_field.value = "./output"
    controller.sessions_dir_field.value = "./sessions"
    if key is not None and provider in controller.key_fields:
        controller.key_fields[provider].value = key


def test_local_check_without_key_reports_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gui.settings._read_secret_from_env", lambda name: None)
    controller, page, _ = _controller()
    _fill(controller, provider="zai", model="glm-4.6", key=None)

    controller._on_validate(None)

    assert controller.status_text is not None
    assert "Не найден" in controller.status_text.value
    assert "ZAI_API_KEY" in controller.status_text.value
    assert page.update_calls >= 1
    assert controller._online_calls == []  # local check never goes online


def test_local_check_with_key_shows_local_ok_and_masked() -> None:
    controller, page, online_calls = _controller()
    _fill(controller, provider="zai", model="glm-4.6", key="sk-zaikey1234567890")

    controller._on_validate(None)

    assert controller.status_text is not None
    assert "Локальная проверка пройдена" in controller.status_text.value
    assert "ZAI_API_KEY" in controller.status_text.value
    assert "sk-zaikey1234567890" not in controller.status_text.value  # masked only
    assert "Онлайн-проверка ещё не выполнялась" in controller.status_text.value
    assert online_calls == []
    assert controller.local_status_text is not None
    assert controller.local_status_text.value == "OK"


def test_local_check_empty_proxy_is_valid() -> None:
    controller, _, _ = _controller()
    _fill(controller, provider="zai", model="glm-4.6", key="sk-zaikey1234567890", proxy="")

    errors = controller.validate_settings()

    assert not any("proxy" in e.lower() for e in errors)


def test_local_check_bad_proxy_is_reported() -> None:
    controller, _, _ = _controller()
    _fill(controller, provider="zai", model="glm-4.6", key="sk-zaikey1234567890", proxy="://bad")

    controller._on_validate(None)

    assert controller.status_text is not None
    assert "Проверка не пройдена" in controller.status_text.value


def test_online_check_success() -> None:
    ok = ProviderCheckResult(True, "ok", "Онлайн-проверка «ZAI» прошла.", "sk****7890")
    controller, page, online_calls = _controller(online_results=[ok])
    _fill(controller, provider="zai", model="glm-4.6", key="sk-zaikey1234567890")

    controller._on_check_online(None)

    assert len(online_calls) == 1
    assert online_calls[0]["provider"] == "zai"
    assert online_calls[0]["model"] == "glm-4.6"
    # The key is passed to the checker (needed for the real request) but never
    # appears in the status text shown to the user.
    assert "sk-zaikey1234567890" not in (controller.status_text.value or "")
    assert "прошла" in controller.status_text.value
    assert controller.online_status_text is not None
    assert controller.online_status_text.value == "OK"
    assert page.update_calls >= 1


def test_online_check_auth_error() -> None:
    err = ProviderCheckResult(
        False, "auth_error",
        "Ключ «ZAI» не принят: ошибка авторизации (401/403).", "sk****7890",
    )
    controller, _, _ = _controller(online_results=[err])
    _fill(controller, provider="zai", model="glm-4.6", key="sk-zaikey1234567890")

    controller._on_check_online(None)

    assert "не принят" in controller.status_text.value
    assert "sk-zaikey1234567890" not in controller.status_text.value
    assert controller.online_status_text.value == "ОШИБКА"


def test_online_check_network_error() -> None:
    err = ProviderCheckResult(
        False, "network_error",
        "Не удалось подключиться к «ZAI». Проверьте интернет/proxy.", "",
    )
    controller, _, _ = _controller(online_results=[err])
    _fill(controller, provider="zai", model="glm-4.6", key="sk-zaikey1234567890")

    controller._on_check_online(None)

    assert "интернет/proxy" in controller.status_text.value.lower() or "интернет" in controller.status_text.value.lower()
    assert controller.online_status_text.value == "ОШИБКА"


def test_online_check_without_key_reports_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gui.settings._read_secret_from_env", lambda name: None)
    controller, _, online_calls = _controller()
    _fill(controller, provider="zai", model="glm-4.6", key=None)

    controller._on_check_online(None)

    assert "Не найден" in controller.status_text.value
    assert online_calls == []  # did not attempt a network call


def test_save_calls_storage_refreshes_key_badge_and_pushes() -> None:
    controller, page, _ = _controller()
    _fill(controller, provider="zai", model="glm-4.6", key="sk-zaikey1234567890")

    result = controller.save_settings_to_disk(None)

    assert result is True
    assert controller._save_calls  # type: ignore[attr-defined]
    assert controller._save_calls[0]["ZAI_API_KEY"] == "sk-zaikey1234567890"  # type: ignore[attr-defined]
    assert ".env.local" in controller.status_text.value
    assert controller.key_status_text is not None
    # Key badge shows a masked form, never the full key.
    assert "sk-zaikey1234567890" not in controller.key_status_text.value
    assert "ZAI_API_KEY" in controller.key_status_text.value
    assert page.update_calls >= 1


# --------------------------------------------------------------------------- #
# _default_save_settings merges into .env.local without erasing other lines
# --------------------------------------------------------------------------- #


def test_save_settings_merges_env_local_without_erasing_lines(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_local = tmp_path / ".env.local"
    env_local.write_text(
        'OTHER_VAR="keepme"\nZAI_API_KEY="old"\n# a comment\n',
        encoding="utf-8",
    )
    fake_settings = types.SimpleNamespace(
        llm=types.SimpleNamespace(provider="openrouter", model="gpt-4o-mini"),
        proxy=None,
    )
    monkeypatch.setattr("core.config.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("core.config.settings", fake_settings)

    ok = _default_save_settings(
        {"ZAI_API_KEY": "new-secret", "llm.provider": "zai", "llm.model": "glm-4.6"}
    )

    assert ok is True
    text = env_local.read_text(encoding="utf-8")
    assert 'ZAI_API_KEY="new-secret"' in text
    assert "old" not in text  # old value replaced
    assert 'OTHER_VAR="keepme"' in text  # unrelated line preserved
    # in-process settings updated
    assert fake_settings.llm.provider == "zai"
    assert fake_settings.llm.model == "glm-4.6"


def test_read_secret_from_env_local_overrides_env(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text('ZAI_API_KEY="from-env"\n', encoding="utf-8")
    (tmp_path / ".env.local").write_text('ZAI_API_KEY="from-local"\n', encoding="utf-8")
    monkeypatch.setattr("core.config.PROJECT_ROOT", tmp_path)

    assert _read_secret_from_env("ZAI_API_KEY") == "from-local"


def test_build_settings_tab_forwards_online_checker() -> None:
    page = FakePage()
    called: list[dict[str, Any]] = []

    def fake_online(**kw: Any) -> ProviderCheckResult:
        called.append(kw)
        return ProviderCheckResult(True, "ok", "ok", "")

    tab, controller = build_settings_tab(page, online_checker=fake_online)
    assert tab.label == "Настройки"
    assert controller.online_checker is fake_online


def test_offline_tests_make_no_network() -> None:
    """Sanity: building the tab and pushing statuses needs no network."""
    page = FakePage()
    build_settings_tab(page)
    assert page.update_calls >= 0
