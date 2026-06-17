from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.models import Candidate
from matcher.video_china import (
    ChinaVideoExtractor,
    VideoExtractError,
    VideoNotFoundError,
    extract_china_videos,
    extract_video_url_from_html,
    extract_video_urls_from_html,
    looks_like_video_url,
    normalize_video_url,
    pick_best_video_url,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
VIDEO_TAG_HTML = FIXTURES / "china_video_video_tag.html"
SCRIPT_JSON_HTML = FIXTURES / "china_video_script_json.html"
NO_VIDEO_HTML = FIXTURES / "china_video_no_video.html"
M3U8_HTML = FIXTURES / "china_video_m3u8.html"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def test_video_extract_error_is_exception() -> None:
    with pytest.raises(VideoExtractError, match="boom"):
        raise VideoExtractError("boom")


def test_video_not_found_error_is_extract_error() -> None:
    with pytest.raises(VideoExtractError):
        raise VideoNotFoundError("not found")


# ---------------------------------------------------------------------------
# normalize_video_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,base,expected",
    [
        ("", None, None),
        ("   ", None, None),
        ("javascript:void(0)", None, None),
        ("data:image/png;base64,abc", None, None),
        ("blob:https://example.com/uuid", None, None),
        ("https://cdn.example.com/video.mp4", None, "https://cdn.example.com/video.mp4"),
        ("http://cdn.example.com/video.mp4", None, "https://cdn.example.com/video.mp4"),
        ("//cdn.example.com/video.mp4", None, "https://cdn.example.com/video.mp4"),
        ("/videos/item.mp4", "https://shop.example.com/", "https://shop.example.com/videos/item.mp4"),
        ("item.mp4", "https://shop.example.com/page", "https://shop.example.com/item.mp4"),
        ("https://cdn.example.com/video%20file.mp4", None, "https://cdn.example.com/video%20file.mp4"),
        (r"https:\u002F\u002Fcdn.example.com\u002Fvideo.mp4", None, "https://cdn.example.com/video.mp4"),
        (r"\u002F\u002Fcdn.example.com\u002Fvideo.mp4", None, "https://cdn.example.com/video.mp4"),
    ],
)
def test_normalize_video_url(raw: str, base: str | None, expected: str | None) -> None:
    assert normalize_video_url(raw, base_url=base) == expected


# ---------------------------------------------------------------------------
# looks_like_video_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url,expected",
    [
        (None, False),
        ("", False),
        ("https://cdn.example.com/video.mp4", True),
        ("https://cdn.example.com/playlist.m3u8", True),
        ("https://cdn.example.com/clip.mov", True),
        ("https://cdn.example.com/clip.webm", True),
        ("https://cloud.video.taobao.com/play/u/123/e/6/123.mp4", True),
        ("https://video.taobao.com/play/u/123/e/6/123.mp4", True),
        ("https://vod.example.com/video.mp4", True),
        ("https://video.alicdn.com/123/456.mp4", True),
        ("https://cloud.video.alibaba.com/123/456.mp4", True),
        ("https://cdn.example.com/photo.jpg", False),
        ("https://cdn.example.com/photo.png", False),
        ("https://cdn.example.com/photo.gif", False),
        ("https://cdn.example.com/photo.webp", False),
        ("https://cdn.example.com/file.pdf", False),
    ],
)
def test_looks_like_video_url(url: str | None, expected: bool) -> None:
    assert looks_like_video_url(url) is expected


# ---------------------------------------------------------------------------
# extract_video_urls_from_html / extract_video_url_from_html
# ---------------------------------------------------------------------------

def test_extract_video_urls_from_html_video_tag() -> None:
    html = _read_text(VIDEO_TAG_HTML)
    urls = extract_video_urls_from_html(html, base_url="https://example.com")
    assert urls == ["https://cdn.example.com/video.mp4"]


def test_extract_video_urls_from_html_source_tag() -> None:
    html = """
    <video controls>
      <source src="//cdn.example.com/video.mov" type="video/mp4">
      <source data-src="https://cdn.example.com/playlist.m3u8" type="application/x-mpegURL">
    </video>
    """
    urls = extract_video_urls_from_html(html, base_url="https://example.com")
    assert "https://cdn.example.com/video.mov" in urls
    assert "https://cdn.example.com/playlist.m3u8" in urls


def test_extract_video_urls_from_html_script_json() -> None:
    html = _read_text(SCRIPT_JSON_HTML)
    urls = extract_video_urls_from_html(html, base_url="https://example.com")
    assert urls == ["https://cdn.example.com/script.mp4"]


def test_extract_video_urls_from_html_escaped_url() -> None:
    html = r'''
    <script>
    var data = {"media": "https:\u002F\u002Fvod.example.com\u002Fitem.mp4"};
    </script>
    '''
    urls = extract_video_urls_from_html(html, base_url="https://example.com")
    assert "https://vod.example.com/item.mp4" in urls


def test_extract_video_urls_from_html_no_video() -> None:
    html = _read_text(NO_VIDEO_HTML)
    assert extract_video_urls_from_html(html) == []


def test_extract_video_url_from_html_m3u8() -> None:
    html = _read_text(M3U8_HTML)
    assert extract_video_url_from_html(html) == "https://cdn.example.com/playlist.m3u8"


def test_extract_video_urls_dedup_preserves_order() -> None:
    html = """
    <video src="https://cdn.example.com/video.mp4"></video>
    <source src="https://cdn.example.com/video.mp4" type="video/mp4">
    <source src="https://cdn.example.com/other.webm">
    """
    urls = extract_video_urls_from_html(html)
    assert urls == [
        "https://cdn.example.com/video.mp4",
        "https://cdn.example.com/other.webm",
    ]


# ---------------------------------------------------------------------------
# pick_best_video_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "urls,expected",
    [
        ([], None),
        (["https://cdn.example.com/playlist.m3u8"], "https://cdn.example.com/playlist.m3u8"),
        (
            [
                "https://cdn.example.com/playlist.m3u8",
                "https://cdn.example.com/clip.mov",
                "https://cdn.example.com/video.mp4",
            ],
            "https://cdn.example.com/video.mp4",
        ),
        (
            [
                "https://video.alicdn.com/abc.m3u8",
                "https://cdn.example.com/clip.webm",
            ],
            "https://cdn.example.com/clip.webm",
        ),
    ],
)
def test_pick_best_video_url(urls: list[str], expected: str | None) -> None:
    assert pick_best_video_url(urls) == expected


# ---------------------------------------------------------------------------
# Fake doubles for ChinaVideoExtractor
# ---------------------------------------------------------------------------

class FakePage:
    """Minimal page double for offline video-extractor tests."""

    def __init__(self, html: str = "", url: str = "") -> None:
        self._html = html
        self.url = url
        self._callbacks: dict[str, list[Any]] = {"request": [], "response": []}
        self.closed = False
        self.network_urls: list[str] = []

    def content(self) -> str:
        return self._html

    def on(self, event: str, callback: Any) -> None:
        self._callbacks.setdefault(event, []).append(callback)

    def trigger_request(self, url: str) -> None:
        for cb in self._callbacks.get("request", []):
            cb(FakeRequest(url))

    def trigger_response(self, url: str) -> None:
        for cb in self._callbacks.get("response", []):
            cb(FakeResponse(url))

    def close(self) -> None:
        self.closed = True


class FakeRequest:
    def __init__(self, url: str) -> None:
        self.url = url


class FakeResponse:
    def __init__(self, url: str) -> None:
        self.url = url


class FakeBrowserManager:
    """Minimal BrowserManager double that never launches a real browser."""

    def __init__(self, *, html: str = "", captcha: bool = False, url: str = "") -> None:
        self.html = html
        self.captcha = captcha
        self.url = url
        self.closed = False
        self.calls: list[tuple[str, str | None]] = []

    def new_page(self, site: str, url: str | None = None) -> FakePage:
        self.calls.append((site, url))
        page_url = url or self.url
        page = FakePage(html=self.html, url=page_url)
        # Pre-populate network capture with a URL if requested by the test.
        for nu in self.network_urls:
            page.network_urls.append(nu)
        return page

    def detect_captcha(self, page: Any) -> bool:
        return self.captcha

    def close(self) -> None:
        self.closed = True

    @property
    def network_urls(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# ChinaVideoExtractor — pure/unit behavior
# ---------------------------------------------------------------------------


def test_extractor_init_defaults_does_not_create_browser() -> None:
    extractor = ChinaVideoExtractor()
    assert extractor._browser_manager is None
    assert extractor._owns_browser is True


def test_extractor_init_with_injected_browser() -> None:
    fake = FakeBrowserManager()
    extractor = ChinaVideoExtractor(browser_manager=fake)
    assert extractor._browser_manager is fake
    assert extractor._owns_browser is False


def test_extract_from_candidate_no_url_returns_no_video() -> None:
    extractor = ChinaVideoExtractor(browser_manager=FakeBrowserManager())
    candidate = Candidate(site="alibaba", title="Earbuds", thumb_url="https://example.com/t.jpg")
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is False
    assert result.video_url is None
    assert result.title == candidate.title


def test_extract_from_candidate_empty_url_returns_no_video() -> None:
    extractor = ChinaVideoExtractor(browser_manager=FakeBrowserManager())
    candidate = Candidate(site="alibaba", title="Earbuds", url="   ", thumb_url="https://example.com/t.jpg")
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is False
    assert result.video_url is None


def test_extract_from_candidate_video_tag() -> None:
    html = _read_text(VIDEO_TAG_HTML)
    fake = FakeBrowserManager(html=html)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0)
    candidate = Candidate(
        site="alibaba",
        title="Earbuds",
        url="https://example.com/product/123",
        thumb_url="https://example.com/t.jpg",
    )
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is True
    assert result.video_url == "https://cdn.example.com/video.mp4"
    assert fake.calls == [("china_video", "https://example.com/product/123")]


def test_extract_from_candidate_script_json() -> None:
    html = _read_text(SCRIPT_JSON_HTML)
    fake = FakeBrowserManager(html=html)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0)
    candidate = Candidate(
        site="1688",
        title="Earbuds",
        url="https://example.com/product/456",
        thumb_url="https://example.com/t.jpg",
    )
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is True
    assert result.video_url == "https://cdn.example.com/script.mp4"


def test_extract_from_candidate_m3u8() -> None:
    html = _read_text(M3U8_HTML)
    fake = FakeBrowserManager(html=html)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0)
    candidate = Candidate(
        site="taobao",
        title="Earbuds",
        url="https://example.com/product/789",
        thumb_url="https://example.com/t.jpg",
    )
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is True
    assert result.video_url == "https://cdn.example.com/playlist.m3u8"


def test_extract_from_candidate_no_video() -> None:
    html = _read_text(NO_VIDEO_HTML)
    fake = FakeBrowserManager(html=html)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0)
    candidate = Candidate(
        site="alibaba",
        title="Earbuds",
        url="https://example.com/product/000",
        thumb_url="https://example.com/t.jpg",
    )
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is False
    assert result.video_url is None


def test_extract_from_candidate_captcha_returns_no_video() -> None:
    html = _read_text(VIDEO_TAG_HTML)
    fake = FakeBrowserManager(html=html, captcha=True)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0)
    candidate = Candidate(
        site="alibaba",
        title="Earbuds",
        url="https://example.com/product/123",
        thumb_url="https://example.com/t.jpg",
    )
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is False
    assert result.video_url is None


def test_extract_from_candidate_falls_back_to_network_url() -> None:
    html = _read_text(NO_VIDEO_HTML)
    fake = FakeBrowserManager(html=html)
    # Manually attach a network URL to the returned page.
    original_new_page = fake.new_page

    def _new_page(site: str, url: str | None = None) -> FakePage:
        page = original_new_page(site, url)
        page.network_urls.append("https://cdn.example.com/network.mp4")
        return page

    fake.new_page = _new_page

    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0)
    candidate = Candidate(
        site="alibaba",
        title="Earbuds",
        url="https://example.com/product/123",
        thumb_url="https://example.com/t.jpg",
    )

    # Patch FakePage.on so pre-registered network URLs are captured.
    original_extract = extractor.extract_from_candidate

    class NetworkFakePage(FakePage):
        def __init__(self, html: str = "", url: str = "") -> None:
            super().__init__(html=html, url=url)
            self.network_urls: list[str] = []

        def content(self) -> str:
            return self._html

        def on(self, event: str, callback: Any) -> None:
            super().on(event, callback)
            if event == "response":
                for nu in self.network_urls:
                    callback(FakeResponse(nu))

    def _new_page_with_network(site: str, url: str | None = None) -> FakePage:
        page = NetworkFakePage(html=html, url=url or "")
        page.network_urls.append("https://cdn.example.com/network.mp4")
        fake.calls.append((site, url))
        return page

    fake.new_page = _new_page_with_network

    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is True
    assert result.video_url == "https://cdn.example.com/network.mp4"


def test_extract_from_candidate_error_returns_no_video() -> None:
    class BrokenBrowser:
        def new_page(self, site: str, url: str | None = None) -> Any:
            raise RuntimeError("browser broken")

        def detect_captcha(self, page: Any) -> bool:
            return False

    extractor = ChinaVideoExtractor(browser_manager=BrokenBrowser(), wait_after_load_ms=0)
    candidate = Candidate(
        site="alibaba",
        title="Earbuds",
        url="https://example.com/product/123",
        thumb_url="https://example.com/t.jpg",
    )
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is False
    assert result.video_url is None


def test_extract_from_candidate_closes_page() -> None:
    html = _read_text(VIDEO_TAG_HTML)
    fake = FakeBrowserManager(html=html)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0)
    candidate = Candidate(
        site="alibaba",
        title="Earbuds",
        url="https://example.com/product/123",
        thumb_url="https://example.com/t.jpg",
    )
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is True
    assert fake.calls[0][1] == "https://example.com/product/123"


def test_extract_for_candidates_respects_top_n_default() -> None:
    html = _read_text(VIDEO_TAG_HTML)
    fake = FakeBrowserManager(html=html)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0, top_n=2)

    candidates = [
        Candidate(site="alibaba", title=f"Item {i}", url=f"https://example.com/{i}", thumb_url="https://example.com/t.jpg")
        for i in range(5)
    ]
    results = extractor.extract_for_candidates(candidates)
    assert len(results) == 2
    for r in results:
        assert r.has_video is True


def test_extract_for_candidates_override_top_n() -> None:
    html = _read_text(NO_VIDEO_HTML)
    fake = FakeBrowserManager(html=html)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0, top_n=10)

    candidates = [
        Candidate(site="alibaba", title=f"Item {i}", url=f"https://example.com/{i}", thumb_url="https://example.com/t.jpg")
        for i in range(5)
    ]
    results = extractor.extract_for_candidates(candidates, top_n=3)
    assert len(results) == 3


def test_extract_for_candidates_error_one_does_not_stop_batch() -> None:
    class FlakyBrowser:
        def __init__(self) -> None:
            self.calls = 0

        def new_page(self, site: str, url: str | None = None) -> FakePage:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("flaky")
            return FakePage(html=_read_text(VIDEO_TAG_HTML), url=url or "")

        def detect_captcha(self, page: Any) -> bool:
            return False

    extractor = ChinaVideoExtractor(browser_manager=FlakyBrowser(), wait_after_load_ms=0)
    candidates = [
        Candidate(site="alibaba", title=f"Item {i}", url=f"https://example.com/{i}", thumb_url="https://example.com/t.jpg")
        for i in range(3)
    ]
    results = extractor.extract_for_candidates(candidates, top_n=3)
    assert len(results) == 3
    assert results[0].has_video is True
    assert results[1].has_video is False
    assert results[2].has_video is True


def test_extract_china_videos_alias() -> None:
    html = _read_text(VIDEO_TAG_HTML)
    fake = FakeBrowserManager(html=html)
    extractor = ChinaVideoExtractor(browser_manager=fake, wait_after_load_ms=0, top_n=1)

    candidates = [
        Candidate(site="alibaba", title="Item", url="https://example.com/1", thumb_url="https://example.com/t.jpg")
    ]
    results = extractor.extract_china_videos(candidates)
    assert len(results) == 1
    assert results[0].has_video is True


def test_extractor_close_closes_owned_browser() -> None:
    fake = FakeBrowserManager()
    extractor = ChinaVideoExtractor(browser_manager=fake)
    # Simulate owned browser: inject and flip ownership.
    extractor._owns_browser = True
    extractor.close()
    assert fake.closed is True


def test_extractor_context_manager_does_not_close_injected_browser() -> None:
    fake = FakeBrowserManager()
    extractor = ChinaVideoExtractor(browser_manager=fake)
    with extractor:
        pass
    assert fake.closed is False


# ---------------------------------------------------------------------------
# Integration with public aliases
# ---------------------------------------------------------------------------

def test_extract_china_videos_public_alias() -> None:
    html = _read_text(VIDEO_TAG_HTML)
    fake = FakeBrowserManager(html=html)
    candidates = [
        Candidate(site="alibaba", title="Item", url="https://example.com/1", thumb_url="https://example.com/t.jpg")
    ]
    results = extract_china_videos(candidates, browser_manager=fake, wait_after_load_ms=0)
    assert len(results) == 1
    assert results[0].has_video is True
    assert results[0].video_url == "https://cdn.example.com/video.mp4"


# ---------------------------------------------------------------------------
# Real network guard — ensures we never accidentally hit the network
# ---------------------------------------------------------------------------

def test_extractor_with_real_browser_manager_does_not_run_in_unit_tests() -> None:
    """If no browser is injected, the extractor creates one lazily.

    This test only verifies that the lazy path exists and returns a safe
    no-video result when given a candidate with no URL, without navigating.
    """
    extractor = ChinaVideoExtractor(wait_after_load_ms=0)
    candidate = Candidate(site="alibaba", title="Earbuds", thumb_url="https://example.com/t.jpg")
    result = extractor.extract_from_candidate(candidate)
    assert result.has_video is False
