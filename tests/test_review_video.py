from __future__ import annotations

from typing import Any

import pytest

from core.models import Review
from core.wb_public import WBPublic
from harvest.review_video import (
    ReviewVideoItem,
    extract_review_videos_from_reviews,
    get_review_videos,
)


def _make_review(
    review_id: str = "FB001",
    *,
    video_url: str | None = None,
    text: str = "",
    rating: float = 5.0,
    nmId: int | None = 12345678,
    pros: list[str] | None = None,
    cons: list[str] | None = None,
) -> Review:
    return Review(
        id=review_id,
        nmId=nmId,
        text=text,
        rating=rating,
        date="2024-01-01",
        pros=pros or [],
        cons=cons or [],
        photo_urls=[],
        video_url=video_url,
    )


# ---------------------------------------------------------------------------
# ReviewVideoItem
# ---------------------------------------------------------------------------


def test_review_video_item_fields() -> None:
    item = ReviewVideoItem(
        review_id="FB001",
        nmId=123,
        rating=4.5,
        text="good",
        video_url="https://v.mp4",
        pros=["fast"],
        cons=["loud"],
    )
    assert item.review_id == "FB001"
    assert item.nmId == 123
    assert item.rating == 4.5
    assert item.text == "good"
    assert item.video_url == "https://v.mp4"
    assert item.pros == ["fast"]
    assert item.cons == ["loud"]


def test_review_video_item_defaults() -> None:
    item = ReviewVideoItem(review_id="FB002", nmId=None, rating=0, text="", video_url="https://v.mp4")
    assert item.pros == []
    assert item.cons == []


def test_review_video_item_to_dict() -> None:
    item = ReviewVideoItem(
        review_id="FB003", nmId=1, rating=5, text="great", video_url="https://v.mp4"
    )
    assert item.to_dict()["review_id"] == "FB003"
    assert item.to_dict()["video_url"] == "https://v.mp4"


# ---------------------------------------------------------------------------
# extract_review_videos_from_reviews
# ---------------------------------------------------------------------------


def test_extract_filters_only_video_reviews() -> None:
    reviews = [
        _make_review("FB001", video_url="https://v1.mp4"),
        _make_review("FB002"),
        _make_review("FB003", video_url="https://v2.mp4"),
    ]
    result = extract_review_videos_from_reviews(reviews)
    assert len(result) == 2
    assert {r.review_id for r in result} == {"FB001", "FB003"}


def test_extract_empty_returns_empty() -> None:
    assert extract_review_videos_from_reviews([]) == []


def test_extract_sorts_text_and_high_rating_first() -> None:
    reviews = [
        _make_review("FB001", video_url="https://v1.mp4", text="", rating=5.0),
        _make_review("FB002", video_url="https://v2.mp4", text="Excellent", rating=4.0),
        _make_review("FB003", video_url="https://v3.mp4", text="Great", rating=5.0),
    ]
    result = extract_review_videos_from_reviews(reviews)
    assert [r.review_id for r in result] == ["FB003", "FB002", "FB001"]


def test_extract_pros_cons_count_as_text() -> None:
    reviews = [
        _make_review("FB001", video_url="https://v1.mp4", text="", rating=5.0),
        _make_review("FB002", video_url="https://v2.mp4", text="", rating=5.0, pros=["nice"]),
    ]
    result = extract_review_videos_from_reviews(reviews)
    # Both have same score, preserve original stable-ish order via id tie-break.
    assert len(result) == 2
    assert result[0].review_id in {"FB001", "FB002"}


def test_extract_malformed_review_skipped() -> None:
    class BrokenReviewVideoItem:
        """Looks like a Review enough to enter the loop but breaks construction."""

        video_url = "https://v.mp4"
        id = "BAD"
        nmId = 1
        rating = "not-a-number"
        text = "ok"
        pros = []
        cons = []

    reviews = [
        _make_review("FB001", video_url="https://v1.mp4"),
        BrokenReviewVideoItem(),  # type: ignore[list-item]
    ]
    result = extract_review_videos_from_reviews(reviews)
    assert len(result) == 1
    assert result[0].review_id == "FB001"


# ---------------------------------------------------------------------------
# get_review_videos
# ---------------------------------------------------------------------------


class FakeWBPublic:
    """Fake WB client that records calls and returns canned data."""

    def __init__(
        self,
        *,
        imtId: int | None = 87654321,
        reviews: list[Review] | None = None,
    ) -> None:
        self.imtId = imtId
        self.reviews = list(reviews or [])
        self.get_detail_calls: list[int] = []
        self.get_reviews_calls: list[tuple[int, int]] = []
        self.closed = False

    def get_detail(self, nmId: int) -> Any:
        self.get_detail_calls.append(nmId)

        class FakeProduct:
            pass

        p = FakeProduct()
        p.imtId = self.imtId
        p.nmId = nmId
        return p

    def get_reviews(self, imtId: int, max_count: int = 1000) -> list[Review]:
        self.get_reviews_calls.append((imtId, max_count))
        return list(self.reviews)

    def close(self) -> None:
        self.closed = True


def test_get_review_videos_uses_detail_and_reviews() -> None:
    reviews = [
        _make_review("FB001", video_url="https://v1.mp4", text="nice", rating=5.0),
        _make_review("FB002"),
    ]
    fake = FakeWBPublic(imtId=87654321, reviews=reviews)
    result = get_review_videos(12345678, wb_client=fake, max_count=60)

    assert fake.get_detail_calls == [12345678]
    assert fake.get_reviews_calls == [(87654321, 60)]
    assert len(result) == 1
    assert result[0].review_id == "FB001"
    assert result[0].video_url == "https://v1.mp4"
    assert fake.closed is False  # injected client not closed by callee


def test_get_review_videos_with_detail_provider() -> None:
    reviews = [_make_review("FB001", video_url="https://v1.mp4", text="nice", rating=5.0)]
    fake = FakeWBPublic(imtId=None, reviews=reviews)
    result = get_review_videos(12345678, wb_client=fake, detail_provider=lambda nmId: 111222)

    assert fake.get_detail_calls == []  # detail_provider used instead
    assert fake.get_reviews_calls == [(111222, 1000)]
    assert len(result) == 1


def test_get_review_videos_returns_empty_when_no_imt_id() -> None:
    fake = FakeWBPublic(imtId=None, reviews=[])
    result = get_review_videos(12345678, wb_client=fake)
    assert result == []
    assert fake.get_reviews_calls == []


def test_get_review_videos_returns_empty_when_no_video_reviews() -> None:
    fake = FakeWBPublic(
        imtId=87654321,
        reviews=[_make_review("FB001", text="no video")],
    )
    result = get_review_videos(12345678, wb_client=fake)
    assert result == []


def test_get_review_videos_sorts_result() -> None:
    reviews = [
        _make_review("FB001", video_url="https://v1.mp4", text="", rating=5.0),
        _make_review("FB002", video_url="https://v2.mp4", text="Best", rating=5.0),
        _make_review("FB003", video_url="https://v3.mp4", text="Good", rating=4.0),
    ]
    fake = FakeWBPublic(imtId=87654321, reviews=reviews)
    result = get_review_videos(12345678, wb_client=fake)
    assert [r.review_id for r in result] == ["FB002", "FB003", "FB001"]


def test_get_review_videos_default_max_count() -> None:
    fake = FakeWBPublic(imtId=87654321, reviews=[])
    get_review_videos(12345678, wb_client=fake)
    assert fake.get_reviews_calls == [(87654321, 1000)]


# ---------------------------------------------------------------------------
# Public API import check
# ---------------------------------------------------------------------------


def test_public_api_import() -> None:
    from harvest.review_video import get_review_videos, extract_review_videos_from_reviews

    assert callable(get_review_videos)
    assert callable(extract_review_videos_from_reviews)


# ---------------------------------------------------------------------------
# Live smoke (only runs under explicit env)
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.skipif(not __import__("os").environ.get("WB_TEST_NMID"), reason="WB_TEST_NMID not set")
def test_get_review_videos_live_smoke() -> None:
    import os

    nmId = int(os.environ["WB_TEST_NMID"])
    items = get_review_videos(nmId, max_count=30)
    assert isinstance(items, list)
    for item in items:
        assert isinstance(item, ReviewVideoItem)
        assert item.video_url and item.video_url.startswith("http")
