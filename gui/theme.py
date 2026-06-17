"""Design system for the WB Radar & China Matcher desktop UI.

Provides a small token model with two palettes — **night** (deep graphite with
neon-green/cyan accents) and **day** (soft light with blue/teal accents) — plus
a helper that turns tokens into a Flet ``ft.Theme`` (M3 ``ColorScheme``).

The shell chrome (sidebar, header, backgrounds) is styled with explicit tokens
and rebuilt on theme switch. Section contents use **M3 role colors** (e.g.
``ft.Colors.SURFACE_CONTAINER_HIGH``, ``ON_SURFACE_VARIANT``) which resolve
against ``page.theme`` and therefore re-theme live without rebuilding the
controls (so the user's input/results survive a theme toggle).
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

NIGHT = "night"
DAY = "day"


@dataclass(frozen=True)
class ThemeTokens:
    """Resolved palette for one theme mode."""

    mode: str
    is_dark: bool

    page_bg: str
    page_bg2: str
    sidebar_bg: str
    sidebar_bg2: str
    content_bg: str

    card_bg: str
    card_bg_hover: str
    input_bg: str

    text_primary: str
    text_secondary: str

    accent: str
    on_accent: str
    accent_2: str

    border: str
    border_active: str
    selected_bg: str

    danger: str
    success: str
    warning: str

    glow: str
    glow_2: str


NIGHT_TOKENS = ThemeTokens(
    mode=NIGHT,
    is_dark=True,
    page_bg="#0B0F0D",
    page_bg2="#050806",
    sidebar_bg="#070B09",
    sidebar_bg2="#0B1110",
    content_bg="#0B0F0D",
    card_bg="#121A16",
    card_bg_hover="#17221D",
    input_bg="#0E1411",
    text_primary="#F2FFF7",
    text_secondary="#8FA79A",
    accent="#39FF88",
    on_accent="#06140C",
    accent_2="#00D1FF",
    border="#234236",
    border_active="#39FF88",
    selected_bg="#13241A",
    danger="#FF6B7A",
    success="#39FF88",
    warning="#FFC857",
    glow="#39FF88",
    glow_2="#00D1FF",
)


DAY_TOKENS = ThemeTokens(
    mode=DAY,
    is_dark=False,
    page_bg="#F4F7F2",
    page_bg2="#EEF4F8",
    sidebar_bg="#EAF1F7",
    sidebar_bg2="#F2F7FB",
    content_bg="#F7F9F5",
    card_bg="#FFFFFF",
    card_bg_hover="#EEF5FB",
    input_bg="#FFFFFF",
    text_primary="#162027",
    text_secondary="#5E6E78",
    accent="#0E8F6A",
    on_accent="#FFFFFF",
    accent_2="#128BFF",
    border="#D7E4EA",
    border_active="#128BFF",
    selected_bg="#DCEEFB",
    danger="#D6404F",
    success="#0E8F6A",
    warning="#C98700",
    glow="#128BFF",
    glow_2="#16C7B7",
)


def get_theme_tokens(mode: str = NIGHT) -> ThemeTokens:
    """Return the token set for ``mode`` (defaults to night)."""
    return DAY_TOKENS if mode == DAY else NIGHT_TOKENS


def other_mode(mode: str) -> str:
    return DAY if mode == NIGHT else NIGHT


def build_flet_theme(tokens: ThemeTokens) -> ft.Theme:
    """Build a Flet ``ft.Theme`` whose M3 color roles match ``tokens``.

    Section controls that use M3 role colors (``SURFACE_CONTAINER_HIGH``,
    ``ON_SURFACE_VARIANT``, ``OUTLINE_VARIANT`` ...) resolve against this theme,
    so they re-theme live when ``page.theme`` is swapped.
    """
    return ft.Theme(
        color_scheme_seed=tokens.accent,
        color_scheme=ft.ColorScheme(
            primary=tokens.accent,
            on_primary=tokens.on_accent,
            primary_container=tokens.selected_bg,
            on_primary_container=tokens.accent,
            secondary=tokens.accent_2,
            on_secondary=tokens.on_accent,
            secondary_container=tokens.selected_bg,
            surface=tokens.page_bg,
            on_surface=tokens.text_primary,
            on_surface_variant=tokens.text_secondary,
            outline=tokens.border,
            outline_variant=tokens.border,
            surface_container_lowest=tokens.page_bg2,
            surface_container_low=tokens.input_bg,
            surface_container=tokens.card_bg,
            surface_container_high=tokens.card_bg_hover,
            surface_container_highest=tokens.card_bg_hover,
            surface_bright=tokens.card_bg_hover,
            surface_dim=tokens.page_bg,
        ),
    )


def sidebar_gradient(tokens: ThemeTokens) -> ft.LinearGradient:
    """Subtle vertical gradient for the sidebar background."""
    return ft.LinearGradient(
        begin=ft.Alignment(0, -1),
        end=ft.Alignment(0, 1),
        colors=[tokens.sidebar_bg, tokens.sidebar_bg2],
    )


def content_glow(tokens: ThemeTokens) -> ft.RadialGradient:
    """Soft radial accent glow placed behind the content area."""
    return ft.RadialGradient(
        center=ft.Alignment(0.92, -0.7),
        radius=1.25,
        colors=[
            ft.Colors.with_opacity(0.10, tokens.glow),
            ft.Colors.with_opacity(0.04, tokens.glow_2),
            ft.Colors.TRANSPARENT,
        ],
    )


def accent_shadow(tokens: ThemeTokens, blur: int = 22, opacity: float = 0.35) -> ft.BoxShadow:
    """Neon/soft accent shadow for highlighted cards/buttons."""
    return ft.BoxShadow(
        spread_radius=0,
        blur_radius=blur,
        color=ft.Colors.with_opacity(opacity, tokens.accent),
        offset=ft.Offset(0, 4),
    )
