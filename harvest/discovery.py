from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.config import settings as default_settings
from core.models import Product, Review
from core.storage import Storage
from core.wb_public import WBPublic

logger = logging.getLogger(__name__)


class ViralProduct(BaseModel):
    nmId: int
    imtId: Optional[int] = None
    name: str
    brand: str = ""
    price: float = Field(ge=0, default=0.0)
    feedbacks: int = Field(ge=0, default=0)
    rating: float = Field(ge=0, le=5, default=0.0)
    velocity_7d: int = 0
    velocity_30d: int = 0
    viral_score: float = 0.0
    img_url: Optional[str] = None
    url: Optional[str] = None


class ViralResult(BaseModel):
    query: str
    products: list[ViralProduct]
    csv_path: Optional[str] = None


_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def parse_review_date(value: Any, *, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse a review date string into an aware UTC datetime.

    Supports ISO 8601 prefixes and plain YYYY-MM-DD dates.
    Returns None for missing/invalid values.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    match = _ISO_RE.match(text)
    if not match:
        return None
    try:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        candidate = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    if now is not None and candidate > now:
        return None
    return candidate


def count_reviews_since(
    reviews: list[Review],
    days: int,
    *,
    now: Optional[datetime] = None,
) -> int:
    """Count reviews newer than ``days`` days from ``now``."""
    if days <= 0:
        return 0
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    count = 0
    for review in reviews:
        parsed = parse_review_date(review.date, now=now)
        if parsed is not None and parsed >= cutoff:
            count += 1
    return count


def compute_velocity(
    reviews: list[Review],
    *,
    now: Optional[datetime] = None,
) -> tuple[int, int]:
    """Return (velocity_7d, velocity_30d) review counts."""
    return (
        count_reviews_since(reviews, 7, now=now),
        count_reviews_since(reviews, 30, now=now),
    )


def normalize_values(values: list[float]) -> list[float]:
    """Min-max normalize values to [0, 1].

    All-equal or single-value inputs become zeros (no discriminative signal).
    Empty input returns an empty list.
    """
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    span = hi - lo
    if span <= 0:
        return [0.0] * len(values)
    return [(v - lo) / span for v in values]


def rating_closeness(rating: float, target: float = 4.6) -> float:
    """Score how close ``rating`` is to ``target`` on a 0..5 scale.

    Returns 1.0 at ``target`` and falls linearly to 0.0 at distance >= 1.4.
    """
    distance = abs(rating - target)
    max_distance = 1.4
    if distance >= max_distance:
        return 0.0
    return 1.0 - (distance / max_distance)


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _sanitize_query_for_path(query: str) -> str:
    """Replace path-unsafe characters with underscores."""
    sanitized = re.sub(r"[^\w\- ]+", "_", query, flags=re.UNICODE)
    return "_".join(part for part in sanitized.split("_") if part).strip() or "niche"


def compute_viral_scores(
    products_with_reviews: list[tuple[Product, list[Review]]],
    *,
    now: Optional[datetime] = None,
) -> list[ViralProduct]:
    """Compute viral scores for each product-review pair.

    Returns products sorted by ``viral_score`` descending.
    """
    if not products_with_reviews:
        return []

    scored: list[ViralProduct] = []
    velocities_7d: list[float] = []
    velocities_30d: list[float] = []
    feedback_counts: list[float] = []
    rating_scores: list[float] = []

    for product, reviews in products_with_reviews:
        velocity_7d, velocity_30d = compute_velocity(reviews, now=now)
        velocities_7d.append(float(velocity_7d))
        velocities_30d.append(float(velocity_30d))
        feedback_counts.append(float(product.feedbacks))
        rating_scores.append(rating_closeness(product.rating))

    norm_7d = normalize_values(velocities_7d)
    norm_feedbacks = normalize_values(feedback_counts)

    for idx, (product, _reviews) in enumerate(products_with_reviews):
        velocity_7d, velocity_30d = compute_velocity(_reviews, now=now)
        viral_score = (
            0.5 * norm_7d[idx]
            + 0.3 * norm_feedbacks[idx]
            + 0.2 * rating_scores[idx]
        )
        scored.append(
            ViralProduct(
                nmId=product.nmId,
                imtId=product.imtId,
                name=product.name,
                brand=product.brand,
                price=product.price,
                feedbacks=product.feedbacks,
                rating=product.rating,
                velocity_7d=velocity_7d,
                velocity_30d=velocity_30d,
                viral_score=round(viral_score, 6),
                img_url=product.img_url,
                url=product.url,
            )
        )

    scored.sort(key=lambda item: item.viral_score, reverse=True)
    return scored


def niche(
    query: str,
    pages: int = 1,
    top_n: int = 20,
    wb_client: Optional[WBPublic] = None,
    output_root: Optional[Path] = None,
    *,
    now: Optional[datetime] = None,
) -> ViralResult:
    """Discover viral products for a WB niche.

    Steps:
    1. Search WB for ``query`` across ``pages``.
    2. Take ``top_n`` products by total feedbacks.
    3. Fetch reviews for each product with ``imtId``.
    4. Compute velocity_7d, velocity_30d and viral_score.
    5. Sort by viral_score descending and export CSV to
       ``output/viral/<query>_<date>.csv``.

    Args:
        query: Niche search query.
        pages: Number of WB search pages to load.
        top_n: How many top-by-feedbacks products receive full review analysis.
        wb_client: Injected WBPublic client. Created/closed if None.
        output_root: Override output directory. Defaults to ``settings.paths.output``.
        now: Optional reference datetime for velocity windows.

    Returns:
        ViralResult containing sorted ViralProduct list and CSV path.
    """
    if not query or not query.strip():
        return ViralResult(query=query or "", products=[], csv_path=None)

    pages = max(1, pages)
    top_n = max(1, top_n)
    owns_client = wb_client is None
    client = wb_client or WBPublic()

    try:
        products = client.search(query, pages=pages)
        if not products:
            return ViralResult(query=query, products=[], csv_path=None)

        top_products = sorted(
            products,
            key=lambda p: p.feedbacks,
            reverse=True,
        )[:top_n]

        products_with_reviews: list[tuple[Product, list[Review]]] = []
        for product in top_products:
            imt_id = product.imtId
            if imt_id is None:
                continue
            try:
                reviews = client.get_reviews(imt_id, max_count=1000)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch reviews for nmId=%s imtId=%s: %s",
                    product.nmId,
                    imt_id,
                    exc,
                )
                reviews = []
            products_with_reviews.append((product, reviews))

        scored = compute_viral_scores(products_with_reviews, now=now)

        base_output = output_root or Path(default_settings.paths.output)
        storage = Storage(output_dir=base_output / "viral")
        query_part = _sanitize_query_for_path(query)
        csv_name = f"{query_part}_{_today_str()}.csv"
        csv_path_obj = storage.save_csv(scored, csv_name)
        csv_path = str(csv_path_obj)
    finally:
        if owns_client:
            client.close()

    return ViralResult(query=query, products=scored, csv_path=csv_path)
