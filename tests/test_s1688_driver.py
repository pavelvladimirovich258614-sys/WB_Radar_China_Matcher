from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.models import Candidate
from core.storage import Storage
from matcher.china.s1688 import (
    S1688CaptchaError,
    S1688ImageSearchDriver,
    S1688LoginRequiredError,
    S1688NoResultsError,
    S1688SearchError,
    _FILE_INPUT_SELECTORS,
    is_captcha_html,
    is_empty_results_html,
    is_login_required_html,
    normalize_candidate_url,
    parse_results_html,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
RESULTS_HTML = FIXTURES / "s1688_search_results.html"
CAPTCHA_HTML = FIXTURES / "s1688_captcha.html"
LOGIN_HTML = FIXTURES / "s1688_login.html"
EMPTY_HTML = FIXTURES / "s1688_empty.html"
DUMMY_IMAGE = FIXTURES / "dummy_query.jpg"
S1688_SESSION_DIR = Path(__file__).resolve().parent.parent / "sessions" / "1688"


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


def test_normalize_candidate_url() -> None:
    assert normalize_candidate_url("/offer/123.html") == "https://www.1688.com/offer/123.html"
    assert normalize_candidate_url("//1688.com/offer/456.html") == "https://1688.com/offer/456.html"
    assert normalize_candidate_url("https://detail.1688.com/offer/789.html") == "https://detail.1688.com/offer/789.html"
    assert normalize_candidate_url("") == ""


def test_parse_results_finds_candidates() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html)

    assert len(candidates) >= 4
    first_url = "https://www.1688.com/offer/123456789.html"
    assert candidates[0].site == "1688"
    assert candidates[0].title == "无线蓝牙耳机 TWS 入耳式"
    assert candidates[0].url == first_url
    assert candidates[0].thumb_url.startswith("https://")
    assert candidates[0].thumb_url.endswith("_123456789.jpg")
    assert candidates[0].price == 12.5
    assert candidates[0].has_video is False
    assert candidates[0].video_url is None

    assert candidates[1].url == "https://1688.com/offer/987654321.html"
    assert candidates[1].price == 45.0

    assert candidates[2].title == "迷你 TWS 耳机 带视频"
    assert candidates[2].url == "https://detail.1688.com/offer/111222333.html"
    assert candidates[2].price == 28.8
    assert candidates[2].has_video is True

    assert candidates[3].title == "运动蓝牙耳机"
    assert candidates[3].url == "https://www.1688.com/offer/444555666.html"
    assert candidates[3].price == 19.9


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/offer/123.html", "https://www.1688.com/offer/123.html"),
        ("//1688.com/offer/456.html", "https://1688.com/offer/456.html"),
        (
            "https://detail.1688.com/offer/789.html",
            "https://detail.1688.com/offer/789.html",
        ),
        ("offer/relative.html", "https://www.1688.com/offer/relative.html"),
    ],
)
def test_normalize_candidate_url_variants(raw: str, expected: str) -> None:
    assert normalize_candidate_url(raw) == expected


def test_parse_results_deduplicates_by_url() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html)
    urls = [c.url for c in candidates]
    assert len(urls) == len(set(urls))


def test_parse_results_absolute_and_protocol_relative_urls() -> None:
    html = _read_text(RESULTS_HTML)
    candidates = parse_results_html(html)

    # Relative href -> absolute https://www.1688.com/...
    assert candidates[0].url == "https://www.1688.com/offer/123456789.html"
    # Protocol-relative img src -> https://...
    assert candidates[0].thumb_url == (
        "https://cbu01.alicdn.com/img/ibank/O1CN01a2b3c4d5e6f7g8h9i0j_123456789.jpg"
    )
    # Protocol-relative href -> https://...
    assert candidates[1].url == "https://1688.com/offer/987654321.html"


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
    with pytest.raises(S1688CaptchaError):
        parse_results_html(_read_text(CAPTCHA_HTML))


def test_parse_results_detects_login() -> None:
    with pytest.raises(S1688LoginRequiredError):
        parse_results_html(_read_text(LOGIN_HTML))


def test_parse_results_empty() -> None:
    with pytest.raises(S1688NoResultsError):
        parse_results_html(_read_text(EMPTY_HTML))


def test_parse_results_no_cards_raises_no_results() -> None:
    html = "<html><body><h1>1688</h1><p>Some generic content.</p></body></html>"
    with pytest.raises(S1688NoResultsError):
        parse_results_html(html)


def test_driver_init_defaults() -> None:
    driver = S1688ImageSearchDriver()
    assert driver._max_results is None
    assert driver._storage is not None


def test_driver_effective_max_results(storage: Storage) -> None:
    driver = S1688ImageSearchDriver(storage=storage, max_results=5)
    assert driver._effective_max_results() == 5
    assert driver._effective_max_results(12) == 12
    assert driver._effective_max_results(0) == 1


def test_driver_search_by_image_missing_file(storage: Storage) -> None:
    driver = S1688ImageSearchDriver(storage=storage)
    with pytest.raises(S1688SearchError, match="Image not found"):
        driver.search_by_image("/non/existent/image.jpg")


def test_driver_uses_cache_and_skips_browser(storage: Storage) -> None:
    cached = [
        Candidate(
            site="1688",
            title="Cached 1688 Earbuds",
            url="https://www.1688.com/offer/Cached.html",
            thumb_url="https://example.com/cached.jpg",
            price=1.99,
            similarity=0.0,
        ).model_dump(mode="json"),
    ]
    limit = 20
    key = S1688ImageSearchDriver._make_cache_key(DUMMY_IMAGE, limit)
    storage.set(key, cached, namespace="1688:image_search")

    driver = S1688ImageSearchDriver(storage=storage)
    fake_upload = MagicMock()
    driver._upload_and_search = fake_upload

    results = driver.search_by_image(DUMMY_IMAGE)

    assert len(results) == 1
    assert results[0].title == "Cached 1688 Earbuds"
    fake_upload.assert_not_called()


def test_driver_use_cache_false_refetches(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    cached = [
        Candidate(
            site="1688",
            title="Stale Cached Earbuds",
            url="https://www.1688.com/offer/Stale.html",
            thumb_url="https://example.com/stale.jpg",
            price=9.99,
            similarity=0.0,
        ).model_dump(mode="json"),
    ]
    limit = 20
    key = S1688ImageSearchDriver._make_cache_key(DUMMY_IMAGE, limit)
    storage.set(key, cached, namespace="1688:image_search")

    driver = S1688ImageSearchDriver(storage=storage)

    upload_calls: list[str] = []

    def _fake_upload(image_path: str | Path) -> str:
        upload_calls.append(str(image_path))
        return html

    monkeypatch.setattr(driver, "_upload_and_search", _fake_upload)

    results = driver.search_by_image(DUMMY_IMAGE, use_cache=False)

    assert len(results) == 4
    assert results[0].title == "无线蓝牙耳机 TWS 入耳式"
    assert len(upload_calls) == 1


def test_driver_cache_returns_candidates_without_parsing(storage: Storage) -> None:
    """Cache hit must not call parse_results_html."""
    cached = [
        {
            "site": "1688",
            "title": "Only via cache",
            "url": "https://www.1688.com/offer/CacheOnly.html",
            "thumb_url": "https://example.com/only_cache.jpg",
            "price": 3.0,
            "similarity": 0.0,
            "has_video": False,
        }
    ]
    limit = 20
    key = S1688ImageSearchDriver._make_cache_key(DUMMY_IMAGE, limit)
    storage.set(key, cached, namespace="1688:image_search")

    driver = S1688ImageSearchDriver(storage=storage)
    parse_spy = MagicMock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("matcher.china.s1688.parse_results_html", parse_spy)

    try:
        results = driver.search_by_image(DUMMY_IMAGE)
        assert len(results) == 1
        assert results[0].title == "Only via cache"
        parse_spy.assert_not_called()
    finally:
        monkeypatch.undo()


def test_driver_respects_max_results(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = S1688ImageSearchDriver(storage=storage)

    def _fake_upload(image_path: str | Path) -> str:
        return html

    monkeypatch.setattr(driver, "_upload_and_search", _fake_upload)

    results = driver.search_by_image(DUMMY_IMAGE, max_results=2)
    assert len(results) == 2


def test_driver_caches_results_after_search(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = S1688ImageSearchDriver(storage=storage)

    monkeypatch.setattr(driver, "_upload_and_search", lambda image_path: html)

    results = driver.search_by_image(DUMMY_IMAGE, max_results=3)
    assert len(results) == 3

    cached = storage.get(S1688ImageSearchDriver._make_cache_key(DUMMY_IMAGE, 3))
    assert isinstance(cached, list)
    assert len(cached) == 3


def test_driver_search_by_image_fake_browser(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = S1688ImageSearchDriver(storage=storage)

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
        assert candidate.site == "1688"
        assert candidate.url.startswith("https://")
        assert candidate.thumb_url.startswith("https://")

    fake_browser.new_page.assert_called_once_with(site="1688", url="https://www.1688.com/picture/search.htm")
    fake_input.set_files.assert_called_once_with(str(DUMMY_IMAGE.resolve()))


def test_driver_search_by_image_fake_browser_falls_back_to_button_click(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(RESULTS_HTML)
    driver = S1688ImageSearchDriver(storage=storage)

    fake_input = MagicMock()
    fake_trigger = MagicMock()

    # First scan returns None for all selectors, query_selector finds a trigger,
    # second scan returns the input.
    calls: list[int] = []

    def _wait_for_selector(selector: str, *, timeout: int) -> MagicMock | None:
        calls.append(1)
        # First full pass over _FILE_INPUT_SELECTORS returns None.
        if len(calls) <= len(_FILE_INPUT_SELECTORS):
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
    driver = S1688ImageSearchDriver(storage=storage)

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

    with pytest.raises(S1688SearchError, match="upload input not found"):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_search_by_image_fake_browser_login(storage: Storage) -> None:
    html = _read_text(LOGIN_HTML)
    driver = S1688ImageSearchDriver(storage=storage)

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

    with pytest.raises(S1688LoginRequiredError):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_search_by_image_fake_browser_empty(storage: Storage) -> None:
    html = _read_text(EMPTY_HTML)
    driver = S1688ImageSearchDriver(storage=storage)

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

    with pytest.raises(S1688NoResultsError):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_search_by_image_fake_browser_captcha_after_upload(storage: Storage) -> None:
    """Captcha detected in result HTML after upload raises S1688CaptchaError."""
    html = _read_text(CAPTCHA_HTML)
    driver = S1688ImageSearchDriver(storage=storage)

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

    with pytest.raises(S1688CaptchaError):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_search_by_image_fake_browser_captcha(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    html = _read_text(CAPTCHA_HTML)
    driver = S1688ImageSearchDriver(storage=storage)

    fake_page = MagicMock()
    fake_page.content.return_value = html
    fake_page.wait_for_selector.return_value = MagicMock()
    fake_page.wait_for_load_state.return_value = None

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_browser.detect_captcha.return_value = True
    driver._browser_manager = fake_browser
    driver._owns_browser = False

    with pytest.raises(S1688CaptchaError):
        driver.search_by_image(DUMMY_IMAGE)


def test_driver_close_releases_owned_browser(storage: Storage) -> None:
    fake_browser = MagicMock()
    driver = S1688ImageSearchDriver(storage=storage)
    driver._browser_manager = fake_browser
    driver._owns_browser = True

    driver.close()

    fake_browser.close.assert_called_once()
    assert driver._browser_manager is None


def test_driver_context_manager_uses_enter_exit(storage: Storage) -> None:
    with S1688ImageSearchDriver(storage=storage) as driver:
        assert driver is not None


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("S1688_LIVE"), reason="S1688_LIVE=1 required")
def test_search_by_image_live() -> None:
    if not S1688_SESSION_DIR.exists() or not any(S1688_SESSION_DIR.iterdir()):
        pytest.skip("no persistent 1688 session")

    driver = S1688ImageSearchDriver()
    try:
        results = driver.search_by_image(DUMMY_IMAGE, max_results=5)
    except (S1688CaptchaError, S1688LoginRequiredError):
        pytest.skip("1688 requires login/captcha")

    assert len(results) > 0
    for candidate in results:
        assert candidate.site == "1688"
        assert candidate.url
        assert candidate.thumb_url
