from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core.models import Product, VideoAsset, VocItem, VoC
from harvest.describe import (
    VideoDescription,
    build_description_prompt,
    describe_video,
    parse_description_response,
    save_description,
)


class FakeLLMProvider:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {
            "title": "Лучший фен для волос",
            "description": "Мощный поток, лёгкий корпус. Идеален для ежедневной укладки.",
            "captions": [
                "Мощный фен без лишнего веса — проверь сам",
                "Секрет быстрой укладки каждое утро",
                "Почему этот фен разбирают в отзывах",
            ],
            "tags": ["фен", "укладка", "волосы", "красота", "wb"],
        }
        self.calls: list[list[dict[str, str]]] = []
        self.closed = False

    def complete_json(
        self,
        messages: list[dict],
        schema: dict[str, Any] | None = None,
        *,
        json_retries: int | None = None,
        **kw: Any,
    ) -> dict[str, Any]:
        self.calls.append(messages)
        return dict(self.response)

    def close(self) -> None:
        self.closed = True


def _video_asset(nm_id: int = 42) -> VideoAsset:
    return VideoAsset(
        source="china",
        nmId=nm_id,
        local_path=f"output/video/{nm_id}/china_1.mp4",
        src_url="https://video.cdn/v.mp4",
        description=None,
    )


def _product(nm_id: int = 42) -> Product:
    return Product(
        nmId=nm_id,
        imtId=101,
        name="Фен для волос",
        brand="BrandA",
        price=1299.0,
        feedbacks=512,
        rating=4.7,
        img_url=f"https://img/{nm_id}.jpg",
        url=f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
    )


def _voc() -> VoC:
    return VoC(
        боли=[VocItem(text="Шумит", frequency=5, quote="шумит")],
        желания=[VocItem(text="Лёгкий", frequency=3)],
        страхи=[VocItem(text="Сломается", frequency=2)],
        триггеры=[VocItem(text="Быстрая доставка", frequency=4)],
        восторги=[VocItem(text="Мощный поток", frequency=7)],
        возражения=[VocItem(text="Дорогой", frequency=3)],
        язык_клиента=[VocItem(text="Огонь", frequency=2)],
    )


def test_build_description_prompt_contains_product_voc_and_video() -> None:
    video = _video_asset()
    product = _product()
    voc = _voc()

    messages = build_description_prompt(video, product, voc)

    assert any(m["role"] == "system" for m in messages)
    content = " ".join(m.get("content", "") for m in messages)
    assert product.name in content
    assert video.source in content
    assert "боли" in content
    assert "Мощный поток" in content
    assert "title" in content
    assert "captions" in content


def test_describe_video_calls_fake_llm_and_saves_files(tmp_path: Path) -> None:
    video = _video_asset()
    product = _product()
    voc = _voc()
    fake = FakeLLMProvider()

    result = describe_video(
        video,
        product,
        voc,
        llm_provider=fake,
        output_root=tmp_path,
    )

    assert len(fake.calls) == 1
    assert isinstance(result, VideoDescription)
    assert result.title == "Лучший фен для волос"
    assert len(result.captions) == 3
    assert result.tags

    json_path = tmp_path / "video" / "42" / "description.json"
    md_path = tmp_path / "video" / "42" / "description.md"
    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["title"] == result.title
    assert data["captions"] == result.captions

    md_text = md_path.read_text(encoding="utf-8")
    assert "# Лучший фен для волос" in md_text
    assert "1. " in md_text
    assert "## Теги" in md_text


def test_parse_description_response_valid() -> None:
    raw = {
        "title": "Title",
        "description": "Desc",
        "captions": ["A", "B", "C"],
        "tags": ["tag1", "tag2"],
    }
    desc = parse_description_response(raw)
    assert desc.title == "Title"
    assert desc.description == "Desc"
    assert desc.captions == ["A", "B", "C"]
    assert desc.tags == ["tag1", "tag2"]


def test_parse_description_response_incomplete_returns_fallback() -> None:
    desc = parse_description_response({"title": "Only title"})
    assert desc.title == "Only title"
    assert desc.description == ""
    assert len(desc.captions) == 3
    assert desc.captions == ["", "", ""]
    assert desc.tags == []


def test_parse_description_response_malformed_returns_safe_fallback() -> None:
    desc = parse_description_response(None)
    assert desc.title == "Описание видео"
    assert len(desc.captions) == 3


def test_parse_description_response_trims_extra_captions() -> None:
    raw = {
        "title": "T",
        "description": "D",
        "captions": ["A", "B", "C", "D", "E"],
        "tags": ["t"],
    }
    desc = parse_description_response(raw)
    assert desc.captions == ["A", "B", "C"]


def test_save_description_creates_json_and_md(tmp_path: Path) -> None:
    desc = VideoDescription(
        title="T",
        description="D",
        captions=["A", "B", "C"],
        tags=["t1", "t2"],
    )
    json_path, md_path = save_description(7, desc, output_root=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert json_path.parent.name == "7"
    assert md_path.name == "description.md"


def test_describe_video_empty_voc_does_not_fail(tmp_path: Path) -> None:
    video = _video_asset()
    product = _product()
    fake = FakeLLMProvider()

    result = describe_video(
        video,
        product,
        VoC(),
        llm_provider=fake,
        output_root=tmp_path,
    )

    assert result.title
    assert len(result.captions) == 3
    assert (tmp_path / "video" / "42" / "description.json").exists()


def test_describe_video_uses_default_provider_on_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = _video_asset()
    product = _product()
    voc = _voc()
    fake = FakeLLMProvider()
    monkeypatch.setattr("harvest.describe.get_provider", lambda: fake)

    describe_video(video, product, voc, llm_provider=None, output_root=tmp_path)

    assert len(fake.calls) == 1
    assert fake.closed is True


def test_describe_video_does_not_close_injected_provider(tmp_path: Path) -> None:
    video = _video_asset()
    product = _product()
    voc = _voc()
    fake = FakeLLMProvider()

    describe_video(video, product, voc, llm_provider=fake, output_root=tmp_path)

    assert fake.closed is False


def test_describe_video_handles_broken_llm_response(tmp_path: Path) -> None:
    class BrokenLLM:
        def complete_json(self, messages, schema=None, *, json_retries=None, **kw):
            raise RuntimeError("llm down")

        def close(self) -> None:
            pass

    video = _video_asset()
    product = _product()
    voc = _voc()

    result = describe_video(
        video,
        product,
        voc,
        llm_provider=BrokenLLM(),
        output_root=tmp_path,
    )

    assert isinstance(result, VideoDescription)
    assert len(result.captions) == 3
    assert (tmp_path / "video" / "42" / "description.json").exists()


def test_public_api_import() -> None:
    from harvest.describe import describe_video, build_description_prompt, save_description

    assert callable(describe_video)
    assert callable(build_description_prompt)
    assert callable(save_description)
