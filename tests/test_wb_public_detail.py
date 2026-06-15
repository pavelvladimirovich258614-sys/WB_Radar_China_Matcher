from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import pytest

from core.config import Settings
from core.models import Product
from core.wb_public import (
    WBNotFoundError,
    WBParseError,
    WBPublic,
    WBRequestError,
    build_wb_image_url,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "wb_detail.json"
FIXTURE_NMID = 12345678


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
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


def test_parse_fixture_to_product() -> None:
    payload = _load_fixture()
    client = FakeClient([FakeResponse(200, payload)])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    product = wb.get_detail(FIXTURE_NMID)

    assert isinstance(product, Product)
    assert product.nmId == FIXTURE_NMID
    assert product.imtId == 87654321
    assert product.name == "Фен для волос мощный Professional"
    assert product.brand == "BrandX"
    assert product.price == 1990.0
    assert product.feedbacks == 120
    assert product.rating == 4.6
    assert product.url == f"https://www.wildberries.ru/catalog/{FIXTURE_NMID}/detail.aspx"
    assert product.img_url and str(FIXTURE_NMID) in product.img_url

    called_url, called_params, _ = client.calls[0]
    assert called_url.endswith("/cards/v2/detail")
    assert called_params["nm"] == str(FIXTURE_NMID)
    assert called_params["appType"] == 1
    assert called_params["curr"] == "rub"


def test_build_wb_image_url_contains_nmid_and_wb_shape() -> None:
    url_default = build_wb_image_url(FIXTURE_NMID)
    assert str(FIXTURE_NMID) in url_default
    assert "wbbasket.ru" in url_default
    assert "/images/big/1.jpg" in url_default
    assert "/vol123/" in url_default
    assert "/part12345/" in url_default
    assert url_default.startswith("https://basket-")

    url_custom = build_wb_image_url(FIXTURE_NMID, size="c516x688")
    assert "/images/c516x688/1.jpg" in url_custom

    big_nmid = 99_999_999
    big_url = build_wb_image_url(big_nmid)
    assert "basket-" in big_url
    assert str(big_nmid) in big_url


def test_empty_products_raises_not_found() -> None:
    client = FakeClient([FakeResponse(200, {"data": {"products": []}})])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    with pytest.raises(WBNotFoundError):
        wb.get_detail(FIXTURE_NMID)


def test_unexpected_structure_raises_parse_error() -> None:
    client = FakeClient([FakeResponse(200, {"weird": True})])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    with pytest.raises(WBParseError):
        wb.get_detail(FIXTURE_NMID)


def test_products_not_a_list_raises_parse_error() -> None:
    client = FakeClient([FakeResponse(200, {"data": {"products": "oops"}})])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    with pytest.raises(WBParseError):
        wb.get_detail(FIXTURE_NMID)


def test_429_is_retried_then_raises_request_error() -> None:
    client = FakeClient([FakeResponse(429), FakeResponse(429), FakeResponse(429)])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    with pytest.raises(WBRequestError):
        wb.get_detail(FIXTURE_NMID)

    assert len(client.calls) == 3


def test_500_is_retried_then_raises_request_error() -> None:
    client = FakeClient([FakeResponse(500), FakeResponse(503), FakeResponse(502)])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    with pytest.raises(WBRequestError):
        wb.get_detail(FIXTURE_NMID)

    assert len(client.calls) == 3


def test_400_refreshes_headers_once_then_raises_request_error() -> None:
    client = FakeClient([FakeResponse(400), FakeResponse(400)])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    with pytest.raises(WBRequestError):
        wb.get_detail(FIXTURE_NMID)

    assert len(client.calls) == 2
    _, _, first_headers = client.calls[0]
    _, _, second_headers = client.calls[1]
    assert "Referer" not in first_headers
    assert second_headers.get("Referer") == "https://www.wildberries.ru/"


def test_403_turns_into_request_error_without_fabricating_data() -> None:
    client = FakeClient([FakeResponse(403), FakeResponse(403)])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    with pytest.raises(WBRequestError):
        wb.get_detail(FIXTURE_NMID)


def test_400_then_200_recovers_after_header_refresh() -> None:
    payload = _load_fixture()
    client = FakeClient([FakeResponse(400), FakeResponse(200, payload)])
    wb = WBPublic(settings=_fast_settings(), client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    product = wb.get_detail(FIXTURE_NMID)

    assert product.nmId == FIXTURE_NMID
    assert product.imtId == 87654321
    assert len(client.calls) == 2


def test_request_uses_dest_from_settings_wb_dest() -> None:
    settings = _fast_settings()
    settings.wb.dest = "-777777"

    assert not hasattr(settings.wb.hosts, "dest")

    client = FakeClient([FakeResponse(200, _load_fixture())])
    wb = WBPublic(settings=settings, client=client, retry_wait_min=0.0, retry_wait_max=0.0)

    wb.get_detail(FIXTURE_NMID)

    _, params, _ = client.calls[0]
    assert params["dest"] == "-777777"


@pytest.mark.live
def test_get_detail_live() -> None:
    nmid = os.environ.get("WB_TEST_NMID")
    if not nmid:
        pytest.skip("WB_TEST_NMID is not set")

    with WBPublic() as wb:
        product = wb.get_detail(int(nmid))

    print("nmId:", product.nmId)
    print("imtId:", product.imtId)
    print("name:", product.name)
    print("brand:", product.brand)
    print("feedbacks:", product.feedbacks)
    print("rating:", product.rating)
    print("img_url:", product.img_url)

    assert product.nmId == int(nmid)
    assert product.imtId
    assert product.name
    assert product.img_url
