from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft
import pytest

from core.models import Product, VocItem, VoC
from gui.app import (
    DiscoveryWBController,
    MatcherChinaController,
    build_discovery_tab,
    create_app,
)
from harvest.discovery import ViralProduct, ViralResult
from harvest.hooks import VideoHookSet
from harvest.review_video import ReviewVideoItem


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


def _viral_product(nm_id: int = 100, viral_score: float = 0.95) -> ViralProduct:
    return ViralProduct(
        nmId=nm_id,
        imtId=200 + nm_id,
        name=f"Фен {nm_id}",
        brand="BrandA",
        price=1299.0,
        feedbacks=500 + nm_id,
        rating=4.7,
        viral_score=viral_score,
    )


def _voc() -> VoC:
    return VoC(
        боли=[VocItem(text="Шумит", frequency=5)],
        желания=[VocItem(text="Лёгкий", frequency=3)],
        страхи=[VocItem(text="Сломается", frequency=2)],
    )


def _hooks() -> VideoHookSet:
    return VideoHookSet(
        hooks=[f"Hook {i}" for i in range(1, 6)],
        structure=[],
        objections=["O1", "O2"],
    )


def _review_videos() -> list[ReviewVideoItem]:
    return [
        ReviewVideoItem(
            review_id="R1",
            nmId=100,
            rating=5.0,
            text="Класс",
            video_url="https://v/r1.mp4",
        ),
    ]


def test_controller_build_tab_creates_controls() -> None:
    page = FakePage()
    controller = DiscoveryWBController()
    tab = controller.build_tab(page)

    assert tab.label == "Разведка WB"
    assert controller.niche_input is not None
    assert controller.search_button is not None
    assert controller.results_column is not None
    assert controller.detail_column is not None
    assert controller.status_text is not None
    assert controller.progress_bar is not None


def test_create_app_has_two_tabs_and_matcher_first() -> None:
    page = FakePage()
    shell = create_app(page)

    assert page.theme_mode == ft.ThemeMode.DARK
    assert shell.sections == ["matcher", "discovery", "settings"]
    assert shell.selected_section == "matcher"
    assert shell.section_labels["matcher"] == "Матчер China"
    assert shell.section_labels["discovery"] == "Разведка WB"
    assert shell.section_labels["settings"] == "Настройки"


def test_search_with_fake_discovery_renders_results() -> None:
    page = FakePage()
    controller = DiscoveryWBController()
    controller.build_tab(page)

    def fake_discovery(query: str) -> ViralResult:
        return ViralResult(
            query=query,
            products=[
                _viral_product(100, 0.95),
                _viral_product(101, 0.88),
            ],
        )

    controller.discovery_service = fake_discovery
    controller.niche_input.value = "фен"
    controller._on_search(None)

    assert len(controller._last_products) == 2
    assert controller.results_column is not None
    assert len(controller.results_column.controls) == 4  # header + divider + 2 rows
    assert "Найдено вирусных товаров: 2" in controller.status_text.value


def test_empty_niche_shows_error() -> None:
    page = FakePage()
    controller = DiscoveryWBController()
    controller.build_tab(page)
    status_messages: list[str] = []
    controller.on_status = status_messages.append

    controller.niche_input.value = ""
    controller._on_search(None)

    assert controller._last_products == []
    assert status_messages
    assert "Введите" in status_messages[-1]


def test_discovery_error_is_handled() -> None:
    page = FakePage()
    controller = DiscoveryWBController()
    controller.build_tab(page)

    def failing_discovery(query: str) -> ViralResult:
        raise RuntimeError("network down")

    controller.discovery_service = failing_discovery
    controller.niche_input.value = "фен"
    controller._on_search(None)

    assert controller.results_column is not None
    assert len(controller.results_column.controls) == 0
    assert controller.status_text is not None
    assert "Ошибка разведки" in controller.status_text.value


def test_select_product_loads_voc_hooks_and_videos() -> None:
    page = FakePage()
    controller = DiscoveryWBController()
    controller.build_tab(page)

    controller.discovery_service = lambda q: ViralResult(
        query=q,
        products=[_viral_product(100)],
    )
    controller.voc_service = lambda nm_id: _voc()
    controller.hooks_service = lambda nm_id, voc: _hooks()
    controller.review_video_service = lambda nm_id: _review_videos()

    controller.niche_input.value = "фен"
    controller._on_search(None)
    controller._select_product(controller._last_products[0])

    assert controller._selected_product is not None
    assert controller._selected_product.nmId == 100
    assert controller._last_voc is not None
    assert controller._last_hooks is not None
    assert len(controller._last_videos) == 1
    assert controller.detail_column is not None
    detail_text = " ".join(
        c.value for c in _flatten_controls(controller.detail_column) if isinstance(c, ft.Text)
    )
    assert "Шумит" in detail_text
    assert "Hook 1" in detail_text
    assert "Видео из отзывов" in detail_text


def test_to_matcher_bridge_fills_matcher_input() -> None:
    page = FakePage()
    matcher_controller = MatcherChinaController()
    matcher_controller.build_tab(page)

    bridge_calls: list[int] = []

    def bridge(nm_id: int) -> None:
        bridge_calls.append(nm_id)
        matcher_controller.set_input_value(str(nm_id))

    discovery_controller = DiscoveryWBController(
        discovery_service=lambda q: ViralResult(
            query=q,
            products=[_viral_product(100)],
        ),
        to_matcher_bridge=bridge,
    )
    discovery_controller.build_tab(page)

    discovery_controller.niche_input.value = "фен"
    discovery_controller._on_search(None)
    discovery_controller._select_product(discovery_controller._last_products[0])
    discovery_controller._on_to_matcher(None)

    assert bridge_calls == [100]
    assert matcher_controller.input_field.value == "100"


def test_create_app_bridge_fills_matcher_input() -> None:
    page = FakePage()

    def fake_discovery(query: str) -> ViralResult:
        return ViralResult(query=query, products=[_viral_product(123)])

    shell = create_app(
        page,
        discovery_service=fake_discovery,
        voc_service=lambda nm_id: _voc(),
        hooks_service=lambda nm_id, voc: _hooks(),
        review_video_service=lambda nm_id: _review_videos(),
    )

    matcher_content = shell.get_section_content("matcher")
    discovery_content = shell.get_section_content("discovery")
    assert matcher_content is not None
    assert discovery_content is not None

    discovery_controller = _find_discovery_controller(discovery_content)
    discovery_controller.niche_input.value = "фен"
    discovery_controller._on_search(None)
    discovery_controller._select_product(discovery_controller._last_products[0])
    with pytest.warns(RuntimeWarning, match="coroutine"):
        discovery_controller._on_to_matcher(None)

    matcher_input = _find_matcher_input(matcher_content)
    assert matcher_input.value == "123"


def test_public_api_import() -> None:
    from gui.app import create_app, build_matcher_tab, build_discovery_tab

    assert callable(create_app)
    assert callable(build_matcher_tab)
    assert callable(build_discovery_tab)


def _flatten_controls(control: Any) -> list[Any]:
    result: list[Any] = [control]
    if hasattr(control, "content"):
        result.extend(_flatten_controls(control.content))
    if hasattr(control, "controls"):
        for child in control.controls:
            result.extend(_flatten_controls(child))
    return result


def _find_discovery_controller(tab: Any) -> DiscoveryWBController:
    # The detail column holds a reference back to the controller via its parent.
    for c in _flatten_controls(tab):
        if isinstance(c, ft.Column) and hasattr(c, "_discovery_controller"):
            return c._discovery_controller
    raise AssertionError("discovery controller not found in tab")


def _find_matcher_input(tab: Any) -> ft.TextField:
    for c in _flatten_controls(tab):
        if isinstance(c, ft.TextField) and getattr(c, "label", None) == "Артикул/ссылка WB":
            return c
    raise AssertionError("matcher input not found in tab")
