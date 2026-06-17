from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path
from typing import Any, Callable, Optional

import flet as ft

from core.models import Candidate, Product, VocItem, VoC
from harvest.discovery import ViralProduct, ViralResult, niche
from harvest.download import download_videos
from harvest.hooks import VideoHookSet, generate_hooks
from harvest.review_video import ReviewVideoItem, get_review_videos
from harvest.voc import analyze_reviews_voc
from matcher.input import resolve_input

# Re-export the settings tab builder so consumers can import from gui.app.
from gui.settings import SettingsController, build_settings_tab

logger = logging.getLogger(__name__)

MatcherPipeline = Callable[[str | Path], tuple[Product | None, list[Candidate]]]
Downloader = Callable[[str, int], Any]

DiscoveryService = Callable[[str], ViralResult]
VoCService = Callable[[int], VoC]
HooksService = Callable[[int, VoC], VideoHookSet]
ReviewVideoService = Callable[[int], list[ReviewVideoItem]]
ToMatcherBridge = Callable[[int], Any]

DEFAULT_THEME = ft.Theme(
    color_scheme_seed=ft.Colors.BLUE_GREY,
    color_scheme=ft.ColorScheme(
        primary=ft.Colors.BLUE_GREY_200,
        on_primary=ft.Colors.BLACK,
        surface=ft.Colors.GREY_900,
        surface_container_highest=ft.Colors.GREY_800,
        on_surface=ft.Colors.WHITE,
        on_surface_variant=ft.Colors.GREY_400,
    ),
)


def _pct(value: float) -> str:
    return f"{max(0.0, min(1.0, value)) * 100:.1f}%"


class MatcherChinaController:
    """Controller for the China matcher tab.

    Keeps UI controls as attributes so tests can inspect and interact with
    them without launching a real window.
    """

    def __init__(
        self,
        *,
        matcher_pipeline: MatcherPipeline | None = None,
        downloader: Downloader | None = None,
        output_root: Path | str | None = None,
        on_status: Callable[[str], Any] | None = None,
    ) -> None:
        self.matcher_pipeline = matcher_pipeline
        self.downloader = downloader
        self.output_root = output_root
        self.on_status = on_status

        self.input_field: ft.TextField | None = None
        self.file_picker: ft.FilePicker | None = None
        self.results_column: ft.Column | None = None
        self.status_text: ft.Text | None = None
        self.progress_bar: ft.ProgressBar | None = None
        self.download_all_button: ft.Button | None = None
        self.pick_file_button: ft.Button | None = None
        self.search_button: ft.Button | None = None

        self._last_candidates: list[Candidate] = []
        self._last_product: Product | None = None
        self._selected_file_path: Path | None = None

    def set_input_value(self, value: str) -> None:
        """Set the matcher input field value (used by the "To Matcher" bridge)."""
        if self.input_field is not None:
            self.input_field.value = value

    def focus_input(self) -> None:
        """Move focus to the matcher input field (best-effort)."""
        if self.input_field is None:
            return
        try:
            result = self.input_field.focus()
            if result is not None and hasattr(result, "__await__"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    # No running event loop in tests; ignore fire-and-forget.
                    pass
        except Exception:
            pass

    def _set_status(self, message: str) -> None:
        if self.status_text is not None:
            self.status_text.value = message
        if self.on_status is not None:
            try:
                self.on_status(message)
            except Exception:
                pass

    def _show_progress(self, visible: bool) -> None:
        if self.progress_bar is not None:
            self.progress_bar.visible = visible

    def _build_input_row(self, page: ft.Page) -> ft.Row:
        self.input_field = ft.TextField(
            label="Артикул/ссылка WB",
            hint_text="12345678 или https://www.wildberries.ru/catalog/.../detail.aspx",
            expand=True,
            on_submit=self._on_search,
        )
        self.search_button = ft.Button(
            "Найти",
            icon=ft.Icons.SEARCH,
            on_click=self._on_search,
        )
        self.pick_file_button = ft.Button(
            "Фото",
            icon=ft.Icons.IMAGE,
            on_click=self._on_pick_file,
        )
        self.file_picker = ft.FilePicker()
        page.overlay.append(self.file_picker)

        return ft.Row(
            [
                self.input_field,
                self.pick_file_button,
                self.search_button,
            ],
            spacing=12,
        )

    def _on_pick_file(self, _event: ft.ControlEvent) -> None:
        if self.file_picker is not None:
            self.file_picker.pick_files(
                dialog_title="Выберите фото товара",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["jpg", "jpeg", "png", "webp"],
                allow_multiple=False,
            )

    def _on_file_picked(self, event: ft.FilePickerResultEvent) -> None:
        if event.files and event.files:
            file = event.files[0]
            self._selected_file_path = Path(file.path)
            if self.input_field is not None:
                self.input_field.value = str(self._selected_file_path)
            self._set_status(f"Выбран файл: {file.name}")
        else:
            self._selected_file_path = None

    def _on_search(self, _event: ft.ControlEvent | None) -> None:
        value = ""
        if self.input_field is not None:
            value = (self.input_field.value or "").strip()

        if not value and self._selected_file_path is None:
            self._set_status("Введите артикул/ссылку WB или выберите фото")
            return

        query: str | Path = value
        if self._selected_file_path is not None and (
            not value or value == str(self._selected_file_path)
        ):
            query = self._selected_file_path

        self._run_search(query)

    def _run_search(self, query: str | Path) -> None:
        self._set_status("Запуск поиска...")
        self._show_progress(True)
        self._last_candidates = []
        self._last_product = None
        if self.results_column is not None:
            self.results_column.controls.clear()
        if self.download_all_button is not None:
            self.download_all_button.disabled = True

        try:
            if self.matcher_pipeline is not None:
                product, candidates = self.matcher_pipeline(query)
            else:
                product, candidates = _default_matcher_pipeline(query)

            self._last_product = product
            self._last_candidates = candidates
            self._render_results(candidates)
            count = len(candidates)
            self._set_status(f"Найдено кандидатов: {count}")
            if self.download_all_button is not None:
                self.download_all_button.disabled = count == 0
        except Exception as exc:
            logger.exception("Matcher search failed")
            self._set_status(f"Ошибка поиска: {exc}")
        finally:
            self._show_progress(False)

    def _render_results(self, candidates: list[Candidate]) -> None:
        if self.results_column is None:
            return

        self.results_column.controls.clear()
        if not candidates:
            self.results_column.controls.append(
                ft.Text("Ничего не найдено", color=ft.Colors.GREY_400)
            )
            return

        for candidate in candidates:
            self.results_column.controls.append(
                self._build_candidate_row(candidate)
            )

    def _build_candidate_row(self, candidate: Candidate) -> ft.Card:
        actions = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.OPEN_IN_BROWSER,
                    tooltip="Открыть",
                    on_click=lambda _e, url=candidate.url: _open_url(url),
                ),
                ft.IconButton(
                    icon=ft.Icons.VIDEOCAM,
                    tooltip="Видео",
                    on_click=lambda _e, c=candidate: _show_video_info(c),
                ),
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD,
                    tooltip="Скачать видео",
                    on_click=lambda _e, cand=candidate: self._download_one(cand),
                    disabled=not bool(candidate.video_url),
                ),
            ],
            spacing=4,
        )

        title_text = ft.Text(
            candidate.title or "—",
            size=14,
            weight=ft.FontWeight.W_500,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )

        meta_text = ft.Text(
            f"{candidate.site} • {_pct(candidate.similarity)} • {candidate.price:.2f} ¥",
            size=12,
            color=ft.Colors.GREY_400,
        )

        content = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.IMAGE, color=ft.Colors.GREY_500)
                        if not candidate.thumb_url
                        else ft.Image(
                            src=candidate.thumb_url,
                            width=64,
                            height=64,
                            fit=ft.BoxFit.COVER,
                            error_content=ft.Icon(
                                ft.Icons.BROKEN_IMAGE, color=ft.Colors.GREY_500
                            ),
                        ),
                        width=64,
                        height=64,
                        bgcolor=ft.Colors.GREY_800,
                        border_radius=4,
                    ),
                    ft.Column(
                        [title_text, meta_text],
                        spacing=4,
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    actions,
                ],
                spacing=12,
            ),
            padding=12,
        )
        return ft.Card(content=content, bgcolor=ft.Colors.GREY_800)

    def _download_one(self, candidate: Candidate) -> None:
        if not candidate.video_url:
            self._set_status("У этого кандидата нет видео")
            return
        nm_id = self._resolve_nm_id()
        self._download_videos([candidate.video_url], nm_id)

    def _on_download_all(self, _event: ft.ControlEvent) -> None:
        urls = [
            c.video_url
            for c in self._last_candidates[:5]
            if c.video_url
        ]
        if not urls:
            self._set_status("Нет видео для скачивания")
            return
        nm_id = self._resolve_nm_id()
        self._download_videos(urls, nm_id)

    def _resolve_nm_id(self) -> int:
        if self._last_product is not None and self._last_product.nmId:
            return self._last_product.nmId
        if self._selected_file_path is not None:
            return 0
        value = ""
        if self.input_field is not None:
            value = (self.input_field.value or "").strip()
        try:
            from matcher.input import parse_wb_nm_id

            parsed = parse_wb_nm_id(value)
            if parsed is not None:
                return parsed
        except Exception:
            pass
        return 0

    def _download_videos(self, urls: list[str], nm_id: int) -> None:
        self._set_status(f"Скачивание {len(urls)} видео...")
        self._show_progress(True)
        try:
            if self.downloader is not None:
                assets = self.downloader(urls[0], nm_id) if len(urls) == 1 else [
                    self.downloader(url, nm_id) for url in urls
                ]
                if not isinstance(assets, list):
                    assets = [assets]
            else:
                assets = download_videos(urls, nm_id, "china", output_root=self.output_root)
            self._set_status(f"Скачано видео: {len(assets)}")
        except Exception as exc:
            logger.exception("Video download failed")
            self._set_status(f"Ошибка скачивания: {exc}")
        finally:
            self._show_progress(False)

    def build_tab(self, page: ft.Page) -> ft.Tab:
        self.results_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.status_text = ft.Text("Готов к поиску", size=12, color=ft.Colors.GREY_400)
        self.progress_bar = ft.ProgressBar(visible=False, color=ft.Colors.BLUE_GREY_200)
        self.download_all_button = ft.Button(
            "Скачать все видео топ-5",
            icon=ft.Icons.DOWNLOAD_FOR_OFFLINE,
            on_click=self._on_download_all,
            disabled=True,
        )

        content = ft.Column(
            [
                self._build_input_row(page),
                self.download_all_button,
                self.progress_bar,
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                ft.Text("Результаты", weight=ft.FontWeight.W_600),
                self.results_column,
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                self.status_text,
            ],
            spacing=16,
            expand=True,
        )

        tab = ft.Tab(label="Матчер China")
        tab.content = ft.Container(content=content, padding=16)
        return tab


class DiscoveryWBController:
    """Controller for the WB discovery tab.

    Keeps UI controls as attributes and accepts fake services for non-live
    testing.
    """

    def __init__(
        self,
        *,
        discovery_service: DiscoveryService | None = None,
        voc_service: VoCService | None = None,
        hooks_service: HooksService | None = None,
        review_video_service: ReviewVideoService | None = None,
        downloader: Downloader | None = None,
        output_root: Path | str | None = None,
        to_matcher_bridge: ToMatcherBridge | None = None,
        on_status: Callable[[str], Any] | None = None,
    ) -> None:
        self.discovery_service = discovery_service
        self.voc_service = voc_service
        self.hooks_service = hooks_service
        self.review_video_service = review_video_service
        self.downloader = downloader
        self.output_root = output_root
        self.to_matcher_bridge = to_matcher_bridge
        self.on_status = on_status

        self.niche_input: ft.TextField | None = None
        self.search_button: ft.Button | None = None
        self.results_column: ft.Column | None = None
        self.status_text: ft.Text | None = None
        self.progress_bar: ft.ProgressBar | None = None
        self.detail_column: ft.Column | None = None

        self._last_products: list[ViralProduct] = []
        self._selected_product: ViralProduct | None = None
        self._last_voc: VoC | None = None
        self._last_hooks: VideoHookSet | None = None
        self._last_videos: list[ReviewVideoItem] = []

    def _set_status(self, message: str) -> None:
        if self.status_text is not None:
            self.status_text.value = message
        if self.on_status is not None:
            try:
                self.on_status(message)
            except Exception:
                pass

    def _show_progress(self, visible: bool) -> None:
        if self.progress_bar is not None:
            self.progress_bar.visible = visible

    def _on_search(self, _event: ft.ControlEvent | None) -> None:
        query = ""
        if self.niche_input is not None:
            query = (self.niche_input.value or "").strip()

        if not query:
            self._set_status("Введите нишу или запрос")
            return

        self._run_discovery(query)

    def _run_discovery(self, query: str) -> None:
        self._set_status("Поиск вирусных товаров...")
        self._show_progress(True)
        self._last_products = []
        self._selected_product = None
        self._last_voc = None
        self._last_hooks = None
        self._last_videos = []
        if self.results_column is not None:
            self.results_column.controls.clear()
        if self.detail_column is not None:
            self.detail_column.controls.clear()

        try:
            if self.discovery_service is not None:
                result = self.discovery_service(query)
            else:
                result = _default_discovery_service(query)

            self._last_products = result.products
            self._render_results(result.products)
            count = len(result.products)
            self._set_status(f"Найдено вирусных товаров: {count}")
        except Exception as exc:
            logger.exception("Discovery failed")
            self._set_status(f"Ошибка разведки: {exc}")
        finally:
            self._show_progress(False)

    def _render_results(self, products: list[ViralProduct]) -> None:
        if self.results_column is None:
            return

        self.results_column.controls.clear()
        if not products:
            self.results_column.controls.append(
                ft.Text("Ничего не найдено", color=ft.Colors.GREY_400)
            )
            return

        header = ft.Row(
            [
                ft.Text("nmId", weight=ft.FontWeight.W_600, width=80),
                ft.Text("Название", weight=ft.FontWeight.W_600, expand=True),
                ft.Text("Бренд", weight=ft.FontWeight.W_600, width=100),
                ft.Text("Viral", weight=ft.FontWeight.W_600, width=60),
                ft.Text("Отзывы", weight=ft.FontWeight.W_600, width=70),
                ft.Text("Рейтинг", weight=ft.FontWeight.W_600, width=60),
                ft.Text("Действия", weight=ft.FontWeight.W_600, width=90),
            ],
            spacing=8,
        )
        self.results_column.controls.append(header)
        self.results_column.controls.append(ft.Divider(height=1, color=ft.Colors.GREY_700))

        for product in products:
            self.results_column.controls.append(
                self._build_product_row(product)
            )

    def _build_product_row(self, product: ViralProduct) -> ft.Row:
        select_button = ft.Button(
            "Выбрать",
            icon=ft.Icons.ARROW_FORWARD,
            on_click=lambda _e, p=product: self._select_product(p),
        )
        return ft.Row(
            [
                ft.Text(str(product.nmId), width=80, size=12),
                ft.Text(
                    product.name or "—",
                    expand=True,
                    size=13,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(product.brand or "—", width=100, size=12),
                ft.Text(f"{product.viral_score:.2f}", width=60, size=12),
                ft.Text(str(product.feedbacks), width=70, size=12),
                ft.Text(f"{product.rating:.1f}", width=60, size=12),
                ft.Container(select_button, width=90),
            ],
            spacing=8,
        )

    def _select_product(self, product: ViralProduct) -> None:
        self._selected_product = product
        self._set_status(f"Выбран товар {product.nmId}")
        if self.detail_column is not None:
            self.detail_column.controls.clear()
            self.detail_column.controls.append(
                ft.Text(
                    f"{product.name} (nmId {product.nmId})",
                    weight=ft.FontWeight.W_600,
                    size=16,
                )
            )

        try:
            self._load_voc(product.nmId)
            self._load_hooks(product.nmId)
            self._load_review_videos(product.nmId)
        except Exception as exc:
            logger.exception("Product detail loading failed")
            self._set_status(f"Ошибка загрузки деталей: {exc}")

    def _load_voc(self, nm_id: int) -> None:
        if self.voc_service is not None:
            voc = self.voc_service(nm_id)
        else:
            voc = _default_voc_service(nm_id)
        self._last_voc = voc
        if self.detail_column is None:
            return

        self.detail_column.controls.append(
            ft.Text("Боли", weight=ft.FontWeight.W_600)
        )
        self.detail_column.controls.extend(
            self._build_voc_items(voc.боли)
        )
        self.detail_column.controls.append(
            ft.Text("Желания", weight=ft.FontWeight.W_600)
        )
        self.detail_column.controls.extend(
            self._build_voc_items(voc.желания)
        )
        self.detail_column.controls.append(
            ft.Text("Страхи", weight=ft.FontWeight.W_600)
        )
        self.detail_column.controls.extend(
            self._build_voc_items(voc.страхи)
        )

    def _build_voc_items(self, items: list[VocItem]) -> list[ft.Control]:
        if not items:
            return [ft.Text("—", color=ft.Colors.GREY_400, size=12)]
        return [
            ft.Text(f"• {item.text} ({item.frequency})", size=12)
            for item in items
        ]

    def _load_hooks(self, nm_id: int) -> None:
        hooks: VideoHookSet
        if self.hooks_service is not None:
            hooks = self.hooks_service(nm_id, self._last_voc or VoC())
        else:
            hooks = _default_hooks_service(nm_id, self._last_voc or VoC())
        self._last_hooks = hooks
        if self.detail_column is None:
            return

        self.detail_column.controls.append(
            ft.Text("Хуки", weight=ft.FontWeight.W_600)
        )
        for idx, hook in enumerate(hooks.hooks, start=1):
            self.detail_column.controls.append(
                ft.Text(f"{idx}. {hook}", size=12)
            )
        if hooks.objections:
            self.detail_column.controls.append(
                ft.Text("Возражения", weight=ft.FontWeight.W_600)
            )
            for objection in hooks.objections:
                self.detail_column.controls.append(
                    ft.Text(f"- {objection}", size=12)
                )

    def _load_review_videos(self, nm_id: int) -> None:
        if self.review_video_service is not None:
            videos = self.review_video_service(nm_id)
        else:
            videos = _default_review_video_service(nm_id)
        self._last_videos = videos
        if self.detail_column is None:
            return

        self.detail_column.controls.append(
            ft.Text("Видео из отзывов", weight=ft.FontWeight.W_600)
        )
        if not videos:
            self.detail_column.controls.append(
                ft.Text("Видеоотзывов не найдено", color=ft.Colors.GREY_400, size=12)
            )
            return

        for item in videos:
            row = ft.Row(
                [
                    ft.Text(f"★{item.rating:.0f}", width=40, size=12),
                    ft.Text(
                        item.text[:60] or "видео",
                        expand=True,
                        size=12,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Button(
                        "Скачать",
                        icon=ft.Icons.DOWNLOAD,
                        on_click=lambda _e, url=item.video_url: self._download_video(url, nm_id),
                    ),
                ],
                spacing=8,
            )
            self.detail_column.controls.append(row)

    def _download_video(self, url: str, nm_id: int) -> None:
        self._set_status(f"Скачивание видео для nmId={nm_id}...")
        self._show_progress(True)
        try:
            if self.downloader is not None:
                asset = self.downloader(url, nm_id)
                count = 1 if asset is not None else 0
            else:
                from harvest.download import download_video
                asset = download_video(
                    url, nm_id, "wb_review", output_root=self.output_root
                )
                count = 1
            self._set_status(f"Скачано видео: {count}")
        except Exception as exc:
            logger.exception("Review video download failed")
            self._set_status(f"Ошибка скачивания: {exc}")
        finally:
            self._show_progress(False)

    def _on_to_matcher(self, _event: ft.ControlEvent) -> None:
        if self._selected_product is None:
            self._set_status("Сначала выберите товар")
            return
        nm_id = self._selected_product.nmId
        if self.to_matcher_bridge is not None:
            try:
                self.to_matcher_bridge(nm_id)
            except Exception as exc:
                logger.exception("Bridge to matcher failed")
                self._set_status(f"Ошибка моста в Матчер: {exc}")
        else:
            self._set_status("Мост в Матчер не настроен")

    def build_tab(self, page: ft.Page) -> ft.Tab:
        self.niche_input = ft.TextField(
            label="Ниша / запрос",
            hint_text="например: фен для волос",
            expand=True,
            on_submit=self._on_search,
        )
        self.search_button = ft.Button(
            "Найти вирусные",
            icon=ft.Icons.TRENDING_UP,
            on_click=self._on_search,
        )
        self.results_column = ft.Column(
            spacing=8, scroll=ft.ScrollMode.AUTO, expand=True
        )
        self.detail_column = ft.Column(
            spacing=8, scroll=ft.ScrollMode.AUTO, expand=True
        )
        self.detail_column._discovery_controller = self  # type: ignore[attr-defined]
        self.status_text = ft.Text("Готов к разведке", size=12, color=ft.Colors.GREY_400)
        self.progress_bar = ft.ProgressBar(visible=False, color=ft.Colors.BLUE_GREY_200)

        to_matcher_button = ft.Button(
            "В Матчер",
            icon=ft.Icons.ARROW_BACK,
            on_click=self._on_to_matcher,
        )

        input_row = ft.Row(
            [self.niche_input, self.search_button],
            spacing=12,
        )

        detail_panel = ft.Column(
            [
                ft.Row(
                    [ft.Text("Детали товара", weight=ft.FontWeight.W_600), to_matcher_button],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                self.detail_column,
            ],
            expand=True,
        )

        content = ft.Column(
            [
                input_row,
                self.progress_bar,
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                ft.Text("Вирусные товары", weight=ft.FontWeight.W_600),
                self.results_column,
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                detail_panel,
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                self.status_text,
            ],
            spacing=16,
            expand=True,
        )

        tab = ft.Tab(label="Разведка WB")
        tab.content = ft.Container(content=content, padding=16)
        return tab


def _default_discovery_service(query: str) -> ViralResult:
    return niche(query)


def _default_voc_service(nm_id: int) -> VoC:
    from harvest.reviews import collect_reviews_for_product

    result = collect_reviews_for_product(nm_id, max_count=1000)
    reviews_data = []
    if result.output_path and Path(result.output_path).exists():
        reviews_data = json.loads(Path(result.output_path).read_text(encoding="utf-8"))
    return analyze_reviews_voc(reviews_data)


def _default_hooks_service(nm_id: int, voc: VoC) -> VideoHookSet:
    return generate_hooks(voc, nm_id=nm_id)


def _default_review_video_service(nm_id: int) -> list[ReviewVideoItem]:
    return get_review_videos(nm_id, max_count=1000)


def _open_url(url: str | None) -> None:
    if url:
        webbrowser.open(url)


def _show_video_info(candidate: Candidate) -> None:
    if candidate.video_url:
        logger.info("Video URL for %s: %s", candidate.url, candidate.video_url)
    else:
        logger.info("No video for %s", candidate.url)


def _default_matcher_pipeline(query: str | Path) -> tuple[Product | None, list[Candidate]]:
    """Default matcher pipeline using project modules.

    This is a thin wrapper that resolves the input, searches all configured
    marketplaces, ranks the results, and extracts videos for the top
    candidates. It is intentionally not invoked in non-live tests.
    """
    resolved = resolve_input(query)
    product = resolved.product

    from core.config import settings
    from matcher.china import (
        AlibabaImageSearchDriver,
        S1688ImageSearchDriver,
        TaobaoImageSearchDriver,
    )
    from matcher.rank import rank_candidates
    from matcher.video_china import ChinaVideoExtractor

    marketplace_drivers: dict[str, Any] = {
        "alibaba": AlibabaImageSearchDriver,
        "s1688": S1688ImageSearchDriver,
        "taobao": TaobaoImageSearchDriver,
    }

    all_candidates: list[Candidate] = []
    try:
        for name in settings.matcher.marketplaces:
            driver_cls = marketplace_drivers.get(name)
            if driver_cls is None:
                continue
            try:
                with driver_cls() as driver:
                    candidates = driver.search_by_image(
                        str(resolved.query_image_path),
                        max_results=settings.matcher.max_candidates,
                    )
                    all_candidates.extend(candidates)
            except Exception as exc:
                logger.warning("Marketplace %s search failed: %s", name, exc)

        ranked = rank_candidates(
            resolved.query_image_path,
            all_candidates,
            use_clip=False,
        )

        if ranked:
            extractor = ChinaVideoExtractor()
            try:
                ranked = extractor.extract_for_candidates(ranked)
            finally:
                extractor.close()
    except Exception:
        logger.exception("Default matcher pipeline failed")
        raise

    return product, ranked


def build_matcher_tab(
    page: ft.Page,
    *,
    matcher_pipeline: MatcherPipeline | None = None,
    downloader: Downloader | None = None,
    output_root: Path | str | None = None,
) -> tuple[ft.Tab, MatcherChinaController]:
    """Build the China matcher tab with dependency injection for tests."""
    controller = MatcherChinaController(
        matcher_pipeline=matcher_pipeline,
        downloader=downloader,
        output_root=output_root,
    )
    return controller.build_tab(page), controller


def build_discovery_tab(
    page: ft.Page,
    *,
    discovery_service: DiscoveryService | None = None,
    voc_service: VoCService | None = None,
    hooks_service: HooksService | None = None,
    review_video_service: ReviewVideoService | None = None,
    downloader: Downloader | None = None,
    output_root: Path | str | None = None,
    to_matcher_bridge: ToMatcherBridge | None = None,
) -> tuple[ft.Tab, DiscoveryWBController]:
    """Build the WB discovery tab with dependency injection for tests."""
    controller = DiscoveryWBController(
        discovery_service=discovery_service,
        voc_service=voc_service,
        hooks_service=hooks_service,
        review_video_service=review_video_service,
        downloader=downloader,
        output_root=output_root,
        to_matcher_bridge=to_matcher_bridge,
    )
    return controller.build_tab(page), controller


def create_app(
    page: ft.Page,
    *,
    matcher_pipeline: MatcherPipeline | None = None,
    downloader: Downloader | None = None,
    output_root: Path | str | None = None,
    discovery_service: DiscoveryService | None = None,
    voc_service: VoCService | None = None,
    hooks_service: HooksService | None = None,
    review_video_service: ReviewVideoService | None = None,
    matcher_controller: MatcherChinaController | None = None,
    settings_controller: SettingsController | None = None,
) -> ft.Tabs:
    """Create the full application with the China matcher tab as default."""
    page.title = "WB Radar & China Matcher"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = DEFAULT_THEME
    page.bgcolor = ft.Colors.GREY_900

    matcher_tab, matcher_ctrl = build_matcher_tab(
        page,
        matcher_pipeline=matcher_pipeline,
        downloader=downloader,
        output_root=output_root,
    )
    if matcher_controller is not None:
        matcher_ctrl = matcher_controller

    def bridge_to_matcher(nm_id: int) -> None:
        matcher_ctrl.set_input_value(str(nm_id))
        matcher_ctrl.focus_input()

    discovery_tab, _discovery_ctrl = build_discovery_tab(
        page,
        discovery_service=discovery_service,
        voc_service=voc_service,
        hooks_service=hooks_service,
        review_video_service=review_video_service,
        downloader=downloader,
        output_root=output_root,
        to_matcher_bridge=bridge_to_matcher,
    )

    if settings_controller is not None:
        settings_tab = settings_controller.build_tab(page)
    else:
        settings_tab, _settings_ctrl = build_settings_tab(page)

    tabs = ft.Tabs(
        content=ft.Column([matcher_tab, discovery_tab, settings_tab], expand=True),
        length=3,
        selected_index=0,
        animation_duration=200,
        expand=True,
    )
    page.add(tabs)
    return tabs


def main() -> None:
    ft.app(target=create_app)


if __name__ == "__main__":
    main()
