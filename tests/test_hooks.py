from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.models import Product, VocItem, VoC
from harvest.hooks import (
    VideoHookSet,
    build_hooks_prompt,
    generate_hooks,
    parse_hooks_response,
    save_hooks,
)


class FakeLLMProvider:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {
            "hooks": [
                "Боишься, что фен сожжёт волосы? Смотри проверку.",
                "Хочешь укладку за 5 минут — без салона?",
                "Муж купил дешёвый фен и пожалел. Этот другой.",
                "Волосы ломаются после каждой сушки? Есть решение.",
                "Почему блогеры молчат об этом фене?",
            ],
            "structure": [
                {"scene": "Хук", "duration": "0–3 сек", "content": "Страх сожженных волос"},
                {"scene": "Боль", "duration": "3–8 сек", "content": "Дешёвый фен портит волосы"},
                {"scene": "Демо", "duration": "8–20 сек", "content": "Фен в действии, результат"},
                {"scene": "Снятие возражений", "duration": "20–28 сек", "content": "Тихий, лёгкий, гарантия"},
                {"scene": "CTA", "duration": "28–30 сек", "content": "Ссылка в профиле"},
            ],
            "objections": [
                "Сожжёт ли волосы",
                "Шумный или тяжёлый",
                "Долго ли служит",
                "Оправдывает ли цена",
            ],
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


def _product() -> Product:
    return Product(
        nmId=42,
        imtId=101,
        name="Фен для волос",
        brand="BrandA",
        price=1299.0,
        feedbacks=512,
        rating=4.7,
        img_url="https://img/42.jpg",
        url="https://www.wildberries.ru/catalog/42/detail.aspx",
    )


def test_build_hooks_prompt_contains_voc_and_product() -> None:
    voc = _voc()
    product = _product()

    messages = build_hooks_prompt(voc, product=product)

    assert any(m["role"] == "system" for m in messages)
    content = " ".join(m.get("content", "") for m in messages)
    assert product.name in content
    assert "страхи" in content
    assert "Мощный поток" in content
    assert "hooks" in content
    assert "structure" in content


def test_build_hooks_prompt_without_product_still_valid() -> None:
    voc = _voc()
    messages = build_hooks_prompt(voc)
    content = " ".join(m.get("content", "") for m in messages)
    assert "Товар" not in content
    assert "VoC" in content


def test_generate_hooks_calls_fake_llm_and_saves_md(tmp_path: Path) -> None:
    voc = _voc()
    product = _product()
    fake = FakeLLMProvider()

    result = generate_hooks(
        voc,
        nm_id=42,
        product=product,
        llm_provider=fake,
        output_root=tmp_path,
    )

    assert len(fake.calls) == 1
    assert isinstance(result, VideoHookSet)
    assert len(result.hooks) == 5
    assert len(result.structure) == 5
    assert len(result.objections) == 4

    md_path = tmp_path / "hooks" / "42.md"
    assert md_path.exists()
    md_text = md_path.read_text(encoding="utf-8")
    assert "## Варианты хуков" in md_text
    assert "1. Боишься, что фен сожжёт волосы? Смотри проверку." in md_text
    assert "## Структура ролика" in md_text
    assert "| Хук |" in md_text
    assert "## Возражения для закрытия" in md_text
    assert "Сожжёт ли волосы" in md_text


def test_parse_hooks_response_valid() -> None:
    raw = {
        "hooks": ["A", "B", "C", "D", "E"],
        "structure": [
            {"scene": "Хук", "duration": "0–3 сек", "content": "A"},
            {"scene": "CTA", "duration": "28–30 сек", "content": "B"},
        ],
        "objections": ["O1", "O2"],
    }
    hook_set = parse_hooks_response(raw)
    assert hook_set.hooks == ["A", "B", "C", "D", "E"]
    assert len(hook_set.structure) == 2
    assert hook_set.structure[0].scene == "Хук"
    assert hook_set.objections == ["O1", "O2"]


def test_parse_hooks_response_incomplete_returns_fallback() -> None:
    hook_set = parse_hooks_response({"hooks": ["only one"]})
    assert len(hook_set.hooks) == 5
    assert hook_set.hooks[0] == "only one"
    assert all(isinstance(h, str) for h in hook_set.hooks)
    assert len(hook_set.structure) == 5
    assert hook_set.objections


def test_parse_hooks_response_malformed_returns_safe_fallback() -> None:
    hook_set = parse_hooks_response(None)
    assert len(hook_set.hooks) == 5
    assert len(hook_set.structure) == 5
    assert len(hook_set.objections) == 4


def test_parse_hooks_response_trims_extra_hooks() -> None:
    raw = {
        "hooks": ["A", "B", "C", "D", "E", "F"],
        "structure": [],
        "objections": [],
    }
    hook_set = parse_hooks_response(raw)
    assert hook_set.hooks == ["A", "B", "C", "D", "E"]


def test_save_hooks_creates_md_in_output_hooks(tmp_path: Path) -> None:
    hook_set = VideoHookSet(
        hooks=["H1", "H2", "H3", "H4", "H5"],
        structure=[],
        objections=["O1"],
    )
    path = save_hooks(7, hook_set, output_root=tmp_path)

    assert path.exists()
    assert path == tmp_path / "hooks" / "7.md"
    text = path.read_text(encoding="utf-8")
    assert "# Хуки и структура ролика (nmId 7)" in text
    assert "1. H1" in text


def test_generate_hooks_empty_voc_does_not_fail(tmp_path: Path) -> None:
    fake = FakeLLMProvider()

    result = generate_hooks(
        VoC(),
        nm_id=42,
        llm_provider=fake,
        output_root=tmp_path,
    )

    assert len(result.hooks) == 5
    assert (tmp_path / "hooks" / "42.md").exists()


def test_generate_hooks_uses_default_provider_on_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLLMProvider()
    monkeypatch.setattr("harvest.hooks.get_provider", lambda: fake)

    generate_hooks(_voc(), nm_id=1, llm_provider=None, output_root=tmp_path)

    assert len(fake.calls) == 1
    assert fake.closed is True


def test_generate_hooks_does_not_close_injected_provider(tmp_path: Path) -> None:
    fake = FakeLLMProvider()

    generate_hooks(_voc(), nm_id=1, llm_provider=fake, output_root=tmp_path)

    assert fake.closed is False


def test_generate_hooks_handles_broken_llm_response(tmp_path: Path) -> None:
    class BrokenLLM:
        def complete_json(self, messages, schema=None, *, json_retries=None, **kw):
            raise RuntimeError("llm down")

        def close(self) -> None:
            pass

    result = generate_hooks(
        _voc(),
        nm_id=1,
        llm_provider=BrokenLLM(),
        output_root=tmp_path,
    )

    assert isinstance(result, VideoHookSet)
    assert len(result.hooks) == 5
    assert (tmp_path / "hooks" / "1.md").exists()


def test_generate_hooks_without_nm_id_does_not_save(tmp_path: Path) -> None:
    fake = FakeLLMProvider()

    result = generate_hooks(_voc(), llm_provider=fake, output_root=tmp_path)

    assert len(result.hooks) == 5
    assert not (tmp_path / "hooks").exists()


def test_public_api_import() -> None:
    from harvest.hooks import generate_hooks, save_hooks, build_hooks_prompt

    assert callable(generate_hooks)
    assert callable(save_hooks)
    assert callable(build_hooks_prompt)
