from __future__ import annotations

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

ALIBABA_IMAGE_SEARCH_URL = "https://www.alibaba.com/picture/search.htm"
ALIBABA_DOMAIN = "alibaba.com"


class AlibabaSearchError(Exception):
    """Base class for Alibaba image search failures."""


class AlibabaCaptchaError(AlibabaSearchError):
    """Alibaba shows a captcha/anti-bot challenge and we do not bypass it."""


class AlibabaLoginRequiredError(AlibabaSearchError):
    """Alibaba requires login; this driver works without login by default."""


class AlibabaNoResultsError(AlibabaSearchError):
    """Search completed but Alibaba reports no similar products."""


_LOGIN_KEYWORDS = (
    "sign in",
    "log in",
    "login",
    "password",
    " Alibaba Member",
    "Join Free",
    "Create Account",
)

_CAPTCHA_KEYWORDS = (
    "captcha",
    "verify",
    "verification",
    "robot",
    "滑块",
    "验证码",
    "人机",
)

_NO_RESULTS_KEYWORDS = (
    "no matching products",
    "no results",
    "0 results",
    "sorry",
    "try again with different",
)


def _is_valid_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(str(value))
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _normalize_price(value: str | None) -> float:
    if not value:
        return 0.0
    text = value.strip().replace(",", "")
    # Handle ranges like "$2.50 - $4.00" by taking the lower bound.
    parts = re.split(r"[-–—]", text)
    first = parts[0].strip()
    match = re.search(r"\d+(?:\.\d+)?", first)
    if match:
        return float(match.group(0))
    return 0.0


def parse_results_html(html: str) -> list[Candidate]:
    """Parse Alibaba image-search result cards from raw HTML without network access.

    Uses only ``html.parser``/``re`` from the standard library so the function
    stays deterministic and fast in offline tests. Raises domain-specific
    exceptions when the HTML signals captcha, login gate, or explicitly empty
    results.
    """
    lowered = html.lower()

    for keyword in _CAPTCHA_KEYWORDS:
        if keyword.lower() in lowered:
            raise AlibabaCaptchaError("Alibaba presented a captcha/verification challenge.")

    for keyword in _LOGIN_KEYWORDS:
        if keyword.lower() in lowered:
            raise AlibabaLoginRequiredError("Alibaba requires login for image search.")

    for keyword in _NO_RESULTS_KEYWORDS:
        if keyword.lower() in lowered:
            raise AlibabaNoResultsError("Alibaba reported no similar products.")

    candidates: list[Candidate] = []
    seen_urls: set[str] = set()

    # Find result cards by their outer wrapper classes, then extract nested
    # link + image + price. Fallback to any <a> block that contains an <img>.
    card_blocks = re.split(
        r"(?i)(<div[^>]*(?:data-content|product-card|search-card|gallery-offer|offer-item|organic-gallery-offer-outter)[^>]*>)",
        html,
    )
    if len(card_blocks) <= 2:
        card_blocks = re.split(r"(?=<a\s)", html)

    for block in card_blocks:
        if not block.strip() or not re.search(r"<img|data-content|product-card|search-card|gallery-offer|offer-item", block, re.I):
            continue

        try:
            url_match = re.search(r'<a[^>]+href\s*=\s*"([^"]+)"', block, re.I)
            url = url_match.group(1).strip() if url_match else ""
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = urljoin("https://www.alibaba.com", url)
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
                    r'<(?:div|span|h[2-4]|p)[^>]*(?:elements-offer-title-font|product-title|title)[^>]*>(.*?)</(?:div|span|h[2-4]|p)>',
                    block,
                    re.I | re.S,
                )
                if title_match:
                    title = _strip_tags(title_match.group(1)).strip()

            thumb = ""
            for attr in ("data-src", "src"):
                src_match = re.search(rf'<img[^>]+{attr}\s*=\s*"([^"]+)"', block, re.I)
                if src_match:
                    thumb = src_match.group(1).strip()
                    break
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urljoin("https://www.alibaba.com", thumb)
            if not _is_valid_http_url(thumb):
                continue

            price_text = ""
            price_match = re.search(
                r'<(?:div|span)[^>]*(?:elements-offer-price-normal|price|offer-price|search-offer-price)[^>]*>(.*?)</(?:div|span)>',
                block,
                re.I | re.S,
            )
            if price_match:
                price_text = _strip_tags(price_match.group(1))
            price = _normalize_price(price_text)

            has_video = bool(
                re.search(
                    r'<video|class\s*=\s*"[^"]*(?:video-icon|play-video|video-tag|video)[^"]*"|data-role\s*=\s*"video"',
                    block,
                    re.I,
                )
            )

            candidates.append(
                Candidate(
                    site="alibaba",
                    title=title,
                    url=url,
                    thumb_url=thumb,
                    price=price,
                    similarity=0.0,
                    has_video=has_video,
                )
            )
        except Exception as exc:
            logger.debug("Skipping malformed Alibaba result card: %s", exc)
            continue

    if not candidates:
        raise AlibabaNoResultsError("No candidate cards found in Alibaba response HTML.")

    return candidates


def _strip_tags(raw_html: str) -> str:
    """Return text with HTML tags removed and entities decoded."""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return re.sub(r"\s+", " ", text).strip()


class AlibabaImageSearchDriver:
    """Default image-search driver for Alibaba.com (works without login).

    Uses a shared :class:`core.browser.BrowserManager` to open Alibaba's picture
    search page, upload the query image, and collect result cards. Captcha or
    login walls raise specific exceptions instead of being bypassed.
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
        self._owns_storage = storage is None
        if self._storage is None:
            self._storage = Storage()

    def _effective_max_results(self, override: Optional[int] = None) -> int:
        if override is not None:
            return max(1, int(override))
        if self._max_results is not None:
            return max(1, int(self._max_results))
        return max(1, int(default_settings.matcher.max_candidates))

    @staticmethod
    def _make_cache_key(image_path: str | Path) -> str:
        return Storage.make_cache_key("alibaba:image_search", str(Path(image_path).resolve()))

    def _detect_page_issues(self, page: Any) -> None:
        """Raise Alibaba-specific exceptions when the page signals captcha/login."""
        if self._browser_manager is not None and self._browser_manager.detect_captcha(page):
            raise AlibabaCaptchaError("Alibaba presented a captcha/verification challenge.")

        content = ""
        try:
            content = page.content().lower()
        except Exception:
            pass

        for keyword in _CAPTCHA_KEYWORDS:
            if keyword.lower() in content:
                raise AlibabaCaptchaError("Alibaba presented a captcha/verification challenge.")

        for keyword in _LOGIN_KEYWORDS:
            if keyword.lower() in content:
                raise AlibabaLoginRequiredError("Alibaba requires login for image search.")

    def _upload_and_search(self, image_path: str | Path) -> str:
        """Open Alibaba, upload image, wait for results, return result HTML."""
        browser = self._browser_manager
        if browser is None:
            browser = BrowserManager()
            self._browser_manager = browser

        page = browser.new_page(site="alibaba", url=ALIBABA_IMAGE_SEARCH_URL)
        try:
            self._detect_page_issues(page)

            # Wait for the upload input. Alibaba's image search exposes a file input.
            upload_input = page.wait_for_selector(
                "input[type='file']", timeout=15_000
            )
            upload_input.set_files(str(Path(image_path).resolve()))

            # Wait until the URL changes (results page) or the result container appears.
            page.wait_for_load_state("networkidle", timeout=30_000)
            try:
                page.wait_for_selector(
                    "[data-content], .product-card, .search-card, .gallery-offer, "
                    ".organic-gallery-offer-outter, .no-matching-products, .empty-result",
                    timeout=15_000,
                )
            except PlaywrightTimeoutError:
                pass

            self._detect_page_issues(page)
            return page.content()
        except PlaywrightTimeoutError as exc:
            logger.warning("Alibaba image search timed out: %s", exc)
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
        """Search Alibaba by image and return up to ``max_results`` candidates.

        Args:
            image_path: path to the query image (jpg/png/webp).
            max_results: optional override for how many candidates to return.
            use_cache: whether to read/write results from storage cache.

        Returns:
            Ordered list of :class:`core.models.Candidate`.

        Raises:
            AlibabaCaptchaError: when a captcha/anti-bot wall is detected.
            AlibabaLoginRequiredError: when Alibaba demands login.
            AlibabaNoResultsError: when the search returns no cards.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise AlibabaSearchError(f"Image not found: {image_path}")

        limit = self._effective_max_results(max_results)

        if use_cache and self._storage is not None:
            cache_key = self._make_cache_key(image_path)
            cached = self._storage.get(cache_key)
            if isinstance(cached, list):
                try:
                    parsed = [Candidate(**item) for item in cached]
                    return parsed[:limit]
                except Exception as exc:
                    logger.warning("Failed to restore cached Alibaba results: %s", exc)

        html = self._upload_and_search(image_path)
        candidates = parse_results_html(html)

        if use_cache and self._storage is not None:
            cache_key = self._make_cache_key(image_path)
            self._storage.set(
                cache_key,
                [candidate.model_dump(mode="json") for candidate in candidates],
                namespace="alibaba:image_search",
            )

        return candidates[:limit]

    def close(self) -> None:
        """Release browser and storage only if this driver created them."""
        if self._owns_browser and self._browser_manager is not None:
            try:
                self._browser_manager.close()
            except Exception:
                logger.exception("Failed to close browser manager")
            finally:
                self._browser_manager = None

    def __enter__(self) -> "AlibabaImageSearchDriver":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
