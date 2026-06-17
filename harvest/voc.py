from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from core.config import settings as default_settings
from core.llm import get_provider
from core.llm.base import LLMJSONError, LLMProvider
from core.models import Review, VoC, VocItem
from core.storage import Storage

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 40

VOC_CATEGORIES = [
    "боли",
    "желания",
    "страхи",
    "триггеры",
    "восторги",
    "возражения",
    "язык_клиента",
]

_VOC_JSON_SCHEMA = {
    "type": "object",
    "required": VOC_CATEGORIES,
    "properties": {
        category: {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "frequency"],
                "properties": {
                    "text": {"type": "string"},
                    "frequency": {"type": "integer"},
                    "quote": {"type": "string"},
                    "source_review_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        }
        for category in VOC_CATEGORIES
    },
}


class VoCAnalyzerError(Exception):
    pass


class ReviewsLoadError(VoCAnalyzerError):
    pass


class VoCAnalysisError(VoCAnalyzerError):
    pass


def load_reviews_for_voc(
    path_or_nm_id: Path | int | str | None = None,
    reviews: list[Review] | None = None,
    output_root: Path | None = None,
) -> tuple[list[Review], Optional[int]]:
    """Load a list of reviews for VoC analysis.

    Args:
        path_or_nm_id: Path to a reviews JSON file or a WB nmId. If nmId is
            provided, the file is read from ``output/reviews/<nmId>.json``.
        reviews: Optional ready list of ``Review`` objects (takes precedence).
        output_root: Override the output directory.

    Returns:
        Tuple of (reviews list, nmId or None).
    """
    if reviews is not None:
        return reviews, None

    if path_or_nm_id is None:
        return [], None

    if isinstance(path_or_nm_id, str):
        try:
            nm_id = int(path_or_nm_id)
        except ValueError:
            path = Path(path_or_nm_id)
            nm_id = None
        else:
            path = _reviews_json_path(output_root, nm_id)
    elif isinstance(path_or_nm_id, int):
        nm_id = path_or_nm_id
        path = _reviews_json_path(output_root, nm_id)
    else:
        path = path_or_nm_id
        nm_id = None

    if not path.exists():
        raise ReviewsLoadError(f"reviews file not found: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewsLoadError(f"failed to read reviews from {path}: {exc}") from exc

    if not isinstance(raw, list):
        raise ReviewsLoadError(f"expected JSON list in {path}, got {type(raw).__name__}")

    parsed: list[Review] = []
    for idx, item in enumerate(raw):
        try:
            parsed.append(Review(**item))
        except Exception as exc:
            logger.warning("Skipping invalid review %s in %s: %s", idx, path, exc)

    if nm_id is None:
        nm_id = _extract_nm_id_from_path(path)

    return parsed, nm_id


def _reviews_json_path(output_root: Path | None, nm_id: int) -> Path:
    base = output_root or Path(default_settings.paths.output)
    return base / "reviews" / f"{nm_id}.json"


def _extract_nm_id_from_path(path: Path) -> Optional[int]:
    try:
        return int(path.stem)
    except ValueError:
        return None


def chunk_reviews(reviews: list[Review], batch_size: int = DEFAULT_BATCH_SIZE) -> list[list[Review]]:
    """Split reviews into fixed-size batches."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [
        reviews[i : i + batch_size]
        for i in range(0, len(reviews), batch_size)
    ]


def _format_review_for_prompt(review: Review) -> dict[str, Any]:
    return {
        "id": review.id,
        "rating": review.rating,
        "text": review.text,
        "pros": review.pros,
        "cons": review.cons,
    }


def build_voc_prompt(reviews: list[Review]) -> list[dict[str, str]]:
    """Build a chat prompt that asks the LLM to extract VoC data.

    Args:
        reviews: Batch of reviews to analyze.

    Returns:
        Messages list for ``LLMProvider.complete_json``.
    """
    data = [_format_review_for_prompt(r) for r in reviews]
    categories = ", ".join(VOC_CATEGORIES)
    schema = json.dumps(_VOC_JSON_SCHEMA, ensure_ascii=False, indent=2)
    user_content = (
        "Проанализируй отзывы на Wildberries и верни JSON-объект со следующими категориями: "
        f"{categories}.\n\n"
        "Каждый элемент должен содержать:\n"
        '- "text" — краткая формулировка инсайта;\n'
        '- "frequency" — сколько раз встречается (целое число, минимум 1);\n'
        '- "quote" — дословная цитата из отзыва (опционально);\n'
        '- "source_review_ids" — список ID отзывов, в которых встречается.\n\n'
        "Вот отзывы:\n"
        f"{json.dumps(data, ensure_ascii=False, indent=2)}\n\n"
        "Ответь ТОЛЬКО JSON-объектом по схеме:\n"
        f"{schema}"
    )
    return [
        {
            "role": "system",
            "content": (
                "Ты аналитик отзывов Wildberries. "
                "Извлекай боли, желания, страхи, триггеры покупки, восторги, "
                "возражения и характерный язык клиента. "
                "Отвечай только валидным JSON-объектом."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def _parse_voc_item(raw: Any) -> VocItem | None:
    if not isinstance(raw, dict):
        return None
    text = str(raw.get("text", "")).strip()
    if not text:
        return None
    try:
        frequency = max(1, int(raw.get("frequency", 1)))
    except (TypeError, ValueError):
        frequency = 1
    quote = raw.get("quote")
    if quote is not None:
        quote = str(quote).strip() or None
    source_ids = raw.get("source_review_ids", [])
    if not isinstance(source_ids, list):
        source_ids = []
    source_ids = [str(sid) for sid in source_ids if sid is not None]
    return VocItem(
        text=text,
        frequency=frequency,
        quote=quote,
        source_review_ids=source_ids,
    )


def _parse_voc_response(raw: Any) -> VoC:
    """Parse a raw LLM JSON response into a ``VoC`` model."""
    if not isinstance(raw, dict):
        return VoC()
    kwargs: dict[str, list[VocItem]] = {}
    for category in VOC_CATEGORIES:
        items_raw = raw.get(category)
        if not isinstance(items_raw, list):
            items_raw = []
        parsed: list[VocItem] = []
        for item_raw in items_raw:
            voc_item = _parse_voc_item(item_raw)
            if voc_item is not None:
                parsed.append(voc_item)
        kwargs[category] = parsed
    return VoC(**kwargs)


def analyze_reviews_voc(
    reviews: list[Review],
    llm_provider: LLMProvider | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> VoC:
    """Analyze reviews with LLM and return a merged ``VoC``.

    Args:
        reviews: Reviews to analyze.
        llm_provider: Injected LLM provider. Created from config if None.
        batch_size: Number of reviews per LLM call.

    Returns:
        Merged and deduplicated ``VoC``.
    """
    if not reviews:
        return VoC()

    owns_provider = llm_provider is None
    provider = llm_provider or get_provider()

    try:
        batches = chunk_reviews(reviews, batch_size=batch_size)
        batch_results: list[VoC] = []
        for batch in batches:
            messages = build_voc_prompt(batch)
            try:
                raw = provider.complete_json(
                    messages,
                    schema=_VOC_JSON_SCHEMA,
                    json_retries=3,
                )
            except (LLMJSONError, Exception) as exc:
                logger.warning("LLM VoC analysis failed for a batch: %s", exc)
                continue
            batch_results.append(_parse_voc_response(raw))

        if not batch_results:
            return VoC()

        merged = merge_voc_results(batch_results)
        return merged
    finally:
        if owns_provider:
            provider.close()


def merge_voc_results(results: list[VoC]) -> VoC:
    """Merge multiple per-batch ``VoC`` objects into one.

    Items are concatenated and then deduplicated by text.
    """
    merged: dict[str, list[VocItem]] = {category: [] for category in VOC_CATEGORIES}
    for voc in results:
        for category in VOC_CATEGORIES:
            merged[category].extend(getattr(voc, category, []) or [])

    deduped: dict[str, list[VocItem]] = {}
    for category, items in merged.items():
        deduped[category] = dedupe_voc_items(items)

    return VoC(**deduped)


def dedupe_voc_items(items: list[VocItem]) -> list[VocItem]:
    """Dedup VoC items by normalized text and sum their frequencies.

    Sorts the result by frequency descending, then by text ascending.
    """
    groups: dict[str, VocItem] = {}
    for item in items:
        key = item.text.strip().lower()
        if not key:
            continue
        existing = groups.get(key)
        if existing is None:
            groups[key] = VocItem(
                text=item.text.strip(),
                frequency=item.frequency,
                quote=item.quote,
                source_review_ids=list(item.source_review_ids),
            )
        else:
            existing.frequency += item.frequency
            if item.quote and not existing.quote:
                existing.quote = item.quote
            for rid in item.source_review_ids:
                if rid not in existing.source_review_ids:
                    existing.source_review_ids.append(rid)

    sorted_items = sorted(
        groups.values(),
        key=lambda item: (-item.frequency, item.text),
    )
    return sorted_items


def save_voc(
    nm_id: int,
    voc: VoC,
    output_root: Path | None = None,
) -> Path:
    """Save a ``VoC`` object to ``output/voc/<nmId>.json``."""
    base = output_root or Path(default_settings.paths.output)
    storage = Storage(output_dir=base / "voc")
    path = storage.save_json(
        voc,
        f"{nm_id}.json",
        ensure_ascii=False,
        indent=2,
    )
    return path


def analyze_voc_for_nmId(
    nm_id: int,
    reviews_path: Path | None = None,
    llm_provider: LLMProvider | None = None,
    output_root: Path | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> VoC:
    """Convenience pipeline: load reviews, analyze, save VoC JSON, return VoC.

    Args:
        nm_id: Wildberries product nmId.
        reviews_path: Optional explicit path to reviews JSON.
        llm_provider: Injected LLM provider. Created from config if None.
        output_root: Override output directory.
        batch_size: Reviews per LLM call.

    Returns:
        The analyzed ``VoC``.
    """
    path = reviews_path or _reviews_json_path(output_root, nm_id)
    reviews, _detected_nm_id = load_reviews_for_voc(
        path_or_nm_id=path,
        output_root=output_root,
    )
    voc = analyze_reviews_voc(
        reviews,
        llm_provider=llm_provider,
        batch_size=batch_size,
    )
    save_voc(nm_id, voc, output_root=output_root)
    return voc
