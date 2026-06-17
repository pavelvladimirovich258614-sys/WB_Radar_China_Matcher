from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.config import settings as default_settings
from core.llm import get_provider
from core.llm.base import LLMJSONError, LLMProvider
from core.models import Product, VideoAsset, VoC, VocItem
from core.storage import Storage
from harvest.download import video_output_dir

logger = logging.getLogger(__name__)


class VideoDescription(BaseModel):
    title: str = ""
    description: str = ""
    captions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class DescriptionWriterError(Exception):
    pass


class DescriptionResponseError(DescriptionWriterError):
    pass


_DESCRIPTION_SCHEMA = {
    "type": "object",
    "required": ["title", "description", "captions", "tags"],
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "captions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


def _format_voc_items(items: list[VocItem]) -> list[dict[str, Any]]:
    return [
        {
            "text": item.text,
            "frequency": item.frequency,
            "quote": item.quote,
        }
        for item in items
    ]


def build_description_prompt(
    video_asset: VideoAsset,
    product: Product,
    voc: VoC,
) -> list[dict[str, str]]:
    """Build a chat prompt for the video description writer."""
    product_data = {
        "nmId": product.nmId,
        "name": product.name,
        "brand": product.brand,
        "rating": product.rating,
        "feedbacks": product.feedbacks,
        "price": product.price,
    }
    video_data = {
        "source": video_asset.source,
        "src_url": video_asset.src_url,
        "local_path": video_asset.local_path,
        "existing_description": video_asset.description,
    }
    voc_data = {
        "боли": _format_voc_items(voc.боли),
        "желания": _format_voc_items(voc.желания),
        "страхи": _format_voc_items(voc.страхи),
        "триггеры": _format_voc_items(voc.триггеры),
        "восторги": _format_voc_items(voc.восторги),
        "возражения": _format_voc_items(voc.возражения),
        "язык_клиента": _format_voc_items(voc.язык_клиента),
    }

    import json

    schema = json.dumps(_DESCRIPTION_SCHEMA, ensure_ascii=False, indent=2)
    user_content = (
        "Напиши продающее описание и подводки для короткого видео о товаре Wildberries.\n\n"
        "Используй язык клиента из VoC, опирайся на боли, желания, страхи и восторги. "
        "Описание должно быть коротким, цепляющим, подходящим для TikTok/Reels/Shorts.\n\n"
        f"Товар:\n{json.dumps(product_data, ensure_ascii=False, indent=2)}\n\n"
        f"Видео:\n{json.dumps(video_data, ensure_ascii=False, indent=2)}\n\n"
        f"VoC:\n{json.dumps(voc_data, ensure_ascii=False, indent=2)}\n\n"
        "Верни JSON-объект по схеме:\n"
        f"{schema}\n\n"
        "Требования:\n"
        '- title — цепляющий заголовок (до 80 символов);\n'
        '- description — краткое описание ролика (2–4 предложения);\n'
        '- captions — ровно 3 варианта подводки/подписи на языке клиента;\n'
        '- tags — 5–10 хештегов/ключевых слов на русском.'
    )
    return [
        {
            "role": "system",
            "content": (
                "Ты копирайтер для коротких видео о товарах. "
                "Пишешь заголовки, описания роликов, подводки и теги. "
                "Отвечай только валидным JSON-объектом."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_str_list(value: Any, *, min_len: int = 0, default: str = "") -> list[str]:
    if value is None:
        value = []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        value = []
    result = [str(item).strip() for item in value if str(item).strip()]
    while len(result) < min_len:
        result.append(default)
    return result


def parse_description_response(raw: Any) -> VideoDescription:
    """Parse and normalize a raw LLM JSON response into ``VideoDescription``.

    Missing or malformed fields are replaced with safe defaults rather than
    raising an exception, so the caller can still save a usable description.
    """
    if not isinstance(raw, dict):
        return VideoDescription(
            title="Описание видео",
            description="",
            captions=["", "", ""],
            tags=[],
        )

    title = _coerce_str(raw.get("title")) or "Описание видео"
    description = _coerce_str(raw.get("description"))
    captions = _coerce_str_list(raw.get("captions"), min_len=3, default="")
    tags = _coerce_str_list(raw.get("tags"))

    # Ensure exactly 3 captions even if LLM returned fewer or more.
    if len(captions) > 3:
        captions = captions[:3]

    return VideoDescription(
        title=title,
        description=description,
        captions=captions,
        tags=tags,
    )


def _render_description_md(description: VideoDescription) -> str:
    lines = [
        f"# {description.title}",
        "",
        "## Описание ролика",
        "",
        description.description,
        "",
        "## Подводки / подписи",
        "",
    ]
    for idx, caption in enumerate(description.captions, start=1):
        lines.append(f"{idx}. {caption}")
    lines.extend(["", "## Теги", ""])
    if description.tags:
        lines.append(", ".join(f"#{tag.replace(' ', '')}" if not tag.startswith("#") else tag for tag in description.tags))
    else:
        lines.append("-")
    lines.append("")
    return "\n".join(lines)


def save_description(
    nm_id: int,
    description: VideoDescription,
    output_root: Path | None = None,
) -> tuple[Path, Path]:
    """Save a video description as JSON and Markdown next to the video folder.

    Files are written to ``output/video/<nmId>/description.json`` and
    ``output/video/<nmId>/description.md``.

    Returns:
        Tuple of (json_path, md_path).
    """
    target_dir = video_output_dir(nm_id, base_output=output_root)
    storage = Storage(output_dir=target_dir)

    json_path = storage.save_json(
        description,
        "description.json",
        ensure_ascii=False,
        indent=2,
    )

    md_path = target_dir / "description.md"
    md_path.write_text(
        _render_description_md(description),
        encoding="utf-8",
    )
    return json_path, md_path


def describe_video(
    video_asset: VideoAsset,
    product: Product,
    voc: VoC,
    llm_provider: LLMProvider | None = None,
    output_root: Path | None = None,
) -> VideoDescription:
    """Generate and save a description for a video asset.

    Args:
        video_asset: The video to describe.
        product: Associated Wildberries product.
        voc: Voice-of-customer analysis for the product.
        llm_provider: Injected LLM provider. Created from config if None.
        output_root: Override output directory.

    Returns:
        A ``VideoDescription`` object.

    Raises:
        DescriptionResponseError: if the LLM response cannot be parsed and
        no usable fallback is possible.
    """
    owns_provider = llm_provider is None
    provider = llm_provider or get_provider()

    try:
        messages = build_description_prompt(video_asset, product, voc)
        try:
            raw = provider.complete_json(
                messages,
                schema=_DESCRIPTION_SCHEMA,
                json_retries=3,
            )
        except (LLMJSONError, Exception) as exc:
            logger.warning("LLM description generation failed: %s", exc)
            raw = {}

        description = parse_description_response(raw)

        # Re-attach the generated title as the video description for consistency.
        save_description(video_asset.nmId, description, output_root=output_root)

        return description
    finally:
        if owns_provider:
            provider.close()
