"""Tests for the desktop UI theme system (night/day tokens + live switching)."""

from __future__ import annotations

from typing import Any

import flet as ft
import pytest

from gui.app import SECTION_DISCOVERY, ShellController, create_app
from gui import theme as theme_mod
from gui.theme import DAY, NIGHT, ThemeTokens, get_theme_tokens


class FakePage:
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

    def clean(self) -> None:  # real pages expose clean(); keep parity
        self.controls.clear()


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #


def test_night_and_day_tokens_exist_and_differ() -> None:
    night = get_theme_tokens(NIGHT)
    day = get_theme_tokens(DAY)

    assert isinstance(night, ThemeTokens)
    assert isinstance(day, ThemeTokens)
    assert night.is_dark is True
    assert day.is_dark is False
    assert night.mode == NIGHT
    assert day.mode == DAY
    # The two palettes are actually different.
    assert night.page_bg != day.page_bg
    assert night.accent != day.accent


def test_default_tokens_are_night() -> None:
    assert get_theme_tokens().mode == NIGHT


def test_all_token_fields_are_colors() -> None:
    for mode in (NIGHT, DAY):
        t = get_theme_tokens(mode)
        for field in (
            "page_bg",
            "sidebar_bg",
            "card_bg",
            "text_primary",
            "text_secondary",
            "accent",
            "accent_2",
            "border",
            "selected_bg",
            "glow",
        ):
            value = getattr(t, field)
            assert isinstance(value, str) and value.startswith("#"), (mode, field, value)


# --------------------------------------------------------------------------- #
# Shell defaults + switcher
# --------------------------------------------------------------------------- #


def test_shell_default_theme_is_night() -> None:
    shell = ShellController()
    assert shell.theme_mode == NIGHT
    assert shell.tokens.is_dark is True


def test_create_app_exposes_theme_toggle_and_applies_night() -> None:
    page = FakePage()
    shell = create_app(page)

    assert shell.theme_toggle is not None
    assert callable(getattr(shell.theme_toggle, "on_click", None))
    # Night applied to the page.
    assert page.theme_mode == ft.ThemeMode.DARK
    assert page.bgcolor == get_theme_tokens(NIGHT).page_bg
    assert page.theme is not None


def test_toggle_theme_switches_mode_and_page_colors() -> None:
    page = FakePage()
    shell = create_app(page)
    night_bg = page.bgcolor

    shell.toggle_theme()

    assert shell.theme_mode == DAY
    assert shell.tokens.is_dark is False
    assert page.theme_mode == ft.ThemeMode.LIGHT
    assert page.bgcolor == get_theme_tokens(DAY).page_bg
    assert page.bgcolor != night_bg


def test_set_theme_round_trip_restores_night() -> None:
    page = FakePage()
    shell = create_app(page)

    shell.set_theme(DAY)
    assert shell.theme_mode == DAY
    shell.set_theme(NIGHT)
    assert shell.theme_mode == NIGHT
    assert page.theme_mode == ft.ThemeMode.DARK


def test_active_section_survives_theme_switch() -> None:
    page = FakePage()
    shell = create_app(page)
    shell.set_section(SECTION_DISCOVERY)
    assert shell.selected_section == SECTION_DISCOVERY

    shell.toggle_theme()

    # Section selection is preserved across the theme switch.
    assert shell.selected_section == SECTION_DISCOVERY
    assert shell.content_area is not None
    assert shell.content_area.content is shell.get_section_content(SECTION_DISCOVERY)


def test_root_still_attached_after_theme_switch() -> None:
    page = FakePage()
    shell = create_app(page)
    assert shell.root in page.controls

    shell.toggle_theme()

    # The (rebuilt) root replaced the old one in the page.
    assert shell.root in page.controls
    assert len([c for c in page.controls if c is shell.root]) == 1


# --------------------------------------------------------------------------- #
# Styling + FilePicker invariant
# --------------------------------------------------------------------------- #


def test_sidebar_buttons_have_styling() -> None:
    page = FakePage()
    shell = create_app(page)

    for key, button in shell.sidebar_buttons.items():
        assert isinstance(button, ft.Container)
        assert button.border_radius is not None
        assert callable(button.on_click), f"{key} button must be clickable"


def test_filepicker_remains_in_services_after_theme_switch() -> None:
    page = FakePage()
    shell = create_app(page)

    assert any(isinstance(c, ft.FilePicker) for c in page.services)

    shell.toggle_theme()

    # Theme switching must not move FilePicker out of page.services.
    assert any(isinstance(c, ft.FilePicker) for c in page.services)
