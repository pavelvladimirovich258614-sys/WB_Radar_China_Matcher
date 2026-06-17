from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from core.models import Product, Review
from harvest.discovery import (
    ViralProduct,
    ViralResult,
    compute_viral_scores,
    count_reviews_since,
    niche,
    normalize_values,
    parse_review_date,
    rating_closeness,
)


class FakeWBPublic:
    def __init__(self, search_results: list[Product] | None = None) -> None:
        self.search_results = search_results or []
        self.reviews_by_imt: dict[int, list[Review]] = {}
        self.search_calls: list[tuple[str, int]] = []
        self.review_calls: list[tuple[int, int]] = []
        self.closed = False

    def search(self, query: str, sort: str = "popular", pages: int = 1) -> list[Product]:
        self.search_calls.append((query, pages))
        return list(self.search_results)

    def get_reviews(self, imtId: int, max_count: int = 1000) -> list[Review]:
        self.review_calls.append((imtId, max_count))
        return list(self.reviews_by_imt.get(imtId, []))

    def close(self) -> None:
        self.closed = True


def _product(
    nm_id: int,
    imt_id: int | None,
    feedbacks: int,
    rating: float,
    name: str = "Product",
) -> Product:
    return Product(
        nmId=nm_id,
        imtId=imt_id,
        name=name,
        brand="Brand",
        price=100.0,
        feedbacks=feedbacks,
        rating=rating,
        img_url=f"https://img/{nm_id}.jpg",
        url=f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
    )


def _review(date_iso: str, rating: float = 5.0) -> Review:
    return Review(
        id="R",
        nmId=1,
        text="ok",
        rating=rating,
        date=date_iso,
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2024-05-01T10:30:00", datetime(2024, 5, 1, 0, 0, tzinfo=timezone.utc)),
        ("2024-04-15T12:00:00", datetime(2024, 4, 15, 0, 0, tzinfo=timezone.utc)),
        ("2024-03-10", datetime(2024, 3, 10, 0, 0, tzinfo=timezone.utc)),
        ("2024-02-01", datetime(2024, 2, 1, 0, 0, tzinfo=timezone.utc)),
        ("", None),
        (None, None),
        ("not-a-date", None),
        ("01-05-2024", None),
    ],
)
def test_parse_review_date(value: Any, expected: datetime | None) -> None:
    assert parse_review_date(value) == expected


def test_parse_review_date_rejects_future_dates() -> None:
    now = datetime(2024, 5, 1, tzinfo=timezone.utc)
    assert parse_review_date("2024-06-01", now=now) is None


def test_count_reviews_since_7d_excludes_old_reviews() -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    reviews = [
        _review("2024-05-09"),  # 1 day ago -> in 7d
        _review("2024-05-03"),  # 7 days ago -> in 7d (>= cutoff)
        _review("2024-05-02"),  # 8 days ago -> out of 7d
        _review("2024-03-01"),  # old -> out
    ]
    assert count_reviews_since(reviews, 7, now=now) == 2


def test_count_reviews_since_30d() -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    reviews = [
        _review("2024-05-09"),
        _review("2024-04-15"),
        _review("2024-03-01"),
    ]
    assert count_reviews_since(reviews, 30, now=now) == 2


def test_count_reviews_since_zero_days_returns_zero() -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    reviews = [_review("2024-05-09")]
    assert count_reviews_since(reviews, 0, now=now) == 0


def test_normalize_values_deterministic() -> None:
    assert normalize_values([10.0, 20.0, 30.0]) == [0.0, 0.5, 1.0]
    assert normalize_values([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]
    assert normalize_values([100.0]) == [0.0]
    assert normalize_values([]) == []


def test_normalize_values_empty_and_uniform() -> None:
    assert normalize_values([]) == []
    assert normalize_values([42.0, 42.0]) == [0.0, 0.0]


def test_rating_closeness_max_at_target() -> None:
    assert rating_closeness(4.6) == pytest.approx(1.0)
    assert rating_closeness(5.0) == pytest.approx(1.0 - 0.4 / 1.4)
    assert rating_closeness(3.2) == pytest.approx(1.0 - 1.4 / 1.4)
    assert rating_closeness(3.1) == pytest.approx(0.0)
    assert rating_closeness(0.0) == pytest.approx(0.0)


def test_viral_score_sorts_products_correctly() -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    products = [
        (_product(1, 101, feedbacks=1000, rating=4.6, name="hot"), [
            _review("2024-05-09"),
            _review("2024-05-08"),
            _review("2024-05-07"),
        ]),
        (_product(2, 102, feedbacks=100, rating=4.5, name="warm"), [
            _review("2024-05-01"),
        ]),
        (_product(3, 103, feedbacks=10, rating=4.0, name="cold"), [
            _review("2024-01-01"),
        ]),
    ]
    scored = compute_viral_scores(products, now=now)
    assert len(scored) == 3
    assert scored[0].nmId == 1
    assert scored[0].viral_score == pytest.approx(1.0)
    assert scored[-1].nmId == 3


def test_compute_viral_scores_empty() -> None:
    assert compute_viral_scores([]) == []


def test_niche_calls_search_and_get_reviews(tmp_path: Path) -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    p1 = _product(1, 101, feedbacks=100, rating=4.6, name="A")
    p2 = _product(2, 102, feedbacks=50, rating=4.5, name="B")
    fake = FakeWBPublic([p1, p2])
    fake.reviews_by_imt[101] = [_review("2024-05-09")]
    fake.reviews_by_imt[102] = [_review("2024-04-01")]

    result = niche("фен", pages=1, top_n=2, wb_client=fake, output_root=tmp_path, now=now)

    assert isinstance(result, ViralResult)
    assert result.query == "фен"
    assert fake.search_calls == [("фен", 1)]
    assert (101, 1000) in fake.review_calls
    assert (102, 1000) in fake.review_calls
    assert len(result.products) == 2
    assert result.products[0].nmId == 1


def test_niche_top_n_limits_products(tmp_path: Path) -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    products = [
        _product(nm_id=i, imt_id=100 + i, feedbacks=i * 10, rating=4.6, name=f"P{i}")
        for i in range(1, 6)
    ]
    fake = FakeWBPublic(products)
    for p in products:
        fake.reviews_by_imt[p.imtId] = [_review("2024-05-09")]

    result = niche("фен", pages=1, top_n=3, wb_client=fake, output_root=tmp_path, now=now)

    assert len(result.products) == 3
    # top_n=3 selects the 3 products with the highest feedbacks: imtIds 105, 104, 103
    top_imt_ids = {call[0] for call in fake.review_calls}
    assert top_imt_ids == {103, 104, 105}


def test_niche_empty_search_returns_empty(tmp_path: Path) -> None:
    fake = FakeWBPublic([])
    result = niche("фен", pages=1, top_n=5, wb_client=fake, output_root=tmp_path)
    assert result.products == []
    assert result.csv_path is None


def test_niche_skips_product_without_imt_id(tmp_path: Path) -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    p1 = _product(1, None, feedbacks=100, rating=4.6, name="no imtId")
    p2 = _product(2, 102, feedbacks=50, rating=4.5, name="has imtId")
    fake = FakeWBPublic([p1, p2])
    fake.reviews_by_imt[102] = [_review("2024-05-09")]

    result = niche("фен", pages=1, top_n=5, wb_client=fake, output_root=tmp_path, now=now)

    assert len(result.products) == 1
    assert result.products[0].nmId == 2
    assert all(call[0] == 102 for call in fake.review_calls)


def test_niche_csv_export_created(tmp_path: Path) -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    p1 = _product(1, 101, feedbacks=100, rating=4.6, name="A")
    fake = FakeWBPublic([p1])
    fake.reviews_by_imt[101] = [_review("2024-05-09")]

    result = niche("фен для волос", pages=1, top_n=1, wb_client=fake, output_root=tmp_path, now=now)

    assert result.csv_path is not None
    csv_path = Path(result.csv_path)
    assert csv_path.exists()
    assert csv_path.parent.name == "viral"
    content = csv_path.read_text(encoding="utf-8")
    assert "nmId" in content
    assert "viral_score" in content
    assert "1" in content


def test_niche_creates_default_wbpublic_when_none_provided(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When wb_client is None, a WBPublic is created and closed."""
    p1 = _product(1, 101, feedbacks=10, rating=4.6, name="A")
    fake = FakeWBPublic([p1])
    fake.reviews_by_imt[101] = [_review("2024-05-09")]
    monkeypatch.setattr("harvest.discovery.WBPublic", lambda: fake)

    result = niche("фен", pages=1, top_n=1, wb_client=None, output_root=tmp_path)

    assert len(result.products) == 1
    assert fake.closed is True


def test_niche_does_not_close_injected_client(tmp_path: Path) -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    p1 = _product(1, 101, feedbacks=10, rating=4.6, name="A")
    fake = FakeWBPublic([p1])
    fake.reviews_by_imt[101] = [_review("2024-05-09")]

    niche("фен", pages=1, top_n=1, wb_client=fake, output_root=tmp_path, now=now)

    assert fake.closed is False


def test_niche_empty_query_returns_empty(tmp_path: Path) -> None:
    fake = FakeWBPublic([_product(1, 101, feedbacks=10, rating=4.6)])
    result = niche("", pages=1, top_n=5, wb_client=fake, output_root=tmp_path)
    assert result.products == []
    assert result.csv_path is None
    assert fake.search_calls == []


def test_niche_reviews_fetch_failure_is_logged_not_fatal(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    now = datetime(2024, 5, 10, tzinfo=timezone.utc)
    p1 = _product(1, 101, feedbacks=10, rating=4.6, name="A")

    class BrokenWBPublic(FakeWBPublic):
        def get_reviews(self, imtId: int, max_count: int = 1000) -> list[Review]:
            raise RuntimeError("boom")

    fake = BrokenWBPublic([p1])

    with caplog.at_level("WARNING", logger="harvest.discovery"):
        result = niche("фен", pages=1, top_n=1, wb_client=fake, output_root=tmp_path, now=now)

    # Failure is logged; the product is still included but with zero velocities.
    assert len(result.products) == 1
    assert result.products[0].velocity_7d == 0
    assert result.products[0].velocity_30d == 0
    assert any("boom" in rec.message for rec in caplog.records)


def test_viral_product_model() -> None:
    vp = ViralProduct(
        nmId=1,
        name="Test",
        feedbacks=10,
        rating=4.5,
        velocity_7d=5,
        velocity_30d=20,
        viral_score=0.75,
    )
    assert vp.brand == ""
    assert vp.viral_score == pytest.approx(0.75)


def test_viral_result_model() -> None:
    vr = ViralResult(query="фен", products=[], csv_path=None)
    assert vr.products == []


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("WB_TEST_DISCOVERY") != "1",
    reason="WB_TEST_DISCOVERY=1 required for live discovery test",
)
def test_niche_live_smoke(tmp_path: Path) -> None:
    """Optional live smoke test against real WB endpoints."""
    result = niche("фен", pages=1, top_n=3, wb_client=None, output_root=tmp_path)
    assert isinstance(result, ViralResult)
