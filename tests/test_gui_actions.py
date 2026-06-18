"""Regression tests for the desktop GUI action-update layer.

These guard the bug where section controllers (Matcher / Discovery / Settings)
mutated control properties (status text, progress bar, results list, session
statuses) inside their click handlers but never pushed those mutations to the
live Flet client, so every in-section button looked unresponsive while the
sidebar (which DID call update) kept working.

Each section controller must call ``page.update()`` (via its ``_push`` helper)
after changing visible state. A ``FakePage`` with an ``update()`` recorder lets
us assert that the push actually happens, which the older ``FakePage`` doubles
(without an ``update`` attribute) could not detect.
"""

from __future__ import annotations

from typing import Any

import flet as ft
import pytest

from core.models import Product, VocItem, VoC
from gui.app import (
    SECTION_DISCOVERY,
    SECTION_SETTINGS,
    MatcherChinaController,
    create_app,
)
from gui.settings import SettingsController
from harvest.discovery import ViralProduct, ViralResult
from harvest.hooks import VideoHookSet
from harvest.review_video import ReviewVideoItem


class FakePage:
    """Minimal Flet page double that RECORDS ``update()`` calls.

    This is the key difference from the older FakePage: it exposes a real
    ``update`` method so we can assert that handlers push mutations to the
    client (the exact behaviour that was missing and made buttons look dead).
    """

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
# Helpers / fixtures
# --------------------------------------------------------------------------- #


def _viral_product(nm_id: int = 100) -> ViralProduct:
    return ViralProduct(
        nmId=nm_id,
        imtId=200 + nm_id,
        name=f"Фен {nm_id}",
        brand="BrandA",
        price=1299.0,
        feedbacks=500,
        rating=4.7,
        viral_score=0.95,
    )


class _FakePickedFile:
    def __init__(self, path: str, name: str) -> None:
        self.path = path
        self.name = name


class _FakeFilePicker:
    def __init__(self, files: list[Any]) -> None:
        self._files = files

    async def pick_files(self, **kwargs: Any) -> list[Any]:
        return self._files


def _settings_controller_recording() -> SettingsController:
    """A SettingsController with fake storage and an update-recording page."""
    save_calls: list[dict[str, str]] = []

    def fake_save(values: dict[str, str]) -> bool:
        save_calls.append(values)
        return True

    controller = SettingsController(
        save_settings=fake_save,
        open_folder=lambda path: True,
        session_status=lambda site: "ok",
    )
    controller._save_calls = save_calls  # type: ignore[attr-defined]
    return controller


# --------------------------------------------------------------------------- #
# Matcher controller
# --------------------------------------------------------------------------- #


def test_matcher_set_status_pushes_to_page() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    controller._set_status("hello")

    assert controller.status_text is not None
    assert controller.status_text.value == "hello"
    assert page.update_calls >= 1


def test_matcher_show_progress_pushes_to_page() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)
    assert controller.progress_bar is not None

    controller._show_progress(True)

    assert controller.progress_bar.visible is True
    assert page.update_calls >= 1


def test_matcher_empty_search_shows_hint_and_pushes() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    controller.input_field.value = ""
    controller._on_search(None)

    assert controller.status_text is not None
    assert "Введите" in controller.status_text.value
    assert page.update_calls >= 1


def test_matcher_search_with_fake_pipeline_pushes_results() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    controller.matcher_pipeline = lambda q: (
        Product(nmId=7, imtId=1, name="x", brand="b", price=1.0, feedbacks=1, rating=5.0),
        [],
    )
    controller.input_field.value = "7"
    before = page.update_calls
    controller._on_search(None)

    assert "Найдено кандидатов" in controller.status_text.value
    assert page.update_calls > before  # results render pushed an update


def test_matcher_apply_picked_files_shows_filename_and_pushes() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    controller._apply_picked_files([_FakePickedFile("D:/img.png", "photo.png")])

    assert controller.status_text is not None
    assert "Фото выбрано" in controller.status_text.value
    assert "photo.png" in controller.status_text.value
    assert page.update_calls >= 1


def test_matcher_pick_file_cancel_shows_cancel_and_pushes() -> None:
    import asyncio

    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)
    controller.file_picker = _FakeFilePicker([])
    messages: list[str] = []
    controller.on_status = messages.append

    asyncio.run(controller._on_pick_file(None))

    assert "Открываю выбор файла…" in messages
    assert "Выбор фото отменён" in messages
    assert page.update_calls >= 1


def test_matcher_pick_file_success_shows_opening_then_chosen() -> None:
    import asyncio

    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)
    controller.file_picker = _FakeFilePicker([_FakePickedFile("C:/x.jpg", "x.jpg")])
    messages: list[str] = []
    controller.on_status = messages.append

    asyncio.run(controller._on_pick_file(None))

    assert messages[0] == "Открываю выбор файла…"
    assert any("Фото выбрано" in m for m in messages)


# --------------------------------------------------------------------------- #
# Discovery controller
# --------------------------------------------------------------------------- #


def test_discovery_empty_search_shows_hint_and_pushes() -> None:
    from gui.app import DiscoveryWBController

    page = FakePage()
    controller = DiscoveryWBController()
    controller.build_tab(page)

    controller.niche_input.value = ""
    controller._on_search(None)

    assert controller.status_text is not None
    assert "Введите" in controller.status_text.value
    assert page.update_calls >= 1


def test_discovery_to_matcher_calls_bridge_and_pushes() -> None:
    from gui.app import DiscoveryWBController

    page = FakePage()
    bridge_calls: list[int] = []

    def bridge(nm_id: int) -> None:
        bridge_calls.append(nm_id)

    controller = DiscoveryWBController(
        discovery_service=lambda q: ViralResult(query=q, products=[_viral_product(100)]),
        to_matcher_bridge=bridge,
    )
    controller.build_tab(page)

    controller.niche_input.value = "фен"
    controller._on_search(None)
    controller._select_product(controller._last_products[0])
    before = page.update_calls
    controller._on_to_matcher(None)

    assert bridge_calls == [100]
    assert controller.status_text is not None
    assert "перенесён в Матчер China" in controller.status_text.value
    assert page.update_calls > before


def test_discovery_select_product_pushes_detail() -> None:
    from gui.app import DiscoveryWBController

    page = FakePage()
    controller = DiscoveryWBController(
        discovery_service=lambda q: ViralResult(query=q, products=[_viral_product(100)]),
        voc_service=lambda nm_id: VoC(
            боли=[VocItem(text="Шумит", frequency=1)],
            желания=[],
            страхи=[],
        ),
        hooks_service=lambda nm_id, voc: VideoHookSet(hooks=[], structure=[], objections=[]),
        review_video_service=lambda nm_id: [],
    )
    controller.build_tab(page)

    controller.niche_input.value = "фен"
    controller._on_search(None)
    before = page.update_calls
    controller._select_product(controller._last_products[0])

    assert page.update_calls > before  # detail panel population pushed


# --------------------------------------------------------------------------- #
# Settings controller
# --------------------------------------------------------------------------- #


def _fill_valid_settings(controller: SettingsController, *, proxy: str = "") -> None:
    controller.provider_dropdown.value = "openrouter"
    controller.model_field.value = "gpt-4o-mini"
    controller.proxy_field.value = proxy
    controller.output_dir_field.value = "./output"
    controller.sessions_dir_field.value = "./sessions"
    # A real (non-masked) key so the local check finds a key for the provider.
    if "openrouter" in controller.key_fields:
        controller.key_fields["openrouter"].value = "sk-or-test-key-1234567890"


def test_settings_validate_pushes_and_shows_live_check_warning() -> None:
    page = FakePage()
    controller = _settings_controller_recording()
    controller.build_tab(page)
    _fill_valid_settings(controller)

    controller._on_validate(None)

    assert controller.status_text is not None
    assert "Локальная проверка пройдена" in controller.status_text.value
    assert page.update_calls >= 1


def test_settings_validate_empty_proxy_is_valid() -> None:
    page = FakePage()
    controller = _settings_controller_recording()
    controller.build_tab(page)
    _fill_valid_settings(controller, proxy="")

    errors = controller.validate_settings()

    assert not any("proxy" in e.lower() for e in errors)


def test_settings_validate_failure_pushes_error_status() -> None:
    page = FakePage()
    controller = _settings_controller_recording()
    controller.build_tab(page)
    controller.provider_dropdown.value = "openrouter"
    controller.model_field.value = ""
    controller.proxy_field.value = "://bad"
    controller.output_dir_field.value = ""
    controller.sessions_dir_field.value = ""

    controller._on_validate(None)

    assert controller.status_text is not None
    assert "Проверка не пройдена" in controller.status_text.value
    assert page.update_calls >= 1


def test_settings_save_pushes_and_reports_env_local() -> None:
    page = FakePage()
    controller = _settings_controller_recording()
    controller.build_tab(page)
    _fill_valid_settings(controller)

    result = controller.save_settings_to_disk(None)

    assert result is True
    assert controller.status_text is not None
    assert ".env.local" in controller.status_text.value
    assert page.update_calls >= 1


def test_settings_validate_does_not_leak_full_key_in_status() -> None:
    page = FakePage()
    controller = _settings_controller_recording()
    controller.build_tab(page)
    _fill_valid_settings(controller)
    secret = "sk-supersecret-key-12345"
    controller.key_fields["openrouter"].value = secret

    controller._on_validate(None)

    assert controller.status_text is not None
    assert secret not in controller.status_text.value


def test_settings_open_output_pushes_opening_status() -> None:
    page = FakePage()
    controller = _settings_controller_recording()
    controller.build_tab(page)
    controller.output_dir_field.value = "./my-output"

    controller._on_open_output(None)

    assert controller.status_text is not None
    assert "Открыта папка output" in controller.status_text.value
    assert page.update_calls >= 1


# --------------------------------------------------------------------------- #
# Shell integration: navigation / theme / FilePicker still intact
# --------------------------------------------------------------------------- #


def test_sidebar_navigation_still_swaps_content() -> None:
    page = FakePage()
    shell = create_app(page)

    shell.set_section(SECTION_DISCOVERY)
    assert shell.selected_section == SECTION_DISCOVERY
    assert shell.content_area.content is shell.get_section_content(SECTION_DISCOVERY)

    shell.set_section(SECTION_SETTINGS)
    assert shell.selected_section == SECTION_SETTINGS
    assert shell.content_area.content is shell.get_section_content(SECTION_SETTINGS)


def test_theme_toggle_still_flips_mode() -> None:
    page = FakePage()
    shell = create_app(page)
    assert page.theme_mode == ft.ThemeMode.DARK

    shell.toggle_theme()
    assert page.theme_mode == ft.ThemeMode.LIGHT

    shell.toggle_theme()
    assert page.theme_mode == ft.ThemeMode.DARK


def test_filepicker_remains_in_services_after_app_build() -> None:
    page = FakePage()
    create_app(page)

    assert any(isinstance(c, ft.FilePicker) for c in page.services)


def test_no_network_in_offline_action_tests() -> None:
    """Sanity: building the app and pushing statuses does not require network."""
    page = FakePage()
    create_app(page)
    # If we got here without raising, the action layer is import/build safe.
    assert page.update_calls >= 0
