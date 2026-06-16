from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.models import Candidate
from core.storage import Storage
from matcher.china.taobao import (
    TaobaoCaptchaError,
    TaobaoImageSearchDriver,
    TaobaoLoginRequiredError,
    TaobaoNoResultsError,
    TaobaoSearchError,
    is_captcha_html,
    is_empty_results_html,
    is_login_required_html,
    normalize_candidate_url,
    parse_results_html,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
RESULTS_HTML = FIXTURES / "taobao_search_results.html"
CAPTCHA_HTML = FIXTURES / "taobao_captcha.html"
LOGIN_HTML = FIXTURES / "taobao_login.html"
EMPTY_HTML = FIXTURES / "taobao_empty.html"
DUMMY_IMAGE = FIXTURES / "dummy_query.jpg"
TAOBAO_SESSION_DIR = Path(__file__).resolve().parent.parent / "sessions" / "taobao"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    return Storage(db_path=tmp_path / "cache.db", output_dir=tmp_path / "output")


def test_is_captcha_html() -> None:
    assert is_captcha_html(_read_text(CAPTCHA_HTML)) is True
    assert is_captcha_html(_read_text(RESULTS_HTML)) is False


def test_is_login_required_html() -> None:
    assert is_login_required_html(_read_text(LOGIN_HTML)) is True
    assert is_login_required_html(_read_text(RESULTS_HTML)) is False


def test_is_empty_results_html() -> None:
    assert is_empty_results_html(_read_text(EMPTY_HTML)) is True
    assert is_empty_results_html(_read_text(RESULTS_HTML)) is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", ""),
        (
            "//item.taobao.com/item.htm?id=1",
            "https://item.taobao.com/item.htm?id=1",
        ),
        (
            "/item/123.html",
            "https://www.taobao.com/item/123.html",
        ),
        (
            "item/789012.html",
            "https://www.taobao.com/item/789012.html",
        ),
        (
            "https://detail.tmall.com/item.htm?id=999",
            "https://detail.tmall.com/item.htm?id=999",
        ),
    ],
)
def test_normalize_candidate_url(raw: str, expected: str) -> None:
    assert normalize_candidate_url(raw) == expected


def test_parse_results_finds_candidates() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html)

    assert len(candidates) == 4

    assert candidates[0].site == "taobao"
    assert candidates[0].title == "TWS Wireless Bluetooth Earbuds"
    assert candidates[0].url == "https://item.taobao.com/item.htm?id=123456"
    assert candidates[0].thumb_url == "https://img.example.com/taobao/earbuds_123456.jpg"
    assert candidates[0].price == 19.9
    assert candidates[0].has_video is False
    assert candidates[0].video_url is None
    assert candidates[0].similarity == 0.0

    assert candidates[1].title == "Bluetooth Headphones Over Ear"
    assert candidates[1].url == "https://www.taobao.com/item/654321.html"
    assert candidates[1].thumb_url == "https://img.example.com/taobao/headphones_654321.jpg"
    assert candidates[1].price == 88.0

    assert candidates[2].title == "Mini TWS Earbuds with Video"
    assert candidates[2].url == "https://item.taobao.com/item.htm?id=111222333"
    assert candidates[2].price == 56.7
    assert candidates[2].has_video is True

    assert candidates[3].title == "Sport Bluetooth Earphone"
    assert candidates[3].url == "https://www.taobao.com/item/789012.html"
    assert candidates[3].thumb_url == "https://img.example.com/taobao/sport_789012.jpg"
    assert candidates[3].price == 35.5


def test_parse_results_deduplicates_by_url() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html)
    urls = [c.url for c in candidates]
    assert len(urls) == len(set(urls))


def test_parse_results_absolute_and_protocol_relative_urls() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html)

    assert candidates[0].url == "https://item.taobao.com/item.htm?id=123456"
    assert candidates[0].thumb_url == "https://img.example.com/taobao/earbuds_123456.jpg"
    assert candidates[1].url == "https://www.taobao.com/item/654321.html"


def test_parse_results_respects_max_results() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html, max_results=2)
    assert len(candidates) == 2

    all_candidates = parse_results_html(html)
    assert len(all_candidates) > 2


def test_parse_results_max_results_zero_returns_empty() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html, max_results=0)
    assert len(candidates) == 0


def test_parse_results_detects_captcha() -> None:
    with pytest.raises(TaobaoCaptchaError):
        parse_results_html(_read_text(CAPTCHA_HTML))


def test_parse_results_detects_login() -> None:
    with pytest.raises(TaobaoLoginRequiredError):
        parse_results_html(_read_text(LOGIN_HTML))


def test_parse_results_empty() -> None:
    with pytest.raises(TaobaoNoResultsError):
        parse_results_html(_read_text(EMPTY_HTML))


def test_parse_results_no_cards_raises_no_results() -> None:
    html = "<html><body><h1>Taobao</h1><p>Some generic content.</p></body></html>"
    with pytest.raises(TaobaoNoResultsError):
        parse_results_html(html)


def test_driver_init_defaults() -> None:
    driver = TaobaoImageSearchDriver()
    assert driver._max_results is None
    assert driver._storage is not None


def test_driver_effective_max_results(storage: Storage) -> None:
    driver = TaobaoImageSearchDriver(storage=storage, max_results=5)
    assert driver._effective_max_results() == 5
    assert driver._effective_max_results(12) == 12
    assert driver._effective_max_results(0) == 1


def test_driver_search_by_image_missing_file(storage: Storage) -> None:
    driver = TaobaoImageSearchDriver(storage=storage)
    with pytest.raises(TaobaoSearchError, match="Image not found"):
        driver.search_by_image("/non/existent/image.jpg")


def test_driver_uses_cache_and_skips_browser(storage: Storage) -> None:
    cached = [
        Candidate(
            site="taobao",
            title="Cached Taobao Earbuds",
            url="https://item.taobao.com/item.htm?id=Cached",
            thumb_url="https://example.com/cached.jpg",
            price=1.99,
            similarity=0.0,
        ).model_dump(mode="json"),
    ]
    limit = 20
    key = TaobaoImageSearchDriver._make_cache_key(DUMMY_IMAGE, limit)
    storage.set(key, cached, namespace="taobao:image_search")

    driver = TaobaoImageSearchDriver(storage=storage)
    fake_upload = MagicMock()
    driver._upload_and_search = fake_upload

    results = driver.search_by_image(DUMMY_IMAGE)

    assert len(results) == 1
    assert results[0].title == "Cached Taobao Earbuds"
    fake_upload.assert_not_called()


def test_driver_use_cache_false_refetches(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    cached = [
        Candidate(
            site="taobao",
            title="Stale Cached Earbuds",
            url="https://item.taobao.com/item.htm?id=Stale",
            thumb_url="https://example.com/stale.jpg",
            price=9.99,
            similarity=0.0,
        ).model_dump(mode="json"),
    ]
    limit = 20
    key = TaobaoImageSearchDriver._make_cache_key(DUMMY_IMAGE, limit)
    storage.set(key, cached, namespace="taobao:image_search")

    driver = TaobaoImageSearchDriver(storage=storage)

    upload_calls: list[str] = []

    def _fake_upload(image_path: str | Path) -> str:
        upload_calls.append(str(image_path))
        return html

    monkeypatch.setattr(driver, "_upload_and_search", _fake_upload)

    results = driver.search_by_image(DUMMY_IMAGE, use_cache=False)

    assert len(results) == 4
    assert results[0].title == "TWS Wireless Bluetooth Earbuds"
    assert len(upload_calls) == 1


def test_driver_cache_returns_candidates_without_parsing(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache hit must not call parse_results_html."""
    cached = [
        {
            "site": "taobao",
            "title": "Only via cache",
            "url": "https://item.taobao.com/item.htm?id=CacheOnly",
            "thumb_url": "https://example.com/only_cache.jpg",
            "price": 3.0,
            "similarity": 0.0,
            "has_video": False,
        }
    ]
    limit = 20
    key = TaobaoImageSearchDriver._make_cache_key(DUMMY_IMAGE, limit)
    storage.set(key, cached, namespace="taobao:image_search")

    driver = TaobaoImageSearchDriver(storage=storage)
    parse_spy = MagicMock()
    monkeypatch.setattr("matcher.china.taobao.parse_results_html", parse_spy)

    results = driver.search_by_image(DUMMY_IMAGE)

    assert len(results) == 1
    assert results[0].title == "Only via cache"
    parse_spy.assert_not_called()


def test_driver_respects_max_results(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = TaobaoImageSearchDriver(storage=storage)

    def _fake_upload(image_path: str | Path) -> str:
        return html

    monkeypatch.setattr(driver, "_upload_and_search", _fake_upload)

    results = driver.search_by_image(DUMMY_IMAGE, max_results=2)
    assert len(results) == 2


def test_driver_caches_results_after_search(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = TaobaoImageSearchDriver(storage=storage)

    monkeypatch.setattr(driver, "_upload_and_search", lambda image_path: html)

    results = driver.search_by_image(DUMMY_IMAGE, max_results=3)
    assert len(results) == 3

    cached = storage.get(TaobaoImageSearchDriver._make_cache_key(DUMMY_IMAGE, 3))
    assert isinstance(cached, list)
    assert len(cached) == 3


def test_driver_search_by_image_fake_browser(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = TaobaoImageSearchDriver(storage=storage)

    fake_input = MagicMock()
    fake_page = MagicMock()
    fake_page.content.return_value = html
    fake_page.wait_for_selector.return_value = fake_input
    fake_page.wait_for_load_state.return_value = None
    fake_page.query_selector.return_value = None

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_browser.detect_captcha.return_value = False
    driver._browser_manager = fake_browser
    driver._owns_browser = False

    results = driver.search_by_image(DUMMY_IMAGE, max_results=3)

    assert len(results) == 3
    for candidate in results:
        assert candidate.site == "taobao"
        assert candidate.url.startswith("https://")
        assert candidate.thumb_url.startswith("https://")

    fake_browser.new_page.assert_called_once_with(site="taobao", url="https://www.taobao.com/markets/pic/search")
    fake_input.set_files.assert_called_once_with(str(DUMMY_IMAGE.resolve()))


def test_driver_search_by_image_fake_browser_falls_back_to_button_click(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = TaobaoImageSearchDriver(storage=storage)

    fake_input = MagicMock()
    fake_trigger = MagicMock()

    calls: list[int] = []

    def _wait_for_selector(selector: str, *, timeout: int) -> MagicMock | None:
        calls.append(1)
        # First full pass over file input selectors returns None.
        if len(calls) <= 4:
            return None
        return fake_input

    fake_page = MagicMock()
    fake_page.content.return_value = html
    fake_page.wait_for_load_state.return_value = None
    fake_page.wait_for_selector.side_effect = _wait_for_selector
    fake_page.query_selector.return_value = fake_trigger
    fake_page.wait_for_timeout.return_value = None

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_browser.detect_captcha.return_value = False
    driver._browser_manager = fake_browser
    driver._owns_browser = False

    results = driver.search_by_image(DUMMY_IMAGE, max_results=3)

    assert len(results) == 3
    fake_trigger.click.assert_called_once()


def test_driver_search_by_image_fake_browser_no_input_raises(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    driver = TaobaoImageSearchDriver(storage=storage)

    fake_page = MagicMock()
    fake_page.content.return_value = _read_text(EMPTY_HTML)
    fake_page.wait_for_load_state.return_value = None
    fake_page.wait_for_selector.return_value = None
    fake_page.query_selector.return_value = None

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_browser.detect_captcha.return_value = False
    driver._browser_manager = fake_browser
    driver._owns_browser = False

    with pytest.raises(TaobaoSearchError, match="upload input not found"):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_search_by_image_fake_browser_login(storage: Storage) -> None:
    html = _read_text(LOGIN_HTML)
    driver = TaobaoImageSearchDriver(storage=storage)

    fake_input = MagicMock()
    fake_page = MagicMock()
    fake_page.content.return_value = html
    fake_page.wait_for_selector.return_value = fake_input
    fake_page.wait_for_load_state.return_value = None
    fake_page.query_selector.return_value = None

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_browser.detect_captcha.return_value = False
    driver._browser_manager = fake_browser
    driver._owns_browser = False

    with pytest.raises(TaobaoLoginRequiredError):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_search_by_image_fake_browser_empty(storage: Storage) -> None:
    html = _read_text(EMPTY_HTML)
    driver = TaobaoImageSearchDriver(storage=storage)

    fake_input = MagicMock()
    fake_page = MagicMock()
    fake_page.content.return_value = html
    fake_page.wait_for_selector.return_value = fake_input
    fake_page.wait_for_load_state.return_value = None
    fake_page.query_selector.return_value = None

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_browser.detect_captcha.return_value = False
    driver._browser_manager = fake_browser
    driver._owns_browser = False

    with pytest.raises(TaobaoNoResultsError):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_search_by_image_fake_browser_captcha_after_upload(storage: Storage) -> None:
    """Captcha detected in result HTML after upload raises TaobaoCaptchaError."""
    html = _read_text(CAPTCHA_HTML)
    driver = TaobaoImageSearchDriver(storage=storage)

    fake_input = MagicMock()
    fake_page = MagicMock()
    fake_page.content.return_value = html
    fake_page.wait_for_selector.return_value = fake_input
    fake_page.wait_for_load_state.return_value = None
    fake_page.query_selector.return_value = None

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_browser.detect_captcha.return_value = False
    driver._browser_manager = fake_browser
    driver._owns_browser = False

    with pytest.raises(TaobaoCaptchaError):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_search_by_image_fake_browser_captcha(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(CAPTCHA_HTML)
    driver = TaobaoImageSearchDriver(storage=storage)

    fake_page = MagicMock()
    fake_page.content.return_value = html
    fake_page.wait_for_selector.return_value = MagicMock()
    fake_page.wait_for_load_state.return_value = None

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_browser.detect_captcha.return_value = True
    driver._browser_manager = fake_browser
    driver._owns_browser = False

    with pytest.raises(TaobaoCaptchaError):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_close_releases_owned_browser(storage: Storage) -> None:
    fake_browser = MagicMock()
    driver = TaobaoImageSearchDriver(storage=storage)
    driver._browser_manager = fake_browser
    driver._owns_browser = True

    driver.close()

    fake_browser.close.assert_called_once()
    assert driver._browser_manager is None


def test_driver_context_manager_uses_enter_exit(storage: Storage) -> None:
    with TaobaoImageSearchDriver(storage=storage) as driver:
        assert driver is not None


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("TAOBAO_LIVE"), reason="Set TAOBAO_LIVE=1 to run live Taobao search")
def test_search_by_image_live() -> None:
    if not TAOBAO_SESSION_DIR.exists() or not any(TAOBAO_SESSION_DIR.iterdir()):
        pytest.skip("no persistent Taobao session")

    driver = TaobaoImageSearchDriver()
    try:
        results = driver.search_by_image(DUMMY_IMAGE, max_results=5)
    except (TaobaoCaptchaError, TaobaoLoginRequiredError):
        pytest.skip("Taobao requires login/captcha")

    assert len(results) > 0
    for candidate in results:
        assert candidate.site == "taobao"
        assert candidate.url
        assert candidate.thumb_url
