from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import pytest

from core.config import Settings
from core.models import Product
from core.wb_public import WBParseError, WBPublic, WBRequestError

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "wb_search.json"


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

    def get(
        self,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> FakeResponse:
        self.calls.append((url, dict(params or {}), dict(headers or {})))
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


def test_parse_fixture_returns_products() -> None:
    wb, _ = _make_wb([FakeResponse(200, _load_fixture())])

    products = wb.search("фен", pages=1)

    assert len(products) == 5
    assert all(isinstance(p, Product) for p in products)

    by_id = {p.nmId: p for p in products}

    first = by_id[10000001]
    assert first.imtId == 20000001
    assert first.name == "Фен для волос profesionalный BrandA"
    assert first.brand == "BrandA"
    assert first.price == 890.0
    assert first.feedbacks == 512
    assert first.rating == 4.7
    assert first.url == "https://www.wildberries.ru/catalog/10000001/detail.aspx"
    assert first.img_url and "10000001" in first.img_url

    no_root = by_id[10000003]
    assert no_root.imtId is None
    assert no_root.feedbacks == 0
    assert no_root.rating == 0.0


def test_every_product_has_required_fields() -> None:
    wb, _ = _make_wb([FakeResponse(200, _load_fixture())])

    products = wb.search("фен", pages=1)

    assert products
    for product in products:
        assert product.nmId
        assert product.name
        assert product.brand
        assert product.price >= 0
        assert product.feedbacks >= 0
        assert 0.0 <= product.rating <= 5.0
        assert product.img_url and str(product.nmId) in product.img_url
        assert product.url.startswith("https://www.wildberries.ru/catalog/")


def test_pages_param_triggers_multiple_requests() -> None:
    page1 = {
        "data": {
            "products": [
                {"id": 11, "root": 111, "name": "A", "brand": "B", "salePriceU": 1000, "feedbacks": 1, "rating": 4.0},
                {"id": 12, "root": 112, "name": "C", "brand": "D", "salePriceU": 2000, "feedbacks": 2, "rating": 4.1},
                {"id": 13, "root": 113, "name": "E", "brand": "F", "salePriceU": 3000, "feedbacks": 3, "rating": 4.2},
            ]
        }
    }
    page2 = {
        "data": {
            "products": [
                {"id": 21, "root": 211, "name": "G", "brand": "H", "salePriceU": 4000, "feedbacks": 4, "rating": 4.3},
                {"id": 22, "root": 212, "name": "I", "brand": "J", "salePriceU": 5000, "feedbacks": 5, "rating": 4.4},
            ]
        }
    }
    wb, client = _make_wb([FakeResponse(200, page1), FakeResponse(200, page2)])

    products = wb.search("запрос", pages=2)

    assert len(products) == 5
    assert len(client.calls) == 2
    assert client.calls[0][1]["page"] == 1
    assert client.calls[1][1]["page"] == 2
    for url, _, _ in client.calls:
        assert url.endswith("/exactmatch/ru/common/v4/search")
        assert "search.wb.ru" in url


def test_empty_result_returns_empty_list() -> None:
    wb, client = _make_wb([FakeResponse(200, {"data": {"products": []}})])

    products = wb.search("несуществующий запрос", pages=1)

    assert products == []
    assert len(client.calls) == 1


def test_empty_page_stops_pagination_early() -> None:
    page1 = {"data": {"products": [{"id": 11, "name": "A", "brand": "B", "salePriceU": 1000, "feedbacks": 1, "rating": 4.0}]}}
    empty = {"data": {"products": []}}
    wb, client = _make_wb([FakeResponse(200, page1), FakeResponse(200, empty), FakeResponse(200, empty)])

    products = wb.search("запрос", pages=3)

    assert len(products) == 1
    assert len(client.calls) == 2


def test_unexpected_structure_raises_parse_error() -> None:
    wb, _ = _make_wb([FakeResponse(200, {"weird": True})])

    with pytest.raises(WBParseError):
        wb.search("запрос", pages=1)


def test_429_is_retried_then_raises_request_error() -> None:
    wb, client = _make_wb([FakeResponse(429), FakeResponse(429), FakeResponse(429)])

    with pytest.raises(WBRequestError):
        wb.search("запрос", pages=1)

    assert len(client.calls) == 3


def test_500_is_retried_then_raises_request_error() -> None:
    wb, client = _make_wb([FakeResponse(500), FakeResponse(503), FakeResponse(502)])

    with pytest.raises(WBRequestError):
        wb.search("запрос", pages=1)

    assert len(client.calls) == 3


def test_400_turns_into_request_error_without_fabricating_data() -> None:
    wb, client = _make_wb([FakeResponse(400), FakeResponse(400)])

    with pytest.raises(WBRequestError):
        wb.search("запрос", pages=1)

    assert len(client.calls) == 2


@pytest.mark.live
def test_search_live() -> None:
    query = os.environ.get("WB_TEST_QUERY")
    if not query:
        pytest.skip("WB_TEST_QUERY is not set")

    with WBPublic() as wb:
        products = wb.search(query, pages=1)

    print("query:", query)
    print("count:", len(products))
    if products:
        first = products[0]
        print("nmId:", first.nmId)
        print("imtId:", first.imtId)
        print("name:", first.name)
        print("brand:", first.brand)
        print("feedbacks:", first.feedbacks)
        print("rating:", first.rating)
        print("img_url:", first.img_url)

    assert isinstance(products, list)
