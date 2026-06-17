from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import flet as ft
import httpx
import pytest
from PIL import Image

from core.llm.base import LLMProvider
from core.models import Candidate, Product, Review, VocItem, VoC
from gui.app import (
    DiscoveryWBController,
    MatcherChinaController,
    build_discovery_tab,
    build_matcher_tab,
    create_app,
)
from harvest.discovery import ViralProduct, ViralResult, compute_viral_scores
from harvest.download import VideoAsset, download_videos
from harvest.hooks import VideoHookSet
from harvest.review_video import ReviewVideoItem
from harvest.reviews import ReviewCollectionResult
from matcher.input import ResolvedInput
from matcher.rank import rank_candidates


@pytest.fixture
def wb_nm_id() -> int:
    return 12345678


@pytest.fixture
def query_image(tmp_path: Path) -> Path:
    """Create a tiny RGB image to use as the matcher query image."""
    path = tmp_path / "query.jpg"
    Image.new("RGB", (64, 64), color=(200, 100, 50)).save(path, format="JPEG")
    return path


@pytest.fixture
def fake_wb_detail(wb_nm_id: int) -> Product:
    return Product(
        nmId=wb_nm_id,
        imtId=101,
        name="Тестовый фен",
        brand="TestBrand",
        price=1299.0,
        feedbacks=500,
        rating=4.7,
        img_url="https://wb.example/img.jpg",
        url=f"https://www.wildberries.ru/catalog/{wb_nm_id}/detail.aspx",
    )


@pytest.fixture
def fake_candidates() -> list[Candidate]:
    return [
        Candidate(
            site="alibaba",
            title="Фен A",
            url="https://alibaba.example/item-a",
            thumb_url="fixtures/dummy_query.jpg",
            price=1100.0,
            similarity=0.0,
            has_video=True,
            video_url="https://alibaba.example/video-a.mp4",
        ),
        Candidate(
            site="1688",
            title="Фен B",
            url="https://1688.example/item-b",
            thumb_url="fixtures/dummy_query.jpg",
            price=950.0,
            similarity=0.0,
            has_video=False,
            video_url=None,
        ),
    ]


@pytest.fixture
def fake_reviews() -> list[Review]:
    return [
        Review(
            id="R1",
            nmId=12345678,
            text="Шумит сильно",
            rating=3.0,
            date="2026-06-01",
            pros=[],
            cons=["Шумит"],
            video_url=None,
        ),
        Review(
            id="R2",
            nmId=12345678,
            text="Лёгкий и удобный",
            rating=5.0,
            date="2026-06-05",
            pros=["Лёгкий"],
            cons=[],
            video_url="https://wb.example/review-r2.mp4",
        ),
    ]


@pytest.fixture
def fake_llm_provider() -> LLMProvider:
    """Return a fake LLM provider that returns deterministic VoC/hooks JSON."""
    class FakeLLM(LLMProvider):
        def complete(self, messages: list[dict], **kw) -> str:
            prompt = " ".join(m.get("content", "") for m in messages)
            if "VoC" in prompt or "Проанализируй" in prompt or "боли" in prompt:
                return json.dumps(
                    {
                        "боли": [{"text": "Шумит", "frequency": 3, "quote": "Шумит сильно"}],
                        "желания": [{"text": "Лёгкий", "frequency": 2}],
                        "страхи": [{"text": "Сломается", "frequency": 1}],
                        "триггеры": [],
                        "восторги": [],
                        "возражения": [],
                        "язык_клиента": [],
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "hooks": [f"Hook {i}" for i in range(1, 6)],
                    "structure": [
                        {"scene": "Хук", "duration": "0-3s", "content": "Цепляем"}
                    ],
                    "objections": ["O1"],
                },
                ensure_ascii=False,
            )

        def close(self) -> None:
            pass

    return FakeLLM()


@pytest.fixture
def fake_matcher_pipeline(
    fake_wb_detail: Product,
    fake_candidates: list[Candidate],
    query_image: Path,
) -> Any:
    """Return a deterministic matcher pipeline that needs no network/browser."""

    def pipeline(query: str | Path) -> tuple[Product | None, list[Candidate]]:
        return fake_wb_detail, fake_candidates

    return pipeline


@pytest.fixture
def fake_downloader(tmp_path: Path) -> Any:
    """Return a downloader that writes a tiny fake mp4 file."""
    downloaded: list[tuple[str, int]] = []

    def downloader(url: str, nm_id: int) -> VideoAsset:
        downloaded.append((url, nm_id))
        target_dir = tmp_path / "video" / str(nm_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / "china_1.mp4"
        path.write_bytes(b"fake video bytes")
        return VideoAsset(
            source="china",
            nmId=nm_id,
            local_path=str(path),
            src_url=url,
            description=None,
        )

    downloader.downloaded = downloaded  # type: ignore[attr-defined]
    return downloader


class FakePage:
    """Minimal Flet page double."""

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


def test_e2e_matcher_happy_path(
    fake_matcher_pipeline: Any,
    fake_downloader: Any,
    wb_nm_id: int,
) -> None:
    """End-to-end: WB article -> candidates -> top candidate -> fake download."""
    page = FakePage()
    tab, controller = build_matcher_tab(
        page,
        matcher_pipeline=fake_matcher_pipeline,
        downloader=fake_downloader,
    )

    controller.input_field.value = str(wb_nm_id)
    controller._on_search(None)

    assert controller._last_product is not None
    assert controller._last_product.nmId == wb_nm_id
    assert len(controller._last_candidates) >= 1
    top = controller._last_candidates[0]
    assert top.video_url is not None

    controller._download_one(top)

    assert fake_downloader.downloaded == [(top.video_url, wb_nm_id)]
    assert "Скачано видео: 1" in controller.status_text.value


def test_e2e_matcher_ranker_orders_candidates(
    tmp_path: Path,
    fake_wb_detail: Product,
    query_image: Path,
) -> None:
    """End-to-end ranking: use the real ranker with fake images."""
    # Use two identical images so ranking produces deterministic high similarity.
    candidate = Candidate(
        site="alibaba",
        title="Фен A",
        url="https://alibaba.example/item-a",
        thumb_url=str(query_image),
        price=1100.0,
        similarity=0.0,
        has_video=True,
        video_url="https://alibaba.example/video-a.mp4",
    )

    ranked = rank_candidates(
        query_image,
        [candidate],
        use_clip=False,
        use_phash=True,
        similarity_threshold=0.0,
        max_candidates=10,
        use_cache=False,
    )

    assert len(ranked) == 1
    assert ranked[0].similarity > 0.95


def test_e2e_discovery_happy_path(
    fake_llm_provider: LLMProvider,
    fake_reviews: list[Review],
) -> None:
    """End-to-end: niche -> viral -> reviews -> VoC -> hooks -> videos."""
    from harvest.voc import analyze_reviews_voc
    from harvest.hooks import generate_hooks
    from harvest.review_video import extract_review_videos_from_reviews

    viral_product = ViralProduct(
        nmId=12345678,
        imtId=101,
        name="Тестовый фен",
        brand="TestBrand",
        price=1299.0,
        feedbacks=500,
        rating=4.7,
        viral_score=0.95,
    )

    voc = analyze_reviews_voc(fake_reviews, llm_provider=fake_llm_provider)
    assert any(item.text == "Шумит" for item in voc.боли)
    assert any(item.text == "Лёгкий" for item in voc.желания)

    hooks = generate_hooks(voc, nm_id=viral_product.nmId, llm_provider=fake_llm_provider)
    assert len(hooks.hooks) == 5
    assert hooks.structure

    videos = extract_review_videos_from_reviews(fake_reviews)
    assert len(videos) == 1
    assert videos[0].video_url == "https://wb.example/review-r2.mp4"


def test_e2e_discovery_gui_bridge_fills_matcher_input(
    fake_llm_provider: LLMProvider,
) -> None:
    """End-to-end GUI bridge: discovery selection -> matcher input field."""
    page = FakePage()
    matcher_tab, matcher_ctrl = build_matcher_tab(page)

    def discovery_service(query: str) -> ViralResult:
        return ViralResult(
            query=query,
            products=[
                ViralProduct(
                    nmId=111111,
                    imtId=201,
                    name="Фен bridge",
                    brand="B",
                    price=999.0,
                    feedbacks=100,
                    rating=4.6,
                    viral_score=0.9,
                )
            ],
        )

    def voc_service(nm_id: int) -> VoC:
        return VoC(
            боли=[VocItem(text="Шумит", frequency=1)],
            желания=[VocItem(text="Лёгкий", frequency=1)],
            страхи=[VocItem(text="Сломается", frequency=1)],
        )

    def hooks_service(nm_id: int, voc: VoC) -> VideoHookSet:
        return VideoHookSet(
            hooks=[f"Hook {i}" for i in range(1, 6)],
            structure=[],
            objections=[],
        )

    def review_video_service(nm_id: int) -> list[ReviewVideoItem]:
        return [
            ReviewVideoItem(
                review_id="R1",
                nmId=nm_id,
                rating=5.0,
                text="Класс",
                video_url="https://v/r1.mp4",
            )
        ]

    bridge_calls: list[int] = []

    def bridge(nm_id: int) -> None:
        bridge_calls.append(nm_id)
        matcher_ctrl.set_input_value(str(nm_id))

    discovery_tab, discovery_ctrl = build_discovery_tab(
        page,
        discovery_service=discovery_service,
        voc_service=voc_service,
        hooks_service=hooks_service,
        review_video_service=review_video_service,
        to_matcher_bridge=bridge,
    )

    discovery_ctrl.niche_input.value = "фен"
    discovery_ctrl._on_search(None)
    discovery_ctrl._select_product(discovery_ctrl._last_products[0])
    discovery_ctrl._on_to_matcher(None)

    assert bridge_calls == [111111]
    assert matcher_ctrl.input_field.value == "111111"


def test_e2e_create_app_three_tabs_with_fake_services(
    fake_matcher_pipeline: Any,
    fake_downloader: Any,
) -> None:
    """GUI integration: create_app accepts fake services and builds 3 tabs."""
    page = FakePage()

    def discovery_service(query: str) -> ViralResult:
        return ViralResult(query=query, products=[])

    shell = create_app(
        page,
        matcher_pipeline=fake_matcher_pipeline,
        downloader=fake_downloader,
        discovery_service=discovery_service,
        voc_service=lambda nm_id: VoC(),
        hooks_service=lambda nm_id, voc: VideoHookSet(hooks=[], structure=[], objections=[]),
        review_video_service=lambda nm_id: [],
    )

    assert shell.sections == ["matcher", "discovery", "settings"]
    assert shell.selected_section == "matcher"
    labels = [shell.section_labels[k] for k in shell.sections]
    assert labels == ["Матчер China", "Разведка WB", "Настройки"]


def test_e2e_fake_llm_not_real_llm(
    fake_llm_provider: LLMProvider,
) -> None:
    """Ensure the fake LLM is used and no real network call happens."""
    from harvest.voc import analyze_reviews_voc

    reviews = [
        Review(id="R1", nmId=1, text="Test", rating=5.0, date="2026-06-01")
    ]
    voc = analyze_reviews_voc(reviews, llm_provider=fake_llm_provider)
    assert isinstance(voc, VoC)
    assert "Шумит" in [item.text for item in voc.боли]


def _find_discovery_controller(tab: Any) -> DiscoveryWBController:
    for c in _flatten_controls(tab):
        if isinstance(c, ft.Column) and hasattr(c, "_discovery_controller"):
            return c._discovery_controller
    raise AssertionError("discovery controller not found")


def _find_matcher_input(tab: Any) -> ft.TextField:
    for c in _flatten_controls(tab):
        if isinstance(c, ft.TextField) and getattr(c, "label", None) == "Артикул/ссылка WB":
            return c
    raise AssertionError("matcher input not found")


def _flatten_controls(control: Any) -> list[Any]:
    result: list[Any] = [control]
    if hasattr(control, "content"):
        result.extend(_flatten_controls(control.content))
    if hasattr(control, "controls"):
        for child in control.controls:
            result.extend(_flatten_controls(child))
    return result


# ---------------------------------------------------------------------------
# Live smoke tests — gated by WB_RADAR_RUN_LIVE=1 and @pytest.mark.live.
# They are NOT run during normal `pytest -m "not live"`.
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_wb_to_discovery_smoke(tmp_path: Path) -> None:
    """Smoke test for real WB discovery.

    Requires WB_RADAR_RUN_LIVE=1. Skips by default.
    """
    if not os.environ.get("WB_RADAR_RUN_LIVE"):
        pytest.skip("Set WB_RADAR_RUN_LIVE=1 to run live tests")

    from harvest.discovery import niche

    result = niche("фен для волос", pages=1, top_n=2, output_root=tmp_path)
    assert result.products is not None
    # If WB blocks us, we still want a sensible result (likely empty).
    # We just verify the pipeline did not crash.


@pytest.mark.live
def test_live_matcher_one_product_smoke(query_image: Path) -> None:
    """Smoke test for real China matcher against one product.

    Requires WB_RADAR_RUN_LIVE=1 and a configured API/browser session.
    Skips by default. Does not bypass captcha/anti-bot.
    """
    if not os.environ.get("WB_RADAR_RUN_LIVE"):
        pytest.skip("Set WB_RADAR_RUN_LIVE=1 to run live tests")

    pytest.skip("live matcher requires manual login sessions — run separately")
