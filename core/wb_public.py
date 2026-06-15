from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

import httpx
from pydantic import ValidationError
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import Settings
from core.config import settings as default_settings
from core.models import Product, Review

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 15.0
DETAIL_PATH = "/cards/v2/detail"
SEARCH_PATH = "/exactmatch/ru/common/v4/search"
FEEDBACKS_PATH = "/api/v1/feedbacks/site"
FEEDBACKS_PAGE_SIZE = 30

_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

_PHOTO_KEY_PRIORITY = ("full", "large", "origin", "big", "medium", "small", "thumb", "url", "src")


class WBPublicError(Exception):
    pass


class WBNotFoundError(WBPublicError):
    pass


class WBRequestError(WBPublicError):
    pass


class WBParseError(WBPublicError):
    pass


class _WBTransientHTTPError(WBRequestError):
    pass


def build_wb_image_url(nmId: int, size: str = "big") -> str:
    vol = nmId // 100_000
    part = nmId // 1_000
    basket = (vol // 144) + 1
    return (
        f"https://basket-{basket:02d}.wbbasket.ru/vol{vol}/part{part}/"
        f"{nmId}/images/{size}/1.jpg"
    )


def _parse_price(product: dict[str, Any]) -> float:
    for key in ("salePriceU", "priceU"):
        value = product.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return value / 100.0
    for key in ("sale_price", "price"):
        value = product.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _to_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _looks_like_media_url(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    return lowered.startswith("http") or lowered.endswith(".mp4")


def _url_from_value(value: Any) -> Optional[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if isinstance(value, dict):
        for key in _PHOTO_KEY_PRIORITY:
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        for inner in value.values():
            if isinstance(inner, str) and _looks_like_media_url(inner):
                return inner.strip()
    return None


def _first_media_url(value: Any) -> Optional[str]:
    if value is None:
        return None
    url = _url_from_value(value)
    if url:
        return url
    if isinstance(value, list):
        for item in value:
            url = _url_from_value(item)
            if url:
                return url
    return None


def _find_mp4_url(obj: Any, depth: int = 0) -> Optional[str]:
    if depth > 8 or obj is None:
        return None
    if isinstance(obj, str):
        return obj.strip() if obj.strip().lower().endswith(".mp4") else None
    if isinstance(obj, dict):
        for inner in obj.values():
            found = _find_mp4_url(inner, depth + 1)
            if found:
                return found
    elif isinstance(obj, list):
        for inner in obj:
            found = _find_mp4_url(inner, depth + 1)
            if found:
                return found
    return None


def extract_review_video_url(raw_review: dict[str, Any]) -> Optional[str]:
    if not isinstance(raw_review, dict):
        return None
    for key in ("video_url", "videoUrl", "video"):
        url = _first_media_url(raw_review.get(key))
        if url:
            return url
    url = _first_media_url(raw_review.get("videos"))
    if url:
        return url
    for key in ("media", "metadata"):
        url = _find_mp4_url(raw_review.get(key))
        if url:
            return url
    return _find_mp4_url(raw_review)


def _photo_url_from_item(item: Any) -> Optional[str]:
    if isinstance(item, str):
        stripped = item.strip()
        return stripped if stripped else None
    if isinstance(item, dict):
        for key in _PHOTO_KEY_PRIORITY:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def extract_review_photo_urls(raw_review: dict[str, Any]) -> list[str]:
    if not isinstance(raw_review, dict):
        return []
    photos = raw_review.get("photos")
    if photos is None:
        photos = raw_review.get("photoUrls")
    if photos is None:
        photos = raw_review.get("images")
    if photos is None:
        return []

    items: list[Any] = photos if isinstance(photos, list) else [photos]
    collected: list[str] = []
    for item in items:
        url = _photo_url_from_item(item)
        if url:
            collected.append(url)
    return _dedup(collected)


class WBPublic:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.Client] = None,
        *,
        retry_wait_min: float = 1.0,
        retry_wait_max: float = 10.0,
    ) -> None:
        self._settings = settings or default_settings
        wb = self._settings.wb
        self._base_url = str(wb.hosts.card).rstrip("/")
        self._search_url = f"{str(wb.hosts.search).rstrip('/')}{SEARCH_PATH}"
        self._feedbacks_url = f"{str(wb.hosts.feedbacks).rstrip('/')}{FEEDBACKS_PATH}"
        self._dest = wb.dest
        self._rate_limit_rps = float(wb.rate_limit_rps)
        self._max_attempts = max(1, int(wb.retries))
        self._retry_wait_min = retry_wait_min
        self._retry_wait_max = retry_wait_max
        self._min_interval = (
            (1.0 / self._rate_limit_rps) if self._rate_limit_rps > 0 else 0.0
        )
        self._last_request_time = 0.0
        self._headers = dict(_DEFAULT_HEADERS)
        self._headers_refreshed = False
        self._owns_client = client is None
        self._client = (
            client
            if client is not None
            else httpx.Client(timeout=DEFAULT_TIMEOUT_SEC, headers=self._headers)
        )

    def __enter__(self) -> "WBPublic":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get_detail(self, nmId: int) -> Product:
        self._headers_refreshed = False
        payload = self._retry_call(self._detail_request, nmId)
        return self._parse_product(payload, nmId)

    def search(
        self,
        query: str,
        sort: str = "popular",
        pages: int = 1,
    ) -> list[Product]:
        if pages < 1:
            return []
        self._headers_refreshed = False
        results: list[Product] = []
        for page in range(1, pages + 1):
            payload = self._retry_call(self._search_request, query, sort, page)
            products_raw = self._extract_products(payload, query, page)
            if not products_raw:
                break
            for raw in products_raw:
                results.append(self._build_product(raw))
        return results

    def get_reviews(self, imtId: int, max_count: int = 1000) -> list[Review]:
        if max_count <= 0:
            return []
        self._headers_refreshed = False
        results: list[Review] = []
        seen_ids: set[str] = set()
        skip = 0
        while len(results) < max_count:
            payload = self._retry_call(self._feedbacks_request, imtId, skip)
            raw_feedbacks = self._extract_feedbacks(payload, imtId, skip)
            if not raw_feedbacks:
                break
            added = 0
            for raw in raw_feedbacks:
                if len(results) >= max_count:
                    break
                review = self._build_review(raw)
                if review.id in seen_ids:
                    continue
                seen_ids.add(review.id)
                results.append(review)
                added += 1
            if len(results) >= max_count:
                break
            if len(raw_feedbacks) < FEEDBACKS_PAGE_SIZE:
                break
            if added == 0:
                break
            skip += FEEDBACKS_PAGE_SIZE
        return results

    def _retry_call(self, fn: Callable[..., dict[str, Any]], *args: Any) -> dict[str, Any]:
        retryer = Retrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(
                multiplier=1,
                min=self._retry_wait_min,
                max=self._retry_wait_max,
            ),
            retry=retry_if_exception_type(_WBTransientHTTPError),
            reraise=True,
        )
        try:
            return retryer(fn, *args)
        except _WBTransientHTTPError as exc:
            raise WBRequestError(str(exc)) from exc

    def _detail_request(self, nmId: int) -> dict[str, Any]:
        return self._request_once(
            "GET",
            f"{self._base_url}{DETAIL_PATH}",
            f"nmId={nmId}",
            params={"appType": 1, "curr": "rub", "dest": self._dest, "nm": str(nmId)},
        )

    def _search_request(self, query: str, sort: str, page: int) -> dict[str, Any]:
        return self._request_once(
            "GET",
            self._search_url,
            f"query={query!r} page={page}",
            params={
                "appType": 1,
                "curr": "rub",
                "dest": self._dest,
                "query": query,
                "resultset": "catalog",
                "sort": sort,
                "page": page,
                "spp": 30,
                "suppressSpellcheck": "false",
            },
        )

    def _feedbacks_request(self, imtId: int, skip: int) -> dict[str, Any]:
        return self._request_once(
            "POST",
            self._feedbacks_url,
            f"imtId={imtId} skip={skip}",
            json_body={
                "imtId": imtId,
                "take": FEEDBACKS_PAGE_SIZE,
                "skip": skip,
                "order": "dateDesc",
            },
        )

    def _request_once(
        self,
        method: str,
        url: str,
        context: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        self._enforce_rate_limit()
        try:
            if method == "GET":
                response = self._client.get(url, params=params, headers=dict(self._headers))
            else:
                response = self._client.post(url, json=json_body, headers=dict(self._headers))
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise _WBTransientHTTPError(
                f"transport error for {context}: {exc!r}"
            ) from exc

        status = response.status_code
        if status == 200:
            try:
                return response.json()
            except (ValueError, TypeError) as exc:
                raise WBParseError(
                    f"non-JSON response for {context}: {exc!r}"
                ) from exc

        if status == 429 or 500 <= status < 600:
            raise _WBTransientHTTPError(f"WB HTTP {status} for {context}")

        if not self._headers_refreshed:
            self._refresh_headers()
            self._headers_refreshed = True
            logger.warning(
                "WB returned HTTP %s for %s; refreshing headers and retrying once",
                status,
                context,
            )
            return self._request_once(
                method, url, context, params=params, json_body=json_body
            )

        raise WBRequestError(
            f"WB HTTP {status} for {context} after header refresh"
        )

    def _enforce_rate_limit(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    def _refresh_headers(self) -> None:
        self._headers = dict(_DEFAULT_HEADERS)
        self._headers["Referer"] = "https://www.wildberries.ru/"
        self._headers["Origin"] = "https://www.wildberries.ru"

    def _extract_products(
        self, payload: dict[str, Any], query: str, page: int
    ) -> list[dict[str, Any]]:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise WBParseError(
                f"unexpected WB search structure for query={query!r} page={page}: "
                "no 'data' mapping"
            )
        products = data.get("products")
        if not isinstance(products, list):
            raise WBParseError(
                f"unexpected WB search structure for query={query!r} page={page}: "
                "'products' is not a list"
            )
        return products

    def _extract_feedbacks(
        self, payload: dict[str, Any], imtId: int, skip: int
    ) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            raise WBParseError(
                f"unexpected WB feedbacks structure for imtId={imtId} skip={skip}: "
                "response is not a mapping"
            )
        container = payload.get("data")
        container = container if isinstance(container, dict) else payload
        feedbacks = container.get("feedbacks")
        if feedbacks is None:
            raise WBParseError(
                f"unexpected WB feedbacks structure for imtId={imtId} skip={skip}: "
                "no 'feedbacks' field"
            )
        if not isinstance(feedbacks, list):
            raise WBParseError(
                f"unexpected WB feedbacks structure for imtId={imtId} skip={skip}: "
                "'feedbacks' is not a list"
            )
        return feedbacks

    def _build_product(
        self, raw: dict[str, Any], nmId_override: Optional[int] = None
    ) -> Product:
        nmId = nmId_override if nmId_override is not None else raw.get("id")
        rating = raw.get("rating")
        if rating is None:
            rating = raw.get("reviewRating", 0.0)
        try:
            return Product(
                nmId=nmId,
                imtId=raw.get("root"),
                name=raw.get("name"),
                brand=raw.get("brand"),
                price=_parse_price(raw),
                feedbacks=raw.get("feedbacks", 0),
                rating=rating,
                img_url=build_wb_image_url(nmId),
                url=f"https://www.wildberries.ru/catalog/{nmId}/detail.aspx",
            )
        except ValidationError as exc:
            raise WBParseError(
                f"failed to map WB product to Product: {exc}"
            ) from exc

    def _build_review(self, raw: dict[str, Any]) -> Review:
        raw_id = raw.get("id")
        review_id = str(raw_id) if raw_id is not None else ""
        text = raw.get("text") or ""
        rating_value = raw.get("rating")
        if rating_value is None:
            rating_value = raw.get("stars", 0.0)
        try:
            rating_float = float(rating_value)
        except (TypeError, ValueError):
            rating_float = 0.0
        date_value = raw.get("createdDate") or raw.get("date") or ""
        try:
            return Review(
                id=review_id,
                nmId=raw.get("nmId"),
                text=text,
                rating=rating_float,
                date=date_value,
                pros=_to_str_list(raw.get("pros")),
                cons=_to_str_list(raw.get("cons")),
                photo_urls=extract_review_photo_urls(raw),
                video_url=extract_review_video_url(raw),
            )
        except ValidationError as exc:
            raise WBParseError(
                f"failed to map WB feedback to Review: {exc}"
            ) from exc

    def _parse_product(
        self, payload: dict[str, Any], nmId: int
    ) -> Product:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise WBParseError(
                f"unexpected WB detail structure for nmId={nmId}: no 'data' mapping"
            )
        products = data.get("products")
        if not isinstance(products, list):
            raise WBParseError(
                f"unexpected WB detail structure for nmId={nmId}: 'products' is not a list"
            )
        if not products:
            raise WBNotFoundError(f"WB returned no products for nmId={nmId}")

        chosen: Optional[dict[str, Any]] = None
        for candidate in products:
            if candidate.get("id") == nmId:
                chosen = candidate
                break
        if chosen is None:
            chosen = products[0]

        return self._build_product(chosen, nmId_override=nmId)
