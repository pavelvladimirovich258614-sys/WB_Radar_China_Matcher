from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core.models import Review, VocItem, VoC
from harvest.voc import (
    analyze_reviews_voc,
    analyze_voc_for_nmId,
    build_voc_prompt,
    chunk_reviews,
    dedupe_voc_items,
    load_reviews_for_voc,
    merge_voc_results,
    save_voc,
)


class FakeLLMProvider:
    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.responses = list(responses or [])
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
        if self.responses:
            return self.responses.pop(0)
        return _empty_voc_dict()

    def close(self) -> None:
        self.closed = True


def _empty_voc_dict() -> dict[str, Any]:
    return {
        "боли": [],
        "желания": [],
        "страхи": [],
        "триггеры": [],
        "восторги": [],
        "возражения": [],
        "язык_клиента": [],
    }


def _voc_dict_with(category: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    d = _empty_voc_dict()
    d[category] = items
    return d


def _review(rid: str, text: str = "ok", rating: float = 5.0) -> Review:
    return Review(id=rid, nmId=1, text=text, rating=rating)


def test_chunk_reviews_splits_by_batch_size() -> None:
    reviews = [_review(f"R{i}") for i in range(85)]
    chunks = chunk_reviews(reviews, batch_size=40)
    assert len(chunks) == 3
    assert len(chunks[0]) == 40
    assert len(chunks[1]) == 40
    assert len(chunks[2]) == 5


def test_analyze_reviews_voc_calls_fake_llm_per_batch() -> None:
    reviews = [_review(f"R{i}") for i in range(85)]
    fake = FakeLLMProvider()

    analyze_reviews_voc(reviews, llm_provider=fake, batch_size=40)

    assert len(fake.calls) == 3


def test_analyze_reviews_voc_returns_valid_voc() -> None:
    reviews = [_review("R1", "очень мощный фен"), _review("R2", "легкий и удобный")]
    fake = FakeLLMProvider([
        _voc_dict_with("восторги", [
            {"text": "Мощный", "frequency": 1, "quote": "очень мощный фен", "source_review_ids": ["R1"]},
            {"text": "Легкий", "frequency": 1, "quote": "легкий и удобный", "source_review_ids": ["R2"]},
        ]),
    ])

    voc = analyze_reviews_voc(reviews, llm_provider=fake, batch_size=40)

    assert isinstance(voc, VoC)
    assert len(voc.восторги) == 2
    texts = {item.text for item in voc.восторги}
    assert texts == {"Мощный", "Легкий"}


def test_merge_voc_results_combines_categories() -> None:
    v1 = VoC(
        боли=[VocItem(text="Шумит", frequency=2)],
        желания=[VocItem(text="Легкий", frequency=1)],
    )
    v2 = VoC(
        боли=[VocItem(text="Шумит", frequency=1)],
        восторги=[VocItem(text="Мощный", frequency=3)],
    )

    merged = merge_voc_results([v1, v2])

    assert len(merged.боли) == 1
    assert merged.боли[0].frequency == 3
    assert len(merged.желания) == 1
    assert len(merged.восторги) == 1


def test_dedupe_voc_items_sums_frequency_and_merges_sources() -> None:
    items = [
        VocItem(text="Шумит", frequency=1, source_review_ids=["R1"], quote="шумит"),
        VocItem(text="шумит", frequency=2, source_review_ids=["R2"], quote="шумит сильно"),
        VocItem(text="Дорогой", frequency=1),
    ]

    deduped = dedupe_voc_items(items)

    assert len(deduped) == 2
    шумит = next(i for i in deduped if i.text == "Шумит")
    assert шумит.frequency == 3
    assert sorted(шумит.source_review_ids) == ["R1", "R2"]


def test_dedupe_voc_items_sorts_by_frequency_desc() -> None:
    items = [
        VocItem(text="A", frequency=1),
        VocItem(text="B", frequency=3),
        VocItem(text="C", frequency=2),
    ]
    deduped = dedupe_voc_items(items)
    assert [i.text for i in deduped] == ["B", "C", "A"]


def test_analyze_reviews_voc_empty_reviews_returns_empty_voc() -> None:
    fake = FakeLLMProvider()
    voc = analyze_reviews_voc([], llm_provider=fake, batch_size=40)
    assert isinstance(voc, VoC)
    assert voc.боли == []
    assert fake.calls == []


def test_save_voc_creates_output_voc_json(tmp_path: Path) -> None:
    voc = VoC(
        боли=[VocItem(text="Шумит", frequency=2, quote="шумит")],
        желания=[VocItem(text="Легкий", frequency=1)],
    )
    path = save_voc(12345, voc, output_root=tmp_path)

    assert path.exists()
    assert path.parent.name == "voc"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["боли"][0]["text"] == "Шумит"
    assert data["боли"][0]["quote"] == "шумит"
    assert data["боли"][0]["frequency"] == 2


def test_load_reviews_for_voc_from_path(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    reviews_dir.mkdir(parents=True)
    reviews_file = reviews_dir / "42.json"
    reviews_file.write_text(
        json.dumps(
            [
                {"id": "R1", "nmId": 42, "text": "отлично", "rating": 5},
                {"id": "R2", "nmId": 42, "text": "плохо", "rating": 2},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    reviews, nm_id = load_reviews_for_voc(tmp_path / "reviews" / "42.json")

    assert len(reviews) == 2
    assert nm_id == 42
    assert reviews[0].text == "отлично"


def test_load_reviews_for_voc_from_nm_id(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    reviews_dir.mkdir(parents=True)
    (reviews_dir / "7.json").write_text(
        json.dumps([{"id": "R1", "nmId": 7, "text": "ok", "rating": 5}], ensure_ascii=False),
        encoding="utf-8",
    )

    reviews, nm_id = load_reviews_for_voc(7, output_root=tmp_path)

    assert len(reviews) == 1
    assert nm_id == 7


def test_load_reviews_for_voc_from_reviews_list() -> None:
    reviews = [_review("R1", "text")]
    loaded, nm_id = load_reviews_for_voc(reviews=reviews)
    assert loaded == reviews
    assert nm_id is None


def test_analyze_voc_for_nmId_pipeline(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    reviews_dir.mkdir(parents=True)
    (reviews_dir / "9.json").write_text(
        json.dumps([{"id": "R1", "nmId": 9, "text": "очень мощный", "rating": 5}], ensure_ascii=False),
        encoding="utf-8",
    )
    fake = FakeLLMProvider([
        _voc_dict_with("восторги", [{"text": "Мощный", "frequency": 1, "quote": "очень мощный", "source_review_ids": ["R1"]}]),
    ])

    voc = analyze_voc_for_nmId(
        9,
        llm_provider=fake,
        output_root=tmp_path,
        batch_size=40,
    )

    assert isinstance(voc, VoC)
    assert len(voc.восторги) == 1
    voc_path = tmp_path / "voc" / "9.json"
    assert voc_path.exists()
    data = json.loads(voc_path.read_text(encoding="utf-8"))
    assert data["восторги"][0]["text"] == "Мощный"


def test_build_voc_prompt_contains_reviews_and_schema() -> None:
    reviews = [_review("R1", "очень хорошо")]
    messages = build_voc_prompt(reviews)
    assert any(m["role"] == "system" for m in messages)
    assert any("очень хорошо" in m.get("content", "") for m in messages)
    assert any("боли" in m.get("content", "") for m in messages)


def test_parse_voc_response_skips_invalid_items() -> None:
    raw = {
        "боли": [
            {"text": "Шумит", "frequency": 2},
            {"frequency": 1},  # no text — skipped
            "not a dict",  # skipped
        ],
        "желания": [],
        "страхи": [],
        "триггеры": [],
        "восторги": [],
        "возражения": [],
        "язык_клиента": [],
    }
    from harvest.voc import _parse_voc_response

    voc = _parse_voc_response(raw)
    assert len(voc.боли) == 1
    assert voc.боли[0].text == "Шумит"


def test_analyze_reviews_voc_handles_llm_failure() -> None:
    class BrokenLLM:
        def complete_json(self, messages, schema=None, *, json_retries=None, **kw):
            raise RuntimeError("llm down")

        def close(self) -> None:
            pass

    reviews = [_review("R1")]
    voc = analyze_reviews_voc(reviews, llm_provider=BrokenLLM(), batch_size=40)
    assert isinstance(voc, VoC)
    assert voc.боли == []


def test_analyze_reviews_voc_does_not_close_injected_provider() -> None:
    reviews = [_review("R1")]
    fake = FakeLLMProvider()
    analyze_reviews_voc(reviews, llm_provider=fake, batch_size=40)
    assert fake.closed is False


def test_analyze_reviews_voc_closes_default_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews = [_review("R1")]
    fake = FakeLLMProvider()
    monkeypatch.setattr("harvest.voc.get_provider", lambda: fake)
    analyze_reviews_voc(reviews, llm_provider=None, batch_size=40)
    assert fake.closed is True


def test_public_api_import() -> None:
    from harvest.voc import analyze_reviews_voc, analyze_voc_for_nmId, merge_voc_results

    assert callable(analyze_reviews_voc)
    assert callable(analyze_voc_for_nmId)
    assert callable(merge_voc_results)


def test_voc_item_has_quote_and_source_ids() -> None:
    item = VocItem(text="Шум", frequency=1, quote="шумит", source_review_ids=["R1"])
    assert item.quote == "шумит"
    assert item.source_review_ids == ["R1"]


def test_empty_voc_model() -> None:
    voc = VoC()
    assert voc.боли == []
    assert voc.язык_клиента == []
