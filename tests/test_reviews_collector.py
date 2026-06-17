from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core.models import Product, Review
from harvest.discovery import ViralProduct
from harvest.reviews import (
    ProductInputError,
    ReviewCollectionResult,
    ReviewsCollectorError,
    collect_reviews_for_product,
    collect_reviews_for_products,
)


class FakeWBPublic:
    def __init__(
        self,
        reviews_by_imt: dict[int, list[Review]] | None = None,
        detail_by_nm: dict[int, Product] | None = None,
    ) -> None:
        self.reviews_by_imt = reviews_by_imt or {}
        self.detail_by_nm = detail_by_nm or {}
        self.search_calls: list[Any] = []
        self.detail_calls: list[int] = []
        self.review_calls: list[tuple[int, int]] = []
        self.closed = False

    def search(self, query: str, pages: int = 1) -> list[Product]:
        self.search_calls.append((query, pages))
        return []

    def get_detail(self, nmId: int) -> Product:
        self.detail_calls.append(nmId)
        if nmId in self.detail_by_nm:
            return self.detail_by_nm[nmId]
        raise RuntimeError(f"no detail for {nmId}")

    def get_reviews(self, imtId: int, max_count: int = 1000) -> list[Review]:
        self.review_calls.append((imtId, max_count))
        return list(self.reviews_by_imt.get(imtId, []))

    def close(self) -> None:
        self.closed = True


def _product(nm_id: int, imt_id: int | None, name: str = "P") -> Product:
    return Product(
        nmId=nm_id,
        imtId=imt_id,
        name=name,
        brand="B",
        price=100.0,
        feedbacks=10,
        rating=4.5,
        img_url=f"https://img/{nm_id}.jpg",
        url=f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
    )


def _review(rid: str, date: str = "2024-05-01") -> Review:
    return Review(
        id=rid,
        nmId=1,
        text=f"review {rid}",
        rating=5,
        date=date,
    )


def test_collect_reviews_for_two_products_creates_json_files(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    p2 = _product(2, 102)
    fake = FakeWBPublic(
        reviews_by_imt={
            101: [_review("R1"), _review("R2")],
            102: [_review("R3")],
        }
    )

    results = collect_reviews_for_products(
        [p1, p2],
        wb_client=fake,
        output_root=tmp_path,
        max_count=1000,
    )

    assert len(results) == 2
    assert all(r.status == "ok" for r in results)
    assert fake.review_calls == [(101, 1000), (102, 1000)]

    for r in results:
        assert r.output_path is not None
        path = Path(r.output_path)
        assert path.exists()
        assert path.parent.name == "reviews"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == r.reviews_count


def test_collect_reviews_uses_imt_id_and_skips_detail(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    fake = FakeWBPublic(
        reviews_by_imt={101: [_review("R1")]},
        detail_by_nm={1: _product(1, 999)},
    )

    result = collect_reviews_for_product(
        p1,
        wb_client=fake,
        output_root=tmp_path,
        max_count=1000,
    )

    assert result.status == "ok"
    assert result.imtId == 101
    assert result.reviews_count == 1
    assert fake.detail_calls == []
    assert fake.review_calls == [(101, 1000)]


def test_collect_reviews_resolves_imt_id_via_detail(tmp_path: Path) -> None:
    p1 = _product(1, None)
    resolved = _product(1, 101)
    fake = FakeWBPublic(
        reviews_by_imt={101: [_review("R1"), _review("R2")]},
        detail_by_nm={1: resolved},
    )

    result = collect_reviews_for_product(
        p1,
        wb_client=fake,
        output_root=tmp_path,
        max_count=500,
    )

    assert result.status == "ok"
    assert result.imtId == 101
    assert result.reviews_count == 2
    assert fake.detail_calls == [1]
    assert fake.review_calls == [(101, 500)]


def test_collect_reviews_accepts_nm_id_int(tmp_path: Path) -> None:
    resolved = _product(42, 101)
    fake = FakeWBPublic(
        reviews_by_imt={101: [_review("R1")]},
        detail_by_nm={42: resolved},
    )

    result = collect_reviews_for_product(
        42,
        wb_client=fake,
        output_root=tmp_path,
    )

    assert result.status == "ok"
    assert result.nmId == 42
    assert result.imtId == 101


def test_collect_reviews_accepts_viral_product(tmp_path: Path) -> None:
    viral = ViralProduct(
        nmId=5,
        imtId=105,
        name="V",
        feedbacks=10,
        rating=4.6,
    )
    fake = FakeWBPublic(reviews_by_imt={105: [_review("R1")]})

    result = collect_reviews_for_product(
        viral,
        wb_client=fake,
        output_root=tmp_path,
    )

    assert result.status == "ok"
    assert result.nmId == 5
    assert result.imtId == 105


def test_get_reviews_called_with_correct_imt_id_and_max_count(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    fake = FakeWBPublic(reviews_by_imt={101: []})

    collect_reviews_for_product(
        p1,
        wb_client=fake,
        output_root=tmp_path,
        max_count=250,
    )

    assert fake.review_calls == [(101, 250)]


def test_json_contains_list_of_reviews(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    fake = FakeWBPublic(reviews_by_imt={101: [_review("R1"), _review("R2")]})

    result = collect_reviews_for_product(
        p1,
        wb_client=fake,
        output_root=tmp_path,
    )

    assert result.output_path is not None
    data = json.loads(Path(result.output_path).read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["id"] == "R1"
    assert data[1]["id"] == "R2"
    # ensure_ascii=False: cyrillic text stored as-is
    assert "review" in data[0]["text"]


def test_empty_reviews_saved_as_empty_list(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    fake = FakeWBPublic(reviews_by_imt={101: []})

    result = collect_reviews_for_product(
        p1,
        wb_client=fake,
        output_root=tmp_path,
    )

    assert result.status == "ok"
    assert result.reviews_count == 0
    data = json.loads(Path(result.output_path).read_text(encoding="utf-8"))
    assert data == []


def test_error_in_one_product_does_not_fail_batch(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    p2 = _product(2, 102)
    fake = FakeWBPublic(
        reviews_by_imt={
            101: [_review("R1")],
        },
        detail_by_nm={2: _product(2, 102)},
    )

    def broken_get_reviews(imtId: int, max_count: int = 1000) -> list[Review]:
        if imtId == 102:
            raise RuntimeError("boom")
        return list(fake.reviews_by_imt.get(imtId, []))

    fake.get_reviews = broken_get_reviews

    results = collect_reviews_for_products(
        [p1, p2],
        wb_client=fake,
        output_root=tmp_path,
    )

    assert len(results) == 2
    statuses = {r.nmId: r.status for r in results}
    assert statuses[1] == "ok"
    assert statuses[2] == "error"
    assert any("boom" in (r.error or "") for r in results)


def test_collect_reviews_output_root_override(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    fake = FakeWBPublic(reviews_by_imt={101: [_review("R1")]})

    result = collect_reviews_for_product(
        p1,
        wb_client=fake,
        output_root=tmp_path,
    )

    assert result.output_path is not None
    assert str(tmp_path) in result.output_path
    assert Path(result.output_path).exists()


def test_collect_reviews_invalid_input_returns_error(tmp_path: Path) -> None:
    fake = FakeWBPublic()

    result = collect_reviews_for_product(
        None,
        wb_client=fake,
        output_root=tmp_path,
    )

    assert result.status == "error"
    assert result.error is not None


def test_collect_reviews_no_imt_id_after_detail_returns_error(tmp_path: Path) -> None:
    p1 = _product(1, None)
    resolved = _product(1, None)
    fake = FakeWBPublic(detail_by_nm={1: resolved})

    result = collect_reviews_for_product(
        p1,
        wb_client=fake,
        output_root=tmp_path,
    )

    assert result.status == "error"
    assert "no imtId available" in (result.error or "")


def test_collect_reviews_empty_products_returns_empty_list() -> None:
    fake = FakeWBPublic()
    assert collect_reviews_for_products([], wb_client=fake) == []


def test_collect_reviews_for_product_does_not_close_injected_client(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    fake = FakeWBPublic(reviews_by_imt={101: [_review("R1")]})

    collect_reviews_for_product(p1, wb_client=fake, output_root=tmp_path)

    assert fake.closed is False


def test_collect_reviews_for_product_closes_default_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p1 = _product(1, 101)
    fake = FakeWBPublic(reviews_by_imt={101: [_review("R1")]})
    monkeypatch.setattr("harvest.reviews.WBPublic", lambda: fake)

    collect_reviews_for_product(p1, wb_client=None, output_root=tmp_path)

    assert fake.closed is True


def test_collect_reviews_for_products_does_not_close_injected_client(tmp_path: Path) -> None:
    p1 = _product(1, 101)
    fake = FakeWBPublic(reviews_by_imt={101: [_review("R1")]})

    collect_reviews_for_products([p1], wb_client=fake, output_root=tmp_path)

    assert fake.closed is False


def test_review_collection_result_model() -> None:
    r = ReviewCollectionResult(nmId=1, imtId=101, reviews_count=5, status="ok")
    assert r.output_path is None
    assert r.error is None


def test_public_api_import() -> None:
    from harvest.reviews import collect_reviews_for_product, collect_reviews_for_products

    assert callable(collect_reviews_for_product)
    assert callable(collect_reviews_for_products)
