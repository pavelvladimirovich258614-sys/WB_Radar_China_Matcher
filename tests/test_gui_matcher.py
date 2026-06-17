from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft
import pytest

from core.models import Candidate, Product
from gui.app import MatcherChinaController, build_matcher_tab, create_app


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


def _product(nm_id: int = 42) -> Product:
    return Product(
        nmId=nm_id,
        imtId=101,
        name="Фен",
        brand="B",
        price=1299.0,
        feedbacks=100,
        rating=4.6,
    )


def _candidate(
    site: str,
    title: str,
    similarity: float,
    price: float,
    video_url: str | None = None,
) -> Candidate:
    return Candidate(
        site=site,
        title=title,
        url=f"https://{site}.example/item",
        thumb_url=f"https://{site}.example/thumb.jpg",
        price=price,
        similarity=similarity,
        has_video=bool(video_url),
        video_url=video_url,
    )


def test_controller_build_tab_creates_controls() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    tab = controller.build_tab(page)

    assert tab.label == "Матчер China"
    assert controller.input_field is not None
    assert controller.search_button is not None
    assert controller.pick_file_button is not None
    assert controller.results_column is not None
    assert controller.status_text is not None
    assert controller.progress_bar is not None
    assert controller.download_all_button is not None


def test_build_matcher_tab_with_fake_pipeline() -> None:
    page = FakePage()
    called_with: list[Any] = []

    def fake_pipeline(query: str | Path) -> tuple[Product | None, list[Candidate]]:
        called_with.append(query)
        return _product(), [_candidate("alibaba", "Фен A", 0.91, 1200.0)]

    tab, controller = build_matcher_tab(page, matcher_pipeline=fake_pipeline)

    assert tab.label == "Матчер China"
    assert called_with == []


def test_create_app_first_tab_is_matcher() -> None:
    page = FakePage()
    tabs = create_app(page)

    assert page.theme_mode == ft.ThemeMode.DARK
    assert tabs.length == 3
    assert tabs.selected_index == 0
    content = tabs.content
    assert content is not None
    assert len(content.controls) == 3
    assert content.controls[0].label == "Матчер China"
    assert content.controls[1].label == "Разведка WB"
    assert content.controls[2].label == "Настройки"
    assert tabs.selected_index == 0


def test_search_with_fake_pipeline_renders_results() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    def fake_pipeline(query: str | Path) -> tuple[Product | None, list[Candidate]]:
        return _product(), [
            _candidate("alibaba", "Фен A", 0.91, 1200.0, video_url="https://v/a.mp4"),
            _candidate("1688", "Фен B", 0.85, 1100.0),
        ]

    controller.matcher_pipeline = fake_pipeline
    controller.input_field.value = "42"
    controller._on_search(None)

    assert controller._last_candidates is not None
    assert len(controller._last_candidates) == 2
    assert controller.results_column is not None
    assert len(controller.results_column.controls) == 2
    assert controller.status_text is not None
    assert "Найдено кандидатов: 2" in controller.status_text.value


def test_search_empty_input_shows_error() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)
    status_messages: list[str] = []
    controller.on_status = status_messages.append

    controller.input_field.value = ""
    controller._on_search(None)

    assert controller._last_candidates == []
    assert status_messages
    assert "Введите" in status_messages[-1]


def test_search_pipeline_error_is_handled() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    def failing_pipeline(query: str | Path) -> tuple[Product | None, list[Candidate]]:
        raise RuntimeError("network down")

    controller.matcher_pipeline = failing_pipeline
    controller.input_field.value = "42"
    controller._on_search(None)

    assert controller.results_column is not None
    assert len(controller.results_column.controls) == 0
    assert controller.status_text is not None
    assert "Ошибка поиска" in controller.status_text.value


def test_similarity_displayed_as_percent() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    controller.matcher_pipeline = lambda q: (
        _product(),
        [_candidate("alibaba", "Фен A", 0.9123, 1200.0)],
    )
    controller.input_field.value = "42"
    controller._on_search(None)

    card = controller.results_column.controls[0]
    text_controls = [
        c for c in _flatten_controls(card) if isinstance(c, ft.Text)
    ]
    meta = " ".join(t.value for t in text_controls)
    assert "91.2%" in meta


def test_download_button_calls_fake_downloader() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    calls: list[tuple[str, int]] = []

    def fake_downloader(url: str, nm_id: int) -> dict[str, Any]:
        calls.append((url, nm_id))
        return {"url": url, "nm_id": nm_id}

    controller.matcher_pipeline = lambda q: (
        _product(7),
        [_candidate("alibaba", "Фен", 0.9, 1000.0, video_url="https://v/x.mp4")],
    )
    controller.downloader = fake_downloader
    controller.input_field.value = "7"
    controller._on_search(None)

    candidate = controller._last_candidates[0]
    controller._download_one(candidate)

    assert calls == [("https://v/x.mp4", 7)]
    assert "Скачано видео: 1" in controller.status_text.value


def test_download_all_top5_takes_maximum_five() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    calls: list[str] = []

    def fake_downloader(url: str, nm_id: int) -> dict[str, Any]:
        calls.append(url)
        return {"url": url, "nm_id": nm_id}

    candidates = [
        _candidate("alibaba", f"Фен {i}", 0.9 - i * 0.01, 1000.0, video_url=f"https://v/{i}.mp4")
        for i in range(8)
    ]
    controller.matcher_pipeline = lambda q: (_product(99), candidates)
    controller.downloader = fake_downloader
    controller.input_field.value = "99"
    controller._on_search(None)

    controller._on_download_all(None)

    assert len(calls) == 5
    assert calls == [f"https://v/{i}.mp4" for i in range(5)]


def test_download_all_skips_candidates_without_video() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    calls: list[str] = []

    def fake_downloader(url: str, nm_id: int) -> dict[str, Any]:
        calls.append(url)
        return {"url": url, "nm_id": nm_id}

    candidates = [
        _candidate("alibaba", "A", 0.9, 1000.0),
        _candidate("1688", "B", 0.88, 900.0, video_url="https://v/b.mp4"),
        _candidate("taobao", "C", 0.86, 800.0),
        _candidate("alibaba", "D", 0.84, 700.0, video_url="https://v/d.mp4"),
    ]
    controller.matcher_pipeline = lambda q: (_product(3), candidates)
    controller.downloader = fake_downloader
    controller.input_field.value = "3"
    controller._on_search(None)

    controller._on_download_all(None)

    assert calls == ["https://v/b.mp4", "https://v/d.mp4"]


def test_public_api_import() -> None:
    from gui.app import create_app, build_matcher_tab

    assert callable(create_app)
    assert callable(build_matcher_tab)


# --------------------------------------------------------------------------- #
# FilePicker registration (regression guard for the "Unknown control:
# FilePicker" runtime bug). In Flet 0.85 FilePicker is a non-visual Service and
# must live in page.services — never inside the layout controls / page.overlay.
# --------------------------------------------------------------------------- #


class _FakePickedFile:
    def __init__(self, path: str | None, name: str) -> None:
        self.path = path
        self.name = name


class _FakeFilePicker:
    """Async FilePicker double mimicking Flet 0.85 pick_files contract."""

    def __init__(self, files: list[Any]) -> None:
        self._files = files
        self.pick_calls: list[dict[str, Any]] = []

    async def pick_files(self, **kwargs: Any) -> list[Any]:
        self.pick_calls.append(kwargs)
        return self._files


def test_filepicker_registered_in_services_not_overlay() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    assert any(isinstance(c, ft.FilePicker) for c in page.services), (
        "FilePicker must be registered in page.services (Flet 0.85 Service)"
    )
    assert not any(isinstance(c, ft.FilePicker) for c in page.overlay), (
        "FilePicker must NOT be in page.overlay — that triggers 'Unknown control'"
    )


def test_matcher_tab_layout_has_no_filepicker() -> None:
    """FilePicker must never appear anywhere in the rendered tab tree."""
    page = FakePage()
    controller = MatcherChinaController()
    tab = controller.build_tab(page)

    walked = _flatten_controls(tab)
    offenders = [c for c in walked if isinstance(c, ft.FilePicker)]
    assert offenders == [], f"FilePicker leaked into layout: {offenders}"


def test_create_app_layout_has_no_filepicker() -> None:
    page = FakePage()
    tabs = create_app(page)

    walked = _flatten_controls(tabs)
    assert not any(isinstance(c, ft.FilePicker) for c in walked)


def test_pick_file_button_is_wired() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    assert controller.pick_file_button is not None
    assert controller.file_picker is not None
    # The button handler is the async picker opener.
    assert callable(getattr(controller.pick_file_button, "on_click", None))


def test_apply_picked_files_updates_input_and_status() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    controller._apply_picked_files(
        [_FakePickedFile(path="D:/imgs/photo.png", name="photo.png")]
    )

    assert controller._selected_file_path == Path("D:/imgs/photo.png")
    assert controller.input_field is not None
    assert controller.input_field.value == str(Path("D:/imgs/photo.png"))
    assert controller.status_text is not None
    assert "Выбран файл" in controller.status_text.value


def test_apply_picked_files_without_path_clears_selection() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)

    controller._apply_picked_files([_FakePickedFile(path=None, name="web.jpg")])

    assert controller._selected_file_path is None
    assert controller.status_text is not None
    assert "Не удалось получить путь" in controller.status_text.value


def test_apply_picked_files_cancel_clears_selection() -> None:
    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)
    controller._selected_file_path = Path("D:/old.jpg")

    controller._apply_picked_files([])

    assert controller._selected_file_path is None


def test_on_pick_file_awaits_pick_files_and_applies_result() -> None:
    import asyncio

    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)
    fake = _FakeFilePicker([_FakePickedFile(path="C:/tmp/x.jpg", name="x.jpg")])
    controller.file_picker = fake

    asyncio.run(controller._on_pick_file(None))

    assert fake.pick_calls, "pick_files must be awaited"
    assert controller._selected_file_path == Path("C:/tmp/x.jpg")
    assert controller.input_field is not None
    assert controller.input_field.value == str(Path("C:/tmp/x.jpg"))


def test_on_pick_file_handles_cancel() -> None:
    import asyncio

    page = FakePage()
    controller = MatcherChinaController()
    controller.build_tab(page)
    controller.file_picker = _FakeFilePicker([])  # user cancelled

    asyncio.run(controller._on_pick_file(None))

    assert controller._selected_file_path is None


def _flatten_controls(control: Any) -> list[Any]:
    result: list[Any] = [control]
    if hasattr(control, "content"):
        result.extend(_flatten_controls(control.content))
    if hasattr(control, "controls"):
        for child in control.controls:
            result.extend(_flatten_controls(child))
    return result
