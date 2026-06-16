from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from core.browser import BrowserManager
from core.config import settings as default_settings
from core.models import Candidate
from core.storage import Storage

logger = logging.getLogger(__name__)

S1688_IMAGE_SEARCH_URL = "https://www.1688.com/picture/search.htm"
S1688_BASE_URL = "https://www.1688.com"


class S1688SearchError(Exception):
    """Base class for 1688 image search failures."""


class S1688CaptchaError(S1688SearchError):
    """1688 shows a captcha/anti-bot challenge and we do not bypass it."""


class S1688LoginRequiredError(S1688SearchError):
    """1688 requires login for image search."""


class S1688NoResultsError(S1688SearchError):
    """Search completed but 1688 reports no similar products."""


_CAPTCHA_KEYWORDS = (
    "captcha",
    "anti-bot",
    "anti bot",
    "verify",
    "verification",
    "robot",
    "滑块",
    "验证码",
    "人机",
)

_LOGIN_KEYWORDS = (
    "login",
    "log in",
    "sign in",
    "登录",
    "帐号",
    "账号",
    "密码",
    "member",
)

_NO_RESULTS_KEYWORDS = (
    "暂无搜索结果",
    "没有找到",
    "0条结果",
    "no results",
    "0 results",
    "暂无相关",
    "暂无数据",
)


_PRICE_RE = re.compile(r"\d+(?:\.\d+)?")

_FILE_INPUT_SELECTORS = (
    "input[type='file']",
    "input[accept*='image']",
    "input#upload-image",
    "input.image-upload",
)

_IMAGE_SEARCH_BUTTON_SELECTORS = (
    "button[data-spm*='image']",
    "button:has-text('以图搜货')",
    "button:has-text('搜图')",
    "button.camera",
    "i.camera",
    ".image-search-btn",
    "[data-spm*='image']",
)

_RESULT_SELECTORS = (
    "[data-offer-id]",
    ".offer-item",
    ".offer-card",
    ".sm-offer-item",
    ".search-offer",
    ".empty-result",
    ".no-result",
    ".no-match",
)


def _is_valid_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(str(value))
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def is_captcha_html(html: str) -> bool:
    """Return True if the HTML signals a captcha/anti-bot challenge."""
    lowered = html.lower()
    return any(keyword.lower() in lowered for keyword in _CAPTCHA_KEYWORDS)


def is_login_required_html(html: str) -> bool:
    """Return True if the HTML signals a login gate."""
    lowered = html.lower()
    return any(keyword.lower() in lowered for keyword in _LOGIN_KEYWORDS)


def is_empty_results_html(html: str) -> bool:
    """Return True if the HTML signals explicitly empty search results."""
    lowered = html.lower()
    return any(keyword.lower() in lowered for keyword in _NO_RESULTS_KEYWORDS)


def normalize_candidate_url(url: str) -> str:
    """Normalize a 1688 candidate URL to absolute https form.

    - Relative ``/path`` → ``https://www.1688.com/path``.
    - Protocol-relative ``//host/path`` → ``https://host/path``.
    - Absolute URLs are left unchanged.
    """
    if not url:
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/") or not urlparse(url).scheme:
        return urljoin(S1688_BASE_URL, url)
    return url


def _normalize_price(value: str | None) -> float:
    """Extract the first numeric price from 1688 price text."""
    if not value:
        return 0.0
    text = value.strip().replace(",", "")
    # Ranges like "¥ 12.50 - ¥ 20.00" — use the lower bound.
    parts = re.split(r"[-–—]", text)
    first = parts[0].strip()
    match = _PRICE_RE.search(first)
    if match:
        return float(match.group(0))
    return 0.0


def _strip_tags(raw_html: str) -> str:
    """Return text with HTML tags removed and common entities decoded."""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", text).strip()


def _extract_card_url(block: str) -> str:
    """Return normalized absolute URL from an offer card block, or ''."""
    url_match = re.search(r'<a[^>]+href\s*=\s*"([^"]+)"', block, re.I)
    if not url_match:
        url_match = re.search(r'<a[^>]+href\s*=\s*\'([^\']+)\'', block, re.I)
    if not url_match:
        url_match = re.search(r'data-url\s*=\s*"([^"]+)"', block, re.I)
    if not url_match:
        return ""
    return normalize_candidate_url(url_match.group(1).strip())


def parse_results_html(html: str, *, max_results: int | None = None) -> list[Candidate]:
    """Parse 1688 image-search result cards from raw HTML without network access.

    Uses only standard-library ``re`` so it stays deterministic in offline tests.
    Raises domain-specific exceptions when the HTML signals captcha, login gate,
    or explicitly empty results.
    """
    if is_captcha_html(html):
        raise S1688CaptchaError("1688 presented a captcha/verification challenge.")

    if is_login_required_html(html):
        raise S1688LoginRequiredError("1688 requires login for image search.")

    if is_empty_results_html(html):
        raise S1688NoResultsError("1688 reported no similar products.")

    candidates: list[Candidate] = []
    seen_urls: set[str] = set()

    # Try to split by typical 1688 offer card wrappers.
    card_blocks = re.split(
        r"(?i)(<div[^>]*(?:data-offer-id|offer-item|offer-list|offer-card|s-item|sm-offer-item|search-offer|offer-info)[^>]*>|"
        r"<li[^>]*(?:data-offer-id|offer-item|offer-list|offer-card|s-item|sm-offer-item|search-offer|offer-info)[^>]*>)",
        html,
    )
    if len(card_blocks) <= 2:
        card_blocks = re.split(r"(?=<a\s)", html)

    for block in card_blocks:
        if not block.strip() or not re.search(
            r"<img|data-offer-id|offer-item|offer-list|offer-card|s-item|sm-offer-item|search-offer|offer-info",
            block,
            re.I,
        ):
            continue

        try:
            url = _extract_card_url(block)
            if not _is_valid_http_url(url):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = ""
            alt_match = re.search(r'<img[^>]+alt\s*=\s*"([^"]*)"', block, re.I)
            if alt_match:
                title = alt_match.group(1).strip()
            if not title:
                title_match = re.search(
                    r'<(?:div|span|h[2-4]|p|a)[^>]*(?:title|offer-title|subject|product-title|item-title|goods-title|offer-desc)[^>]*>(.*?)</(?:div|span|h[2-4]|p|a)>',
                    block,
                    re.I | re.S,
                )
                if title_match:
                    title = _strip_tags(title_match.group(1)).strip()

            thumb = ""
            for attr in ("data-src", "data-lazy-src", "src", "data-original", "data-img"):
                src_match = re.search(rf'<img[^>]+{attr}\s*=\s*"([^"]+)"', block, re.I)
                if src_match:
                    thumb = src_match.group(1).strip()
                    break
            thumb = normalize_candidate_url(thumb)
            if not _is_valid_http_url(thumb):
                continue

            price_text = ""
            price_match = re.search(
                r'<(?:div|span|em|b|p|strong|i)[^>]*(?:price|price-num|offer-price|amount|cost|unit-price|range-price)[^>]*>(.*?)</(?:div|span|em|b|p|strong|i)>',
                block,
                re.I | re.S,
            )
            if price_match:
                price_text = _strip_tags(price_match.group(1))
            if not price_text:
                # Loose fallback: any currency symbol in the block.
                loose_price = re.search(
                    r'<[^>]*>([^<]*[¥￥$€\d][^<\n]*\d+[^<\n]*)</',
                    block,
                    re.I | re.S,
                )
                if loose_price:
                    price_text = _strip_tags(loose_price.group(1))
            price = _normalize_price(price_text)

            has_video = bool(
                re.search(
                    r'<video|'
                    r'<[^>]*\bclass\s*=\s*"[^"]*(?:video-icon|video-tag|play-video|video-badge|video-flag|main-video)[^"]*"|'
                    r'data-role\s*=\s*"video"|'
                    r'data-video\s*=\s*"[^"]+"|'
                    r'video-icon|video-tag',
                    block,
                    re.I,
                )
            )

            candidates.append(
                Candidate(
                    site="1688",
                    title=title,
                    url=url,
                    thumb_url=thumb,
                    price=price,
                    similarity=0.0,
                    has_video=has_video,
                    video_url=None,
                )
            )
        except Exception as exc:
            logger.debug("Skipping malformed 1688 result card: %s", exc)
            continue

    if not candidates:
        raise S1688NoResultsError("No candidate cards found in 1688 response HTML.")

    if max_results is not None and max_results >= 0:
        candidates = candidates[:max_results]

    return candidates


class S1688ImageSearchDriver:
    """Image-search driver for 1688.com (uses login session via BrowserManager).

    The driver opens 1688's picture search page, uploads the query image, waits
    for results, and collects result cards. Captcha or login walls raise
    specific exceptions instead of being bypassed.
    """

    def __init__(
        self,
        browser_manager: Optional[BrowserManager] = None,
        storage: Optional[Storage] = None,
        max_results: Optional[int] = None,
    ) -> None:
        self._browser_manager = browser_manager
        self._storage = storage
        self._max_results = max_results
        self._owns_browser = browser_manager is None
        if self._storage is None:
            self._storage = Storage()

    def _effective_max_results(self, override: Optional[int] = None) -> int:
        if override is not None:
            return max(1, int(override))
        if self._max_results is not None:
            return max(1, int(self._max_results))
        return max(1, int(default_settings.matcher.max_candidates))

    @staticmethod
    def _make_cache_key(image_path: str | Path, max_results: int) -> str:
        image_bytes = Path(image_path).read_bytes()
        image_sha256 = hashlib.sha256(image_bytes).hexdigest()
        return Storage.make_cache_key(
            "1688:image_search", {"image_sha256": image_sha256, "max_results": max_results}
        )

    def _detect_page_issues(self, page: Any) -> None:
        """Raise 1688-specific exceptions when the page signals captcha/login."""
        if self._browser_manager is not None and self._browser_manager.detect_captcha(page):
            raise S1688CaptchaError("1688 presented a captcha/verification challenge.")

        content = ""
        try:
            content = page.content()
        except Exception:
            pass

        if is_captcha_html(content):
            raise S1688CaptchaError("1688 presented a captcha/verification challenge.")

        if is_login_required_html(content):
            raise S1688LoginRequiredError("1688 requires login for image search.")

    def _find_file_input(self, page: Any) -> Any:
        """Find the file input on 1688 picture-search page.

        Tries several selectors, then falls back to clicking a visible
        image-search trigger button and re-scanning. Returns the element or
        raises S1688SearchError if no input appears.
        """
        for selector in _FILE_INPUT_SELECTORS:
            try:
                element = page.wait_for_selector(selector, timeout=5_000)
                if element is not None:
                    return element
            except PlaywrightTimeoutError:
                continue

        logger.info("No direct file input; trying image-search trigger buttons.")
        for trigger_selector in _IMAGE_SEARCH_BUTTON_SELECTORS:
            try:
                trigger = page.query_selector(trigger_selector)
                if trigger is not None:
                    trigger.click()
                    page.wait_for_timeout(1_000)
                    break
            except Exception:
                continue

        for selector in _FILE_INPUT_SELECTORS:
            try:
                element = page.wait_for_selector(selector, timeout=5_000)
                if element is not None:
                    return element
            except PlaywrightTimeoutError:
                continue

        raise S1688SearchError("1688 image upload input not found.")

    def _wait_for_results_or_timeout(self, page: Any) -> None:
        """Wait until result cards, an explicit empty/no-result marker, or timeout."""
        result_selector = ", ".join(_RESULT_SELECTORS)
        try:
            page.wait_for_selector(result_selector, timeout=20_000)
        except PlaywrightTimeoutError:
            # Results didn't appear in time; the caller will still inspect the page.
            pass

    def _upload_and_search(self, image_path: str | Path) -> str:
        """Open 1688, upload image, wait for results, return result HTML."""
        browser = self._browser_manager
        if browser is None:
            browser = BrowserManager()
            self._browser_manager = browser

        page = browser.new_page(site="1688", url=S1688_IMAGE_SEARCH_URL)
        try:
            self._detect_page_issues(page)

            upload_input = self._find_file_input(page)
            upload_input.set_files(str(Path(image_path).resolve()))

            page.wait_for_load_state("networkidle", timeout=30_000)
            self._wait_for_results_or_timeout(page)

            self._detect_page_issues(page)
            return page.content()
        except PlaywrightTimeoutError as exc:
            logger.warning("1688 image search timed out: %s", exc)
            return page.content()
        finally:
            try:
                page.close()
            except Exception:
                pass

    def search_by_image(
        self,
        image_path: str | Path,
        *,
        max_results: Optional[int] = None,
        use_cache: bool = True,
    ) -> list[Candidate]:
        """Search 1688 by image and return up to ``max_results`` candidates.

        Args:
            image_path: path to the query image (jpg/png/webp).
            max_results: optional override for how many candidates to return.
            use_cache: whether to read/write results from storage cache.

        Returns:
            Ordered list of :class:`core.models.Candidate`.

        Raises:
            S1688CaptchaError: when a captcha/anti-bot wall is detected.
            S1688LoginRequiredError: when 1688 demands login.
            S1688NoResultsError: when the search returns no cards.
            S1688SearchError: when the image file is missing or upload fails.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise S1688SearchError(f"Image not found: {image_path}")

        limit = self._effective_max_results(max_results)

        if use_cache and self._storage is not None:
            cache_key = self._make_cache_key(image_path, limit)
            cached = self._storage.get(cache_key)
            if isinstance(cached, list):
                try:
                    parsed = [Candidate(**item) for item in cached]
                    return parsed[:limit]
                except Exception as exc:
                    logger.warning("Failed to restore cached 1688 results: %s", exc)

        html = self._upload_and_search(image_path)
        candidates = parse_results_html(html, max_results=limit)

        if use_cache and self._storage is not None:
            cache_key = self._make_cache_key(image_path, limit)
            self._storage.set(
                cache_key,
                [candidate.model_dump(mode="json") for candidate in candidates],
                namespace="1688:image_search",
            )

        return candidates

    def close(self) -> None:
        """Release browser only if this driver created it."""
        if self._owns_browser and self._browser_manager is not None:
            try:
                self._browser_manager.close()
            except Exception:
                logger.exception("Failed to close browser manager")
            finally:
                self._browser_manager = None

    def __enter__(self) -> "S1688ImageSearchDriver":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
