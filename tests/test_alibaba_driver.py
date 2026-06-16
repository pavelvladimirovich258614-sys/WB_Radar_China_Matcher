from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.models import Candidate
from core.storage import Storage
from matcher.china.alibaba import (
    AlibabaCaptchaError,
    AlibabaImageSearchDriver,
    AlibabaLoginRequiredError,
    AlibabaNoResultsError,
    AlibabaSearchError,
    parse_results_html,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
RESULTS_HTML = FIXTURES / "alibaba_search_results.html"
CAPTCHA_HTML = FIXTURES / "alibaba_captcha.html"
LOGIN_HTML = FIXTURES / "alibaba_login.html"
EMPTY_HTML = FIXTURES / "alibaba_empty.html"
DUMMY_IMAGE = FIXTURES / "dummy_query.jpg"


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    return Storage(db_path=tmp_path / "cache.db", output_dir=tmp_path / "output")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_parse_results_finds_candidates() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html)

    assert len(candidates) == 3

    assert candidates[0].site == "alibaba"
    assert candidates[0].title == "Wireless Bluetooth Earbuds TWS"
    assert candidates[0].url == "https://www.alibaba.com/product-detail/Wireless-Bluetooth-Earbuds_123456789.html"
    assert candidates[0].thumb_url.startswith("https://")
    assert candidates[0].thumb_url.endswith("Hb1e2c3d4e5f6789abcdef0123456789.jpg")
    assert candidates[0].price == 2.5
    assert candidates[0].has_video is False

    assert candidates[1].title == "Bluetooth Headphones Over Ear"
    assert candidates[1].price == 5.2

    assert candidates[2].title == "Mini TWS Earbuds with Video"
    assert candidates[2].has_video is True


def test_parse_results_detects_captcha() -> None:
    with pytest.raises(AlibabaCaptchaError):
        parse_results_html(_read_text(CAPTCHA_HTML))


def test_parse_results_detects_login() -> None:
    with pytest.raises(AlibabaLoginRequiredError):
        parse_results_html(_read_text(LOGIN_HTML))


def test_parse_results_empty() -> None:
    with pytest.raises(AlibabaNoResultsError):
        parse_results_html(_read_text(EMPTY_HTML))


def test_parse_results_no_cards_raises_no_results() -> None:
    html = "<html><body><h1>Alibaba</h1><p>Some generic content.</p></body></html>"
    with pytest.raises(AlibabaNoResultsError):
        parse_results_html(html)


def test_driver_init_defaults() -> None:
    driver = AlibabaImageSearchDriver()
    assert driver._max_results is None
    assert driver._storage is not None


def test_driver_effective_max_results(storage: Storage) -> None:
    driver = AlibabaImageSearchDriver(storage=storage, max_results=5)
    assert driver._effective_max_results() == 5
    assert driver._effective_max_results(12) == 12
    assert driver._effective_max_results(0) == 1


def test_driver_search_by_image_missing_file(storage: Storage) -> None:
    driver = AlibabaImageSearchDriver(storage=storage)
    with pytest.raises(AlibabaSearchError, match="Image not found"):
        driver.search_by_image("/non/existent/image.jpg")


def test_driver_uses_cache(storage: Storage) -> None:
    cached = [
        Candidate(
            site="alibaba",
            title="Cached Earbuds",
            url="https://www.alibaba.com/product-detail/Cached.html",
            thumb_url="https://example.com/cached.jpg",
            price=1.99,
            similarity=0.0,
        ).model_dump(mode="json"),
    ]
    key = Storage.make_cache_key("alibaba:image_search", str(DUMMY_IMAGE.resolve()))
    storage.set(key, cached, namespace="alibaba:image_search")

    driver = AlibabaImageSearchDriver(storage=storage)
    results = driver.search_by_image(DUMMY_IMAGE)

    assert len(results) == 1
    assert results[0].title == "Cached Earbuds"


def test_driver_respects_max_results(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = AlibabaImageSearchDriver(storage=storage)

    def _fake_upload(image_path: str | Path) -> str:
        return html

    monkeypatch.setattr(driver, "_upload_and_search", _fake_upload)

    results = driver.search_by_image(DUMMY_IMAGE, max_results=2)
    assert len(results) == 2


def test_driver_caches_results_after_search(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = AlibabaImageSearchDriver(storage=storage)

    monkeypatch.setattr(driver, "_upload_and_search", lambda image_path: html)

    results = driver.search_by_image(DUMMY_IMAGE, max_results=3)
    assert len(results) == 3

    cached = storage.get(Storage.make_cache_key("alibaba:image_search", str(DUMMY_IMAGE.resolve())))
    assert isinstance(cached, list)
    assert len(cached) == 3


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ALIBABA_LIVE"), reason="Set ALIBABA_LIVE=1 to run live Alibaba search")
def test_search_by_image_live() -> None:
    driver = AlibabaImageSearchDriver()
    results = driver.search_by_image(DUMMY_IMAGE, max_results=5)
    assert len(results) > 0
    for candidate in results:
        assert candidate.site == "alibaba"
        assert candidate.url
        assert candidate.thumb_url


def test_driver_close_releases_owned_browser(storage: Storage) -> None:
    fake_browser = MagicMock()
    driver = AlibabaImageSearchDriver(storage=storage)
    driver._browser_manager = fake_browser
    driver._owns_browser = True

    driver.close()

    fake_browser.close.assert_called_once()
    assert driver._browser_manager is None


def test_driver_context_manager_uses_enter_exit(storage: Storage) -> None:
    with AlibabaImageSearchDriver(storage=storage) as driver:
        assert driver is not None
