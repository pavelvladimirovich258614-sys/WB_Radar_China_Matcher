from __future__ import annotations

import html
import json
import logging
import re
import time
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core.browser import BrowserManager
from core.config import settings as default_settings
from core.models import Candidate

logger = logging.getLogger(__name__)

_VIDEO_EXTENSIONS = (".mp4", ".m3u8", ".mov", ".webm")
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")

# Host/path substrings that strongly suggest a video URL on Chinese marketplaces.
_VIDEO_HOST_MARKERS = (
    "cloud.video.taobao",
    "video.taobao",
    "vod",
    "alicdn",
    "cloud.video",
)

# JSON/script field names where product videos are often embedded.
_VIDEO_JSON_KEYS = (
    "videoUrl",
    "video_url",
    "videoSrc",
    "video_src",
    "videoPath",
    "video_path",
    "mp4Url",
    "mp4_url",
    "playUrl",
    "play_url",
    "videoURI",
    "video_uri",
)


class VideoExtractError(Exception):
    """Base class for China product-video extraction failures."""


class VideoNotFoundError(VideoExtractError):
    """No usable product video was found on the page or in network traffic."""


def normalize_video_url(url: str, base_url: str | None = None) -> str | None:
    """Normalize a raw video URL string to absolute https form.

    Returns ``None`` for empty/blank strings, javascript/data/blob URLs, or
    anything that cannot be made absolute. HTML-escaped sequences such as
    ``\\u002F`` are decoded to regular characters.
    """
    if not isinstance(url, str):
        return None

    url = url.strip()
    if not url:
        return None

    # Decode HTML escapes and JSON-style \uXXXX sequences first.
    url = url.encode().decode("unicode_escape")
    url = html.unescape(url)

    lower = url.lower()
    if lower.startswith(("javascript:", "data:", "blob:")):
        return None

    if lower.startswith("http://"):
        url = "https" + url[4:]

    if url.startswith("//"):
        return "https:" + url

    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return url

    if base_url:
        joined = urljoin(base_url, url)
        parsed_joined = urlparse(joined)
        if parsed_joined.scheme in ("http", "https") and parsed_joined.netloc:
            return joined

    return None


def looks_like_video_url(url: str | None) -> bool:
    """Return True if ``url`` looks like a video resource.

    Checks:
    - path ends with a known video extension;
    - hostname or path contains well-known video/CDN markers;
    - rejects obvious image extensions and empty/None values.
    """
    if not url:
        return False

    text = str(url).lower()

    if any(text.endswith(ext) for ext in _IMAGE_EXTENSIONS):
        return False

    if any(text.endswith(ext) for ext in _VIDEO_EXTENSIONS):
        return True

    for marker in _VIDEO_HOST_MARKERS:
        if marker in text:
            return True

    if "video" in text and ("alicdn" in text or "vod" in text or "cloud" in text):
        return True

    return False


def _extract_strings_from_json(value: Any) -> list[str]:
    """Recursively collect string values from a parsed JSON object."""
    results: list[str] = []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        for k, v in value.items():
            # Prioritize known video keys, but still collect everything.
            results.extend(_extract_strings_from_json(v))
    if isinstance(value, list):
        for item in value:
            results.extend(_extract_strings_from_json(item))
    return results


def _candidate_video_from_json(value: Any) -> list[str]:
    """Collect URL-like strings, with a bias toward known video JSON keys."""
    urls: list[str] = []
    if not isinstance(value, dict):
        return _extract_strings_from_json(value)

    for key, val in value.items():
        if key in _VIDEO_JSON_KEYS:
            if isinstance(val, str):
                urls.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        urls.append(item)
        else:
            urls.extend(_extract_strings_from_json(val))
    return urls


def extract_video_urls_from_html(html: str, base_url: str | None = None) -> list[str]:
    """Extract and normalize candidate video URLs from raw HTML.

    Sources, in order:
    1. ``<video>`` and ``<source>`` ``src`` / ``data-src`` attributes.
    2. URL-like strings inside ``<script>`` tags (JSON or escaped URLs).
    3. Escaped URLs anywhere in the text (``\\u002F`` and friends).

    Each candidate is normalized and filtered through
    :func:`looks_like_video_url`; duplicates are removed while preserving the
    discovery order.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    raw_urls: list[str] = []

    # 1. Explicit video/source tags.
    for tag in soup.find_all(["video", "source"]):
        for attr in ("src", "data-src"):
            value = tag.get(attr)
            if value:
                raw_urls.append(str(value))

    # 2. URLs hidden in <script> JSON or plain text.
    for script in soup.find_all("script"):
        text = script.string or script.text or ""
        if not text.strip():
            continue

        # Try as JSON first.
        try:
            data = json.loads(text)
            for maybe in _candidate_video_from_json(data):
                if maybe and isinstance(maybe, str):
                    raw_urls.append(maybe)
        except (json.JSONDecodeError, ValueError, TypeError):
            # Otherwise extract likely http(s) URL tokens.
            for token in re.split(r"[\"'\s,\{\}\[\]]+", text):
                token = token.strip()
                if token.startswith(("http://", "https://", "//")):
                    raw_urls.append(token)

    # 3. Catch escaped URLs anywhere in the raw HTML (\u002F -> /).
    escaped_pattern = re.compile(r"https?\s*:\\u002F\\u002F[^\"'\s<>,]+|https?://[^\"'\s<>,]+")
    for match in escaped_pattern.finditer(html):
        raw_urls.append(match.group(0))

    # Normalize and filter.
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_urls:
        normalized = normalize_video_url(raw, base_url=base_url)
        if not normalized:
            continue
        if not looks_like_video_url(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)

    return out


def pick_best_video_url(urls: list[str]) -> str | None:
    """Pick the single best video URL from a list of candidates.

    Preference order:
    1. ``.mp4``
    2. ``.mov`` / ``.webm``
    3. ``.m3u8``
    4. Any other URL accepted by :func:`looks_like_video_url`

    Returns ``None`` for an empty list.
    """
    if not urls:
        return None

    def rank(url: str) -> int:
        lower = url.lower()
        if lower.endswith(".mp4"):
            return 0
        if lower.endswith((".mov", ".webm")):
            return 1
        if lower.endswith(".m3u8"):
            return 2
        return 3

    best = min(urls, key=rank)
    if looks_like_video_url(best):
        return best
    return None


def extract_video_url_from_html(html: str, base_url: str | None = None) -> str | None:
    """Convenience wrapper: return the best video URL from HTML, or None."""
    return pick_best_video_url(extract_video_urls_from_html(html, base_url=base_url))


def extract_china_videos(
    candidates: list[Candidate],
    **kwargs: Any,
) -> list[Candidate]:
    """Public convenience wrapper creating :class:`ChinaVideoExtractor` and extracting.

    This module-level alias exists so callers can do
    ``extract_china_videos(candidates, top_n=3)`` without importing the class.
    """
    extractor = ChinaVideoExtractor(**kwargs)
    return extractor.extract_for_candidates(candidates)


class ChinaVideoExtractor:
    """Extract product videos from China marketplace detail pages.

    Uses a :class:`core.browser.BrowserManager` to open candidate pages,
    inspect the DOM, and listen to network traffic for video URLs. Never
    bypasses captchas: if ``detect_captcha`` is True, the candidate is returned
    with ``has_video=False``.
    """

    def __init__(
        self,
        browser_manager: BrowserManager | None = None,
        timeout_ms: int = 15000,
        wait_after_load_ms: int = 1500,
        top_n: int = 5,
    ) -> None:
        self._browser_manager = browser_manager
        self._owns_browser = browser_manager is None
        self.timeout_ms = int(timeout_ms)
        self.wait_after_load_ms = int(wait_after_load_ms)
        self.top_n = int(top_n)

    def _browser(self) -> BrowserManager:
        if self._browser_manager is None:
            self._browser_manager = BrowserManager()
        return self._browser_manager

    def extract_from_candidate(self, candidate: Candidate) -> Candidate:
        """Open the candidate detail page and try to find a product video.

        Returns a copy of ``candidate`` with ``has_video`` / ``video_url`` set
        appropriately. Any error is caught and logged, returning a copy with
        ``has_video=False``.
        """

        def _capture_request(request: Any) -> None:
            try:
                req_url = request.url
            except Exception:
                req_url = str(request)
            if looks_like_video_url(req_url):
                normalized = normalize_video_url(req_url, base_url=url)
                if normalized:
                    network_urls.append(normalized)

        def _capture_response(response: Any) -> None:
            try:
                resp_url = response.url
            except Exception:
                resp_url = str(response)
            if looks_like_video_url(resp_url):
                normalized = normalize_video_url(resp_url, base_url=url)
                if normalized:
                    network_urls.append(normalized)

        if not candidate.url:
            return candidate.model_copy(update={"has_video": False, "video_url": None})

        url = str(candidate.url).strip()
        if not url:
            return candidate.model_copy(update={"has_video": False, "video_url": None})

        page: Any = None
        network_urls: list[str] = []

        try:
            bm = self._browser()
            page = bm.new_page(site="china_video", url=url)

            if self.wait_after_load_ms > 0:
                time.sleep(self.wait_after_load_ms / 1000.0)

            if bm.detect_captcha(page):
                logger.warning(
                    "Captcha detected on China video page, skipping: %s",
                    candidate.url,
                )
                return candidate.model_copy(update={"has_video": False, "video_url": None})

            html_content = page.content()
            if not isinstance(html_content, str):
                html_content = str(html_content)

            # Collect network URLs if the page exposes Playwright-style hooks.
            if hasattr(page, "on"):
                try:
                    page.on("request", _capture_request)
                    page.on("response", _capture_response)
                except Exception:
                    logger.debug("page.on unavailable for network capture", exc_info=True)

            found_urls = extract_video_urls_from_html(html_content, base_url=url)
            if not found_urls and network_urls:
                # Deduplicate network URLs while preserving order.
                seen: set[str] = set()
                for nu in network_urls:
                    if nu not in seen:
                        seen.add(nu)
                        found_urls.append(nu)

            video_url = pick_best_video_url(found_urls)
            if video_url:
                return candidate.model_copy(update={"has_video": True, "video_url": video_url})

            return candidate.model_copy(update={"has_video": False, "video_url": None})

        except Exception:
            logger.debug("Failed to extract video from %s", candidate.url, exc_info=True)
            return candidate.model_copy(update={"has_video": False, "video_url": None})

        finally:
            if page is not None and hasattr(page, "close"):
                try:
                    page.close()
                except Exception:
                    logger.debug("Failed to close page after extraction", exc_info=True)

    def extract_for_candidates(
        self,
        candidates: list[Candidate],
        top_n: int | None = None,
    ) -> list[Candidate]:
        """Extract videos for up to ``top_n`` candidates.

        Errors for one candidate do not stop the batch. Returns copies in the
        same order as ``candidates``.
        """
        limit = top_n if top_n is not None else self.top_n
        limit = max(0, int(limit))
        results: list[Candidate] = []
        for candidate in candidates[:limit]:
            try:
                results.append(self.extract_from_candidate(candidate))
            except Exception:
                logger.debug("Batch extraction failed for one candidate", exc_info=True)
                results.append(
                    candidate.model_copy(update={"has_video": False, "video_url": None})
                )
        return results

    def extract_china_videos(
        self,
        candidates: list[Candidate],
        **kwargs: Any,
    ) -> list[Candidate]:
        """Alias for :meth:`extract_for_candidates`."""
        return self.extract_for_candidates(candidates, **kwargs)

    def close(self) -> None:
        """Close the owned browser manager, if any."""
        if self._owns_browser and self._browser_manager is not None:
            try:
                self._browser_manager.close()
            except Exception:
                logger.debug("Failed to close browser manager", exc_info=True)
            finally:
                self._browser_manager = None

    def __enter__(self) -> "ChinaVideoExtractor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
