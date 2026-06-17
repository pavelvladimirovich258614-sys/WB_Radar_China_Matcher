"""Tests for the custom desktop shell (sidebar + swappable content).

These guard the regression where ``ft.Tabs`` in Flet 0.85 only rendered tab
labels in the packaged desktop client (Tab has no ``content`` field). The shell
replaces Tabs with a sidebar of clickable sections and a content area that
swaps on selection.
"""

from __future__ import annotations

from typing import Any

import flet as ft
import pytest

from gui.app import (
    SECTION_DISCOVERY,
    SECTION_MATCHER,
    SECTION_SETTINGS,
    ShellController,
    build_desktop_shell,
    build_sidebar_button,
    create_app,
)


class FakePage:
    """Minimal Flet page double with both overlay and services lists."""

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


def _flatten(control: Any) -> list[Any]:
    out: list[Any] = [control]
    if hasattr(control, "content") and control is not None:
        try:
            child = control.content
        except Exception:
            child = None
        if child is not None:
            out.extend(_flatten(child))
    if hasattr(control, "controls"):
        for c in control.controls or []:
            out.extend(_flatten(c))
    return out


def _find_text(control: Any, value: str) -> ft.Text | None:
    for c in _flatten(control):
        if isinstance(c, ft.Text) and c.value == value:
            return c
    return None


def _find_text_field(control: Any, label: str) -> ft.TextField | None:
    for c in _flatten(control):
        if isinstance(c, ft.TextField) and getattr(c, "label", None) == label:
            return c
    return None


def _find_button(control: Any, text: str) -> ft.Control | None:
    for c in _flatten(control):
        # In Flet 0.85 ft.Button stores its label in the ``content`` field.
        if isinstance(c, ft.Button) and getattr(c, "content", None) == text:
            return c
    return None


# --------------------------------------------------------------------------- #
# create_app builds a working shell
# --------------------------------------------------------------------------- #


def test_create_app_returns_shell_and_adds_root_to_page() -> None:
    page = FakePage()
    shell = create_app(page)

    assert isinstance(shell, ShellController)
    assert shell.root is not None
    assert page.controls[-1] is shell.root


def test_shell_has_three_sections_matcher_default() -> None:
    page = FakePage()
    shell = create_app(page)

    assert shell.sections == ["matcher", "discovery", "settings"]
    assert shell.selected_section == SECTION_MATCHER
    assert shell.section_labels == {
        SECTION_MATCHER: "Матчер China",
        SECTION_DISCOVERY: "Разведка WB",
        SECTION_SETTINGS: "Настройки",
    }


def test_default_content_area_is_not_empty() -> None:
    page = FakePage()
    shell = create_app(page)

    assert shell.content_area is not None
    assert shell.content_area.content is not None
    # Header reflects the default section.
    assert shell.header_title is not None
    assert shell.header_title.value == "Матчер China"


def test_sidebar_has_three_clickable_buttons() -> None:
    page = FakePage()
    shell = create_app(page)

    assert set(shell.sidebar_buttons) == {"matcher", "discovery", "settings"}
    for key, button in shell.sidebar_buttons.items():
        assert isinstance(button, ft.Container)
        on_click = getattr(button, "on_click", None)
        assert callable(on_click), f"sidebar button {key} must be clickable"


def test_clicking_discovery_button_switches_content() -> None:
    page = FakePage()
    shell = create_app(page)
    discovery_content = shell.get_section_content(SECTION_DISCOVERY)

    shell.sidebar_buttons[SECTION_DISCOVERY].on_click(None)

    assert shell.selected_section == SECTION_DISCOVERY
    assert shell.content_area is not None
    assert shell.content_area.content is discovery_content
    assert shell.header_title is not None
    assert shell.header_title.value == "Разведка WB"


def test_clicking_settings_button_switches_content() -> None:
    page = FakePage()
    shell = create_app(page)
    settings_content = shell.get_section_content(SECTION_SETTINGS)

    shell.set_section(SECTION_SETTINGS)

    assert shell.selected_section == SECTION_SETTINGS
    assert shell.content_area is not None
    assert shell.content_area.content is settings_content


def test_set_section_round_trip_restores_matcher() -> None:
    page = FakePage()
    shell = create_app(page)
    matcher_content = shell.get_section_content(SECTION_MATCHER)

    shell.set_section(SECTION_DISCOVERY)
    assert shell.selected_section == SECTION_DISCOVERY
    shell.set_section(SECTION_MATCHER)
    assert shell.selected_section == SECTION_MATCHER
    assert shell.content_area.content is matcher_content


# --------------------------------------------------------------------------- #
# Each section exposes its real controls
# --------------------------------------------------------------------------- #


def test_matcher_section_has_input_and_search_button() -> None:
    page = FakePage()
    shell = create_app(page)
    matcher = shell.get_section_content(SECTION_MATCHER)

    assert _find_text_field(matcher, "Артикул/ссылка WB") is not None
    assert _find_button(matcher, "Найти") is not None
    # Photo button is present too.
    assert _find_button(matcher, "Фото") is not None


def test_discovery_section_has_niche_and_search_button() -> None:
    page = FakePage()
    shell = create_app(page)
    discovery = shell.get_section_content(SECTION_DISCOVERY)

    assert _find_text_field(discovery, "Ниша / запрос") is not None
    assert _find_button(discovery, "Найти вирусные") is not None


def test_settings_section_has_provider_dropdown_and_title() -> None:
    page = FakePage()
    shell = create_app(page)
    settings = shell.get_section_content(SECTION_SETTINGS)

    assert _find_text(settings, "Настройки") is not None
    has_dropdown = any(isinstance(c, ft.Dropdown) for c in _flatten(settings))
    assert has_dropdown, "settings section must expose the provider dropdown"


# --------------------------------------------------------------------------- #
# FilePicker stays a Service, never a layout/overlay control
# --------------------------------------------------------------------------- #


def test_filepicker_registered_in_services_not_in_shell_layout() -> None:
    page = FakePage()
    shell = create_app(page)

    assert any(isinstance(c, ft.FilePicker) for c in page.services)
    walked = _flatten(shell.root)
    assert not any(isinstance(c, ft.FilePicker) for c in walked)
    assert not any(isinstance(c, ft.FilePicker) for c in page.overlay)


# --------------------------------------------------------------------------- #
# build_desktop_shell / build_sidebar_button units
# --------------------------------------------------------------------------- #


def test_build_sidebar_button_is_clickable_container() -> None:
    calls: list[str] = []

    def on_click(_e: Any) -> None:
        calls.append("clicked")

    button = build_sidebar_button(
        label="X", icon=ft.Icons.HOME, selected=True, on_click=on_click
    )
    assert isinstance(button, ft.Container)
    assert callable(button.on_click)
    button.on_click(None)
    assert calls == ["clicked"]


def test_build_desktop_shell_builds_from_sections() -> None:
    page = FakePage()
    sections = [
        ("a", "A", "sub a", ft.Icons.HOME, ft.Container(content=ft.Text("A content"))),
        ("b", "B", "sub b", ft.Icons.STAR, ft.Container(content=ft.Text("B content"))),
    ]
    shell = build_desktop_shell(page, sections)

    assert shell.sections == ["a", "b"]
    assert shell.selected_section == "a"
    assert isinstance(shell.root, ft.Row)
    # Switching swaps the content.
    shell.set_section("b")
    assert shell.selected_section == "b"
    assert shell.content_area.content is sections[1][4]
