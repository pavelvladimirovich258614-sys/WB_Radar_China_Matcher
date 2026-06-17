from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.config import settings as default_settings
from core.models import Product, Review
from core.storage import Storage
from core.wb_public import WBPublic

logger = logging.getLogger(__name__)


class ReviewCollectionResult(BaseModel):
    nmId: int
    imtId: Optional[int] = None
    reviews_count: int = 0
    output_path: Optional[str] = None
    status: str = "ok"
    error: Optional[str] = None


class ReviewsCollectorError(Exception):
    pass


class ProductInputError(ReviewsCollectorError):
    pass


def _resolve_nm_id(value: Any) -> int:
    """Extract ``nmId`` from a supported input type."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ProductInputError(f"Invalid nmId string: {value!r}") from exc
    if isinstance(value, Product):
        if value.nmId is None:
            raise ProductInputError("Product has no nmId")
        return value.nmId
    if isinstance(value, dict):
        nm_id = value.get("nmId")
        if nm_id is None:
            raise ProductInputError(f"Dict input has no nmId: {value!r}")
        return int(nm_id)
    raise ProductInputError(f"Unsupported input type for nmId: {type(value).__name__}")


def _resolve_imt_id(value: Any) -> Optional[int]:
    """Extract ``imtId`` from a supported input type if present."""
    if isinstance(value, Product):
        return value.imtId
    if isinstance(value, dict):
        imt_id = value.get("imtId")
        return int(imt_id) if imt_id is not None else None
    return None


def _resolve_product(value: Any) -> Product:
    """Normalize input to a ``Product`` instance."""
    if isinstance(value, Product):
        return value
    if isinstance(value, BaseModel):
        return Product(**value.model_dump(mode="json"))
    if isinstance(value, dict):
        return Product(**value)
    if isinstance(value, (int, str)):
        return Product(nmId=_resolve_nm_id(value), name="", brand="")
    raise ProductInputError(f"Unsupported input type: {type(value).__name__}")


def _reviews_output_path(output_root: Path, nm_id: int) -> Path:
    return output_root / "reviews" / f"{nm_id}.json"


def _save_reviews(
    reviews: list[Review],
    output_root: Path,
    nm_id: int,
) -> Path:
    storage = Storage(output_dir=output_root / "reviews")
    path = storage.save_json(
        reviews,
        f"{nm_id}.json",
        ensure_ascii=False,
        indent=2,
    )
    return path


def collect_reviews_for_product(
    product_or_nm_id: Any,
    wb_client: Optional[WBPublic] = None,
    output_root: Optional[Path] = None,
    max_count: int = 1000,
) -> ReviewCollectionResult:
    """Collect WB reviews for a single product and save them as JSON.

    Args:
        product_or_nm_id: ``Product``/``ViralProduct``/dict/int/nmId string.
        wb_client: Injected ``WBPublic`` client. Created/closed if None.
        output_root: Override output directory. Defaults to ``settings.paths.output``.
        max_count: Maximum number of reviews to fetch.

    Returns:
        ``ReviewCollectionResult`` with status, path and review count.
    """
    output_base = output_root or Path(default_settings.paths.output)

    try:
        product = _resolve_product(product_or_nm_id)
        nm_id = product.nmId
        imt_id = product.imtId
    except ProductInputError as exc:
        return ReviewCollectionResult(
            nmId=0,
            status="error",
            error=str(exc),
        )

    owns_client = wb_client is None
    client = wb_client or WBPublic()

    try:
        if imt_id is None:
            try:
                resolved = client.get_detail(nm_id)
                imt_id = resolved.imtId
                if product.name == "" and resolved.name:
                    product = resolved
            except Exception as exc:
                logger.warning(
                    "Failed to resolve imtId for nmId=%s: %s",
                    nm_id,
                    exc,
                )
                return ReviewCollectionResult(
                    nmId=nm_id,
                    status="error",
                    error=f"detail lookup failed: {exc}",
                )

        if imt_id is None:
            return ReviewCollectionResult(
                nmId=nm_id,
                status="error",
                error="no imtId available",
            )

        try:
            reviews = client.get_reviews(imt_id, max_count=max_count)
        except Exception as exc:
            logger.warning(
                "Failed to fetch reviews for nmId=%s imtId=%s: %s",
                nm_id,
                imt_id,
                exc,
            )
            return ReviewCollectionResult(
                nmId=nm_id,
                imtId=imt_id,
                status="error",
                error=f"reviews fetch failed: {exc}",
            )

        try:
            output_path = _save_reviews(reviews, output_base, nm_id)
        except Exception as exc:
            return ReviewCollectionResult(
                nmId=nm_id,
                imtId=imt_id,
                reviews_count=len(reviews),
                status="error",
                error=f"save failed: {exc}",
            )

        return ReviewCollectionResult(
            nmId=nm_id,
            imtId=imt_id,
            reviews_count=len(reviews),
            output_path=str(output_path),
            status="ok",
        )
    finally:
        if owns_client:
            client.close()


def collect_reviews_for_products(
    products: list[Any],
    wb_client: Optional[WBPublic] = None,
    output_root: Optional[Path] = None,
    max_count: int = 1000,
) -> list[ReviewCollectionResult]:
    """Batch collect reviews for multiple products.

    Errors for individual products are returned as results with ``status="error"``
    and do not abort the batch.
    """
    if not products:
        return []

    owns_client = wb_client is None
    client = wb_client or WBPublic()

    try:
        results: list[ReviewCollectionResult] = []
        for item in products:
            try:
                result = collect_reviews_for_product(
                    item,
                    wb_client=client,
                    output_root=output_root,
                    max_count=max_count,
                )
            except Exception as exc:
                logger.exception("Unexpected failure collecting reviews")
                nm_id = 0
                try:
                    nm_id = _resolve_nm_id(item)
                except Exception:
                    pass
                result = ReviewCollectionResult(
                    nmId=nm_id,
                    status="error",
                    error=f"unexpected: {exc}",
                )
            results.append(result)
        return results
    finally:
        if owns_client:
            client.close()
