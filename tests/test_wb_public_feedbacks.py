from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import pytest

from core.config import Settings
from core.models import Review
from core.wb_public import (
    WBParseError,
    WBPublic,
    WBRequestError,
    extract_review_photo_urls,
    extract_review_video_url,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "wb_feedbacks.json"


class FakeResponse:
    def __init__(self, status_code: int, payload: Optional[dict[str, Any]] = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        if self._payload is None:
            raise ValueError("no JSON payload")
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, dict[str, Any], dict[str, str]]] = []

    def post(
        self,
        url: str,
        *,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> FakeResponse:
        self.calls.append((url, dict(json or {}), dict(headers or {})))
        if self._index >= len(self._responses):
            response = self._responses[-1]
        else:
            response = self._responses[self._index]
        self._index += 1
        return response

    def close(self) -> None:
        pass


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fast_settings() -> Settings:
    settings = Settings()
    settings.wb.rate_limit_rps = 10000.0
    return settings


def _make_wb(responses: list[FakeResponse]) -> tuple[WBPublic, FakeClient]:
    client = FakeClient(responses)
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)
    return wb, client


def _make_feedbacks(count: int, start: int = 0) -> list[dict[str, Any]]:
    return [
        {"id": f"FB{start + i:04d}", "text": f"review {start + i}", "rating": 5, "createdDate": "2024-01-01"}
        for i in range(count)
    ]


def test_extract_review_video_url_supports_multiple_structures() -> None:
    assert extract_review_video_url({"video_url": "https://v/a.mp4"}) == "https://v/a.mp4"
    assert extract_review_video_url({"videoUrl": "https://v/b.mp4"}) == "https://v/b.mp4"
    assert extract_review_video_url({"video": "https://v/c.mp4"}) == "https://v/c.mp4"
    assert extract_review_video_url({"videos": [{"url": "https://v/d.mp4"}]}) == "https://v/d.mp4"
    assert extract_review_video_url(
        {"media": [{"type": "image", "url": "https://p/x.jpg"}, {"type": "video", "url": "https://v/e.mp4"}]}
    ) == "https://v/e.mp4"
    assert extract_review_video_url({"deep": {"nested": {"clip": "https://v/f.mp4"}}}) == "https://v/f.mp4"
    assert extract_review_video_url({"text": "no media"}) is None


def test_extract_review_photo_urls_supports_multiple_structures() -> None:
    dict_list = extract_review_photo_urls(
        {"photos": [{"full": "https://p/1.jpg", "large": "https://p/1l.jpg"}, {"full": "https://p/2.jpg"}]}
    )
    assert dict_list == ["https://p/1.jpg", "https://p/2.jpg"]

    str_list = extract_review_photo_urls({"photos": ["https://p/a.jpg", "https://p/b.jpg"]})
    assert str_list == ["https://p/a.jpg", "https://p/b.jpg"]

    photo_urls_key = extract_review_photo_urls({"photoUrls": ["https://p/c.jpg"]})
    assert photo_urls_key == ["https://p/c.jpg"]

    assert extract_review_photo_urls({"text": "no photos"}) == []
    assert extract_review_photo_urls({"photos": [{"full": "https://p/x.jpg"}, {"full": "https://p/x.jpg"}]}) == [
        "https://p/x.jpg"
    ]


def test_parse_fixture_returns_reviews() -> None:
    wb, _ = _make_wb([FakeResponse(200, _load_fixture())])

    reviews = wb.get_reviews(87654321, max_count=1000)

    assert len(reviews) == 5
    assert all(isinstance(r, Review) for r in reviews)

    by_id = {r.id: r for r in reviews}

    fb1 = by_id["FB001"]
    assert fb1.nmId == 12345678
    assert fb1.rating == 5.0
    assert fb1.date == "2024-05-01T10:30:00"
    assert fb1.text == "Отличный фен, мощный поток воздуха."
    assert fb1.pros == ["Мощный", "Лёгкий"]
    assert fb1.cons == ["Дорогой"]
    assert fb1.photo_urls == ["https://photos.wb.ru/v1/full1.jpg", "https://photos.wb.ru/v1/photo2.jpg"]
    assert fb1.video_url == "https://video.wb.ru/review1.mp4"


def test_reviews_cover_required_variants() -> None:
    wb, _ = _make_wb([FakeResponse(200, _load_fixture())])

    reviews = wb.get_reviews(87654321, max_count=1000)
    by_id = {r.id: r for r in reviews}

    assert by_id["FB002"].text == ""
    assert by_id["FB002"].video_url == "https://video.wb.ru/review2.mp4"

    assert by_id["FB003"].date == "2024-03-10"
    assert by_id["FB003"].cons == ["Слабый мотор", "Шумит"]

    fb4 = by_id["FB004"]
    assert fb4.video_url == "https://video.wb.ru/review3.mp4"
    assert fb4.photo_urls == ["https://photos.wb.ru/v2/p1.jpg", "https://photos.wb.ru/v2/p2.jpg"]

    video_reviews = [r for r in reviews if r.video_url]
    assert len(video_reviews) >= 3
    photo_reviews = [r for r in reviews if r.photo_urls]
    assert len(photo_reviews) >= 2

    fb5 = by_id["FB005"]
    assert fb5.video_url is None
    assert fb5.photo_urls == []
    assert fb5.date == ""
    assert fb5.nmId is None


def test_feedbacks_request_body_shape() -> None:
    wb, client = _make_wb([FakeResponse(200, {"data": {"feedbacks": []}})])

    wb.get_reviews(87654321, max_count=1000)

    assert len(client.calls) == 1
    url, body, _ = client.calls[0]
    assert url.endswith("/api/v1/feedbacks/site")
    assert body == {"imtId": 87654321, "take": 30, "skip": 0, "order": "dateDesc"}


def test_pagination_makes_multiple_requests() -> None:
    page1 = {"data": {"feedbacks": _make_feedbacks(30, start=0)}}
    page2 = {"data": {"feedbacks": _make_feedbacks(5, start=30)}}
    wb, client = _make_wb([FakeResponse(200, page1), FakeResponse(200, page2)])

    reviews = wb.get_reviews(87654321, max_count=1000)

    assert len(reviews) == 35
    assert len(client.calls) == 2
    assert client.calls[0][1]["skip"] == 0
    assert client.calls[1][1]["skip"] == 30


def test_max_count_limits_reviews_and_stops_early() -> None:
    page1 = {"data": {"feedbacks": _make_feedbacks(30, start=0)}}
    wb, client = _make_wb([FakeResponse(200, page1)])

    reviews = wb.get_reviews(87654321, max_count=10)

    assert len(reviews) == 10
    assert len(client.calls) == 1


def test_empty_result_returns_empty_list() -> None:
    wb, client = _make_wb([FakeResponse(200, {"data": {"feedbacks": []}})])

    reviews = wb.get_reviews(87654321, max_count=1000)

    assert reviews == []
    assert len(client.calls) == 1


def test_malformed_structure_raises_parse_error() -> None:
    wb, _ = _make_wb([FakeResponse(200, {"weird": True})])

    with pytest.raises(WBParseError):
        wb.get_reviews(87654321, max_count=1000)


def test_429_is_retried_then_raises_request_error() -> None:
    wb, client = _make_wb([FakeResponse(429), FakeResponse(429), FakeResponse(429)])

    with pytest.raises(WBRequestError):
        wb.get_reviews(87654321, max_count=1000)

    assert len(client.calls) == 3


def test_500_is_retried_then_raises_request_error() -> None:
    wb, client = _make_wb([FakeResponse(500), FakeResponse(503), FakeResponse(502)])

    with pytest.raises(WBRequestError):
        wb.get_reviews(87654321, max_count=1000)

    assert len(client.calls) == 3


def test_400_turns_into_request_error_without_fabricating_data() -> None:
    wb, client = _make_wb([FakeResponse(400), FakeResponse(400)])

    with pytest.raises(WBRequestError):
        wb.get_reviews(87654321, max_count=1000)

    assert len(client.calls) == 2


@pytest.mark.live
def test_get_reviews_live() -> None:
    imtid = os.environ.get("WB_TEST_IMTID")
    if not imtid:
        pytest.skip("WB_TEST_IMTID is not set")

    with WBPublic() as wb:
        reviews = wb.get_reviews(int(imtid), max_count=60)

    video_reviews = [r for r in reviews if r.video_url]
    print("imtId:", imtid)
    print("count:", len(reviews))
    print("with video_url:", len(video_reviews))
    if reviews:
        first = reviews[0]
        print("first.rating:", first.rating)
        print("first.date:", first.date)
        print("first.text:", first.text)
        print("first.pros:", first.pros)
        print("first.cons:", first.cons)
        print("first.video_url:", first.video_url)

    assert isinstance(reviews, list)
