from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.config import settings as default_settings
from core.llm import get_provider
from core.llm.base import LLMJSONError, LLMProvider
from core.models import Product, VoC, VocItem
from core.storage import Storage

logger = logging.getLogger(__name__)


class Scene(BaseModel):
    scene: str = ""
    duration: str = ""
    content: str = ""


class VideoHookSet(BaseModel):
    hooks: list[str] = Field(default_factory=list)
    structure: list[Scene] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)


class HookGeneratorError(Exception):
    pass


class HookResponseError(HookGeneratorError):
    pass


_HOOKS_JSON_SCHEMA = {
    "type": "object",
    "required": ["hooks", "structure", "objections"],
    "properties": {
        "hooks": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5,
            "maxItems": 5,
        },
        "structure": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["scene", "duration", "content"],
                "properties": {
                    "scene": {"type": "string"},
                    "duration": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        "objections": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


DEFAULT_STRUCTURE = [
    {"scene": "Хук", "duration": "0–3 сек", "content": "Остановить скролл цепляющим вопросом или утверждением"},
    {"scene": "Боль", "duration": "3–8 сек", "content": "Показать знакомую проблему клиента на языке отзывов"},
    {"scene": "Демо", "duration": "8–20 сек", "content": "Показать товар в действии, ключевое преимущество"},
    {"scene": "Снятие возражений", "duration": "20–28 сек", "content": "Развеять основные сомнения и страхи"},
    {"scene": "Призыв к действию", "duration": "28–30 сек", "content": "CTA: переходи, заказывай, забирай на WB"},
]


DEFAULT_HOOKS = [
    "Ты точно не догадываешься, чем этот товар спасает каждый день...",
    "Перестань платить за то, что ломается через неделю.",
    "Вот почему в отзывах его называют спасением.",
    "Эта мелочь экономит часы нервов — смотри, как работает.",
    "Узнал цену и сначала не поверил. Сейчас покажу почему стоит.",
]


DEFAULT_OBJECTIONS = [
    "Сомнения в качестве",
    "Страх, что не подойдёт размер/цвет/модель",
    "Цена кажется высокой",
    "Не уверены в быстрой доставке",
]


def _format_voc_items(items: list[VocItem]) -> list[dict[str, Any]]:
    return [
        {
            "text": item.text,
            "frequency": item.frequency,
            "quote": item.quote,
        }
        for item in items
    ]


def build_hooks_prompt(
    voc: VoC,
    product: Product | None = None,
) -> list[dict[str, str]]:
    """Build a chat prompt that asks the LLM to generate video hooks."""
    voc_data = {
        "боли": _format_voc_items(voc.боли),
        "желания": _format_voc_items(voc.желания),
        "страхи": _format_voc_items(voc.страхи),
        "триггеры": _format_voc_items(voc.триггеры),
        "восторги": _format_voc_items(voc.восторги),
        "возражения": _format_voc_items(voc.возражения),
        "язык_клиента": _format_voc_items(voc.язык_клиента),
    }
    product_data = None
    if product is not None:
        product_data = {
            "nmId": product.nmId,
            "name": product.name,
            "brand": product.brand,
            "rating": product.rating,
            "feedbacks": product.feedbacks,
            "price": product.price,
        }

    schema = json.dumps(_HOOKS_JSON_SCHEMA, ensure_ascii=False, indent=2)
    user_parts = [
        "Сгенерируй хуки и структуру короткого продающего видео для товара Wildberries.",
        "",
        "Требования:",
        "- 5 вариантов хука (0–3 секунды), которые цепляют внимание;",
        "- Хуки должны быть на языке клиента из отзывов и опираться на страхи, желания и боли;",
        "- Структура ролика: хук -> боль -> демо -> снятие возражений -> CTA;",
        "- Список возражений, которые нужно закрыть в ролике.",
        "",
    ]
    if product_data is not None:
        user_parts.append(f"Товар:\n{json.dumps(product_data, ensure_ascii=False, indent=2)}\n")
    user_parts.extend([
        f"VoC:\n{json.dumps(voc_data, ensure_ascii=False, indent=2)}\n",
        "",
        "Верни JSON-объект по схеме:\n",
        schema,
    ])
    user_content = "\n".join(user_parts)

    return [
        {
            "role": "system",
            "content": (
                "Ты креативный сценарист для коротких видео о товарах. "
                "Пишешь цепляющие хуки, структуру ролика и возражения. "
                "Отвечай только валидным JSON-объектом."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        value = []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        value = []
    return [str(item).strip() for item in value if str(item).strip()]


def _parse_scene(raw: Any) -> Scene | None:
    if not isinstance(raw, dict):
        return None
    scene = _coerce_str(raw.get("scene"))
    duration = _coerce_str(raw.get("duration"))
    content = _coerce_str(raw.get("content"))
    if not scene and not content:
        return None
    return Scene(scene=scene, duration=duration, content=content)


def parse_hooks_response(raw: Any) -> VideoHookSet:
    """Parse and normalize a raw LLM JSON response into ``VideoHookSet``.

    Missing or malformed fields are replaced with safe defaults so the caller
    can still save a usable hooks file.
    """
    if not isinstance(raw, dict):
        return VideoHookSet(
            hooks=list(DEFAULT_HOOKS),
            structure=[Scene(**item) for item in DEFAULT_STRUCTURE],
            objections=list(DEFAULT_OBJECTIONS),
        )

    hooks = _coerce_str_list(raw.get("hooks"))
    while len(hooks) < 5:
        hooks.append(DEFAULT_HOOKS[len(hooks) % len(DEFAULT_HOOKS)])
    if len(hooks) > 5:
        hooks = hooks[:5]

    structure_raw = raw.get("structure")
    if isinstance(structure_raw, list):
        structure = [_parse_scene(item) for item in structure_raw]
        structure = [s for s in structure if s is not None]
    else:
        structure = []
    if not structure:
        structure = [Scene(**item) for item in DEFAULT_STRUCTURE]

    objections = _coerce_str_list(raw.get("objections"))
    if not objections:
        objections = list(DEFAULT_OBJECTIONS)

    return VideoHookSet(hooks=hooks, structure=structure, objections=objections)


def _render_hooks_md(hook_set: VideoHookSet, nm_id: int | None = None) -> str:
    lines: list[str] = []
    title = "Хуки и структура ролика"
    if nm_id is not None:
        title = f"{title} (nmId {nm_id})"
    lines.extend([f"# {title}", ""])

    lines.extend(["## Варианты хуков", ""])
    for idx, hook in enumerate(hook_set.hooks, start=1):
        lines.append(f"{idx}. {hook}")
    lines.append("")

    lines.extend(["## Структура ролика", ""])
    lines.extend(["| Сцена | Хронометраж | Содержание |", "|---|---|---|"])
    for scene in hook_set.structure:
        lines.append(f"| {scene.scene} | {scene.duration} | {scene.content} |")
    lines.append("")

    lines.extend(["## Возражения для закрытия", ""])
    for objection in hook_set.objections:
        lines.append(f"- {objection}")
    lines.append("")

    return "\n".join(lines)


def save_hooks(
    nm_id: int,
    hook_set: VideoHookSet,
    output_root: Path | None = None,
) -> Path:
    """Save a ``VideoHookSet`` as Markdown to ``output/hooks/<nmId>.md``.

    Returns:
        Path to the saved Markdown file.
    """
    base = output_root or Path(default_settings.paths.output)
    target_dir = base / "hooks"
    target_dir.mkdir(parents=True, exist_ok=True)
    md_path = target_dir / f"{nm_id}.md"
    md_path.write_text(_render_hooks_md(hook_set, nm_id=nm_id), encoding="utf-8")
    return md_path


def generate_hooks(
    voc: VoC,
    nm_id: int | None = None,
    product: Product | None = None,
    llm_provider: LLMProvider | None = None,
    output_root: Path | None = None,
) -> VideoHookSet:
    """Generate hooks and video structure from a VoC and save them as Markdown.

    Args:
        voc: Voice-of-customer analysis for the product.
        nm_id: Optional Wildberries product nmId. If provided, the result is
            saved to ``output/hooks/<nmId>.md``.
        product: Optional product metadata for the prompt.
        llm_provider: Injected LLM provider. Created from config if None.
        output_root: Override output directory.

    Returns:
        A ``VideoHookSet`` object.
    """
    owns_provider = llm_provider is None
    provider = llm_provider or get_provider()

    try:
        messages = build_hooks_prompt(voc, product=product)
        try:
            raw = provider.complete_json(
                messages,
                schema=_HOOKS_JSON_SCHEMA,
                json_retries=3,
            )
        except (LLMJSONError, Exception) as exc:
            logger.warning("LLM hook generation failed: %s", exc)
            raw = {}

        hook_set = parse_hooks_response(raw)

        if nm_id is not None:
            save_hooks(nm_id, hook_set, output_root=output_root)

        return hook_set
    finally:
        if owns_provider:
            provider.close()
