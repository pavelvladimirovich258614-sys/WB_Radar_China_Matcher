from __future__ import annotations

from typing import Any

import flet as ft
import pytest

from gui.app import create_app
from gui.settings import (
    LLM_PROVIDERS,
    SettingsController,
    SettingsSnapshot,
    build_settings_tab,
    mask_secret,
)


class FakePage:
    """Minimal page double for unit tests without a real Flet window."""

    def __init__(self) -> None:
        self.title = ""
        self.theme_mode: ft.ThemeMode | None = None
        self.theme: Any | None = None
        self.bgcolor: Any | None = None
        self.controls: list[Any] = []
        self.overlay: list[Any] = []
        self.services: list[Any] = []

    def add(self, control: Any) -> None:
        self.controls.append(control)


def _settings_controller(
    *,
    save: bool = True,
    open_folder: bool = True,
    sessions: dict[str, str] | None = None,
) -> SettingsController:
    save_calls: list[dict[str, str]] = []
    folder_calls: list[str] = []
    session_map = sessions or {}

    def fake_save(values: dict[str, str]) -> bool:
        save_calls.append(values)
        return save

    def fake_open_folder(path: str) -> bool:
        folder_calls.append(path)
        return open_folder
    controller = SettingsController(
        save_settings=fake_save,
        open_folder=fake_open_folder,
        session_status=lambda site: session_map.get(site, "ok"),
    )
    controller._save_calls = save_calls  # type: ignore[attr-defined]
    controller._folder_calls = folder_calls  # type: ignore[attr-defined]
    return controller


def test_build_settings_tab_creates_controls() -> None:
    page = FakePage()
    tab, controller = build_settings_tab(page)

    assert tab.label == "Настройки"
    assert controller.provider_dropdown is not None
    assert controller.model_field is not None
    assert controller.proxy_field is not None
    assert controller.output_dir_field is not None
    assert controller.sessions_dir_field is not None
    assert controller.status_text is not None
    assert set(controller.key_fields) == {"openrouter", "zai", "groq", "ollama"}


def test_create_app_has_three_tabs_in_order() -> None:
    page = FakePage()
    shell = create_app(page)

    assert shell.sections == ["matcher", "discovery", "settings"]
    assert shell.selected_section == "matcher"
    assert shell.section_labels == {
        "matcher": "Матчер China",
        "discovery": "Разведка WB",
        "settings": "Настройки",
    }
    assert shell.content_area is not None
    assert shell.content_area.content is not None


def test_load_settings_returns_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage()
    controller = _settings_controller(sessions={"1688": "ok"})
    monkeypatch.setattr(
        "core.config.settings",
        type("S", (), {
            "llm": type("L", (), {"provider": "zai", "model": "glm-4-flash"})(),
            "proxy": "http://proxy.example:8080",
            "paths": type("P", (), {"output": "./out", "sessions": "./sess"})(),
            "openrouter_api_key": "sk-abc123",
            "zai_api_key": None,
            "groq_api_key": None,
            "ollama_base_url": None,
        })(),
    )

    snapshot = controller.load_settings()

    assert isinstance(snapshot, SettingsSnapshot)
    assert snapshot.provider == "zai"
    assert snapshot.model == "glm-4-flash"
    assert snapshot.proxy == "http://proxy.example:8080"
    assert snapshot.output_dir == "./out"
    assert snapshot.sessions_dir == "./sess"
    assert snapshot.sessions == {"1688": "ok", "taobao": "ok", "chatgpt": "ok"}
    assert snapshot.openrouter_api_key == "sk-abc123"


def test_mask_secret_hides_full_key() -> None:
    assert mask_secret("sk-abcdefghijklmnopqrstuvwxyz") == "sk****wxyz"
    assert mask_secret("abcd") == "abcd"
    assert mask_secret("abcdefgh") == "ab****efgh"
    assert mask_secret("") == ""
    assert mask_secret(None) == ""


def test_validate_settings_catches_bad_proxy() -> None:
    page = FakePage()
    controller = _settings_controller()
    controller.build_tab(page)

    controller.provider_dropdown.value = "openrouter"
    controller.model_field.value = "gpt-4"
    controller.proxy_field.value = "://bad"
    controller.output_dir_field.value = "./output"
    controller.sessions_dir_field.value = "./sessions"

    errors = controller.validate_settings()

    assert any("proxy" in e.lower() for e in errors)


def test_validate_settings_passes_for_good_values() -> None:
    page = FakePage()
    controller = _settings_controller()
    controller.build_tab(page)

    controller.provider_dropdown.value = "groq"
    controller.model_field.value = "llama-3.1-70b"
    controller.proxy_field.value = "http://proxy.example:8080"
    controller.output_dir_field.value = "./output"
    controller.sessions_dir_field.value = "./sessions"

    errors = controller.validate_settings()
    assert errors == []


def test_save_settings_calls_fake_storage() -> None:
    page = FakePage()
    controller = _settings_controller()
    controller.build_tab(page)
    save_calls = controller._save_calls  # type: ignore[attr-defined]

    controller.provider_dropdown.value = "openrouter"
    controller.model_field.value = "gpt-4"
    controller.proxy_field.value = ""
    controller.output_dir_field.value = "./output"
    controller.sessions_dir_field.value = "./sessions"

    result = controller.save_settings_to_disk(None)

    assert result is True
    assert len(save_calls) == 1
    assert save_calls[0]["llm.provider"] == "openrouter"
    assert save_calls[0]["llm.model"] == "gpt-4"
    assert "Сохранены" in controller.status_text.value or "Настройки сохранены" in controller.status_text.value


def test_save_settings_reports_failure() -> None:
    page = FakePage()
    controller = _settings_controller(save=False)
    controller.build_tab(page)

    controller.provider_dropdown.value = "openrouter"
    controller.model_field.value = "gpt-4"
    controller.proxy_field.value = ""
    controller.output_dir_field.value = "./output"
    controller.sessions_dir_field.value = "./sessions"

    result = controller.save_settings_to_disk(None)

    assert result is False
    assert "Не удалось" in controller.status_text.value


def test_session_statuses_displayed(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage()
    controller = _settings_controller(
        sessions={"1688": "активна", "taobao": "нет сессии", "chatgpt": "ok"}
    )
    monkeypatch.setattr(
        "core.config.settings",
        type("S", (), {
            "llm": type("L", (), {"provider": "openrouter", "model": "gpt-4"})(),
            "proxy": None,
            "paths": type("P", (), {"output": "./output", "sessions": "./sessions"})(),
            "openrouter_api_key": None,
            "zai_api_key": None,
            "groq_api_key": None,
            "ollama_base_url": None,
        })(),
    )
    controller.build_tab(page)

    for site, expected in (
        ("1688", "активна"),
        ("taobao", "нет сессии"),
        ("chatgpt", "ok"),
    ):
        text = controller.session_status_texts[site]
        assert text.value == expected


def test_validate_button_updates_status() -> None:
    page = FakePage()
    controller = _settings_controller()
    controller.build_tab(page)

    controller.provider_dropdown.value = "unknown"
    controller.model_field.value = ""
    controller.proxy_field.value = "://bad"
    controller.output_dir_field.value = ""
    controller.sessions_dir_field.value = ""

    controller._on_validate(None)

    assert "Проверка не пройдена" in controller.status_text.value


def test_open_output_button_calls_fake_opener() -> None:
    page = FakePage()
    controller = _settings_controller()
    controller.build_tab(page)
    folder_calls = controller._folder_calls  # type: ignore[attr-defined]

    controller.output_dir_field.value = "./my-output"
    controller._on_open_output(None)

    assert folder_calls == ["./my-output"]
    assert "Открыта папка output" in controller.status_text.value


def test_open_sessions_button_reports_failure() -> None:
    page = FakePage()
    controller = _settings_controller(open_folder=False)
    controller.build_tab(page)

    controller.sessions_dir_field.value = "./my-sessions"
    controller._on_open_sessions(None)

    assert "Не удалось открыть sessions" in controller.status_text.value


def test_provider_field_masked_value_not_full_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage()
    monkeypatch.setattr(
        "core.config.settings",
        type("S", (), {
            "llm": type("L", (), {"provider": "openrouter", "model": "gpt-4"})(),
            "proxy": None,
            "paths": type("P", (), {"output": "./output", "sessions": "./sessions"})(),
            "openrouter_api_key": "sk-abcdefghijklmnopqrstuvwxyz",
            "zai_api_key": None,
            "groq_api_key": None,
            "ollama_base_url": None,
        })(),
    )
    tab, controller = build_settings_tab(page)

    field = controller.key_fields["openrouter"]
    assert field.value != "sk-abcdefghijklmnopqrstuvwxyz"
    assert "****" in field.value
    assert field.password is True


def test_public_api_import() -> None:
    from gui.app import create_app, build_matcher_tab, build_discovery_tab, build_settings_tab

    assert callable(create_app)
    assert callable(build_matcher_tab)
    assert callable(build_discovery_tab)
    assert callable(build_settings_tab)


def _flatten_controls(control: Any) -> list[Any]:
    result: list[Any] = [control]
    if hasattr(control, "content"):
        result.extend(_flatten_controls(control.content))
    if hasattr(control, "controls"):
        for child in control.controls:
            result.extend(_flatten_controls(child))
    return result
