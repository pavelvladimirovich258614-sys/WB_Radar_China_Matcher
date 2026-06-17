from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Optional

from core.models import Review
from core.wb_public import WBPublic

logger = logging.getLogger(__name__)


class ReviewVideoItem:
    """A single WB review that contains a video reference.

    Lightweight dataclass-style object. Keeps the review id, rating, text,
    and the direct video URL so downstream modules (download, description writer)
    do not need to re-parse :class:`Review`.
    """

    def __init__(
        self,
        *,
        review_id: str,
        nmId: Optional[int],
        rating: float,
        text: str,
        video_url: str,
        pros: list[str] | None = None,
        cons: list[str] | None = None,
    ) -> None:
        self.review_id = review_id
        self.nmId = nmId
        self.rating = float(rating)
        self.text = text or ""
        self.video_url = video_url
        self.pros = list(pros or [])
        self.cons = list(cons or [])

    def __repr__(self) -> str:
        return (
            f"ReviewVideoItem(review_id={self.review_id!r}, "
            f"nmId={self.nmId}, rating={self.rating}, "
            f"video_url={self.video_url!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "nmId": self.nmId,
            "rating": self.rating,
            "text": self.text,
            "video_url": self.video_url,
            "pros": self.pros,
            "cons": self.cons,
        }


def _review_has_text(review: Review) -> bool:
    """Return True when the review carries meaningful text or pros/cons."""
    if (review.text or "").strip():
        return True
    return bool(review.pros or review.cons)


def _review_usefulness_score(review: Review) -> float:
    """Higher score = more useful for downstream content generation.

    Boosts:
    - presence of text/pros/cons;
    - higher star rating.
    """
    score = 0.0
    if _review_has_text(review):
        score += 1.0
    score += 0.2 * (review.rating or 0.0)
    return score


def extract_review_videos_from_reviews(reviews: list[Review]) -> list[ReviewVideoItem]:
    """Filter ``reviews`` down to items that contain a ``video_url``.

    The result is sorted by usefulness (text + high rating first). A broken
    review is logged and skipped instead of crashing the batch.
    """
    items: list[tuple[float, ReviewVideoItem]] = []
    for review in reviews:
        try:
            if not review.video_url:
                continue
            item = ReviewVideoItem(
                review_id=review.id,
                nmId=review.nmId,
                rating=review.rating,
                text=review.text,
                video_url=review.video_url,
                pros=review.pros,
                cons=review.cons,
            )
        except Exception as exc:
            logger.debug("Skipping malformed review %s: %s", review.id, exc)
            continue
        items.append((_review_usefulness_score(review), item))

    items.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in items]


def get_review_videos(
    nmId: int,
    *,
    wb_client: Optional[WBPublic] = None,
    max_count: int = 1000,
    detail_provider: Callable[[int], int] | None = None,
) -> list[ReviewVideoItem]:
    """Return video-carrying WB reviews for a given ``nmId``.

    Steps:
    1. Resolve ``nmId`` -> ``imtId``. If ``detail_provider`` is supplied it is
       called with ``nmId`` and must return ``imtId``; otherwise a default
       ``WBPublic.get_detail`` call is used. The default path creates a transient
       ``WBPublic`` instance and closes it afterwards.
    2. Fetch up to ``max_count`` reviews via ``WBPublic.get_reviews``.
    3. Filter and sort video reviews with
       :func:`extract_review_videos_from_reviews`.

    Args:
        nmId: Wildberries product number.
        wb_client: Optional injected ``WBPublic`` used to fetch reviews. If not
            provided, a fresh instance is created and closed on return.
        max_count: Maximum reviews to read from the WB endpoint.
        detail_provider: Optional callable ``nmId -> imtId`` for tests or
            callers that already know the ``imtId``.

    Returns:
        Sorted list of :class:`ReviewVideoItem` with direct video URLs.
    """
    if detail_provider is not None:
        imtId = detail_provider(nmId)
    else:
        detail_wb = wb_client if wb_client is not None else WBPublic()
        try:
            product = detail_wb.get_detail(nmId)
            imtId = product.imtId
        finally:
            if wb_client is None:
                detail_wb.close()

    if not imtId:
        logger.warning("Cannot resolve imtId for nmId=%s; no review videos", nmId)
        return []

    reviews_wb = wb_client if wb_client is not None else WBPublic()
    try:
        reviews = reviews_wb.get_reviews(imtId, max_count=max_count)
    finally:
        if wb_client is None:
            reviews_wb.close()

    return extract_review_videos_from_reviews(reviews)
