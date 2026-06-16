from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from PIL import Image

from core.config import settings as default_settings
from core.models import Product
from core.wb_public import WBPublic


class InputResolverError(Exception):
    pass


class InvalidInputError(InputResolverError):
    pass


class ImageDownloadError(InputResolverError):
    pass


class ImageValidationError(InputResolverError):
    pass


@dataclass
class ResolvedInput:
    query_image_path: Path
    source_type: Literal["wb_nm", "wb_url", "file"]
    nmId: int | None = None
    product: Product | None = None
    original_input: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


_WB_URL_RE = re.compile(
    r"(?:^|/)catalog/(\d+)/detail\.aspx",
    re.IGNORECASE,
)


_WB_NM_RE = re.compile(r"^\s*(\d{5,12})\s*$")


def parse_wb_nm_id(value: str | int) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None
    if not isinstance(value, str):
        return None
    match = _WB_NM_RE.match(value)
    if match is None:
        return None
    try:
        parsed = int(match.group(1))
    except (ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def is_wb_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower().strip()
    if not lowered.startswith(("http://", "https://")):
        return False
    if "wildberries.ru" not in lowered:
        return False
    return _WB_URL_RE.search(value) is not None


def extract_wb_nm_id_from_url(url: str) -> int | None:
    if not isinstance(url, str):
        return None
    if "wildberries.ru" not in url.lower():
        return None
    match = _WB_URL_RE.search(url)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except (ValueError, OverflowError):
        return None


_ALLOWED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})


def _query_jpg_path(output_dir: Path) -> Path:
    return output_dir / "query.jpg"


def normalize_image_to_query_jpg(
    src: Path | bytes | BytesIO,
    output_path: Path,
    *,
    max_size: tuple[int, int] = (1024, 1024),
    quality: int = 92,
) -> Path:
    try:
        if isinstance(src, Path):
            img = Image.open(src)
        elif isinstance(src, bytes):
            img = Image.open(BytesIO(src))
        elif isinstance(src, BytesIO):
            img = Image.open(src)
        else:
            raise ImageValidationError(
                f"unsupported image source type: {type(src).__name__}"
            )
    except (OSError, Image.UnidentifiedImageError) as exc:
        raise ImageValidationError(f"failed to open image: {exc}") from exc
    except Exception as exc:
        raise ImageValidationError(f"failed to process image: {exc}") from exc

    try:
        rgb = img.convert("RGB")
        rgb.thumbnail(max_size, Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(output_path, format="JPEG", quality=quality, optimize=True)
    except Exception as exc:
        raise ImageValidationError(f"failed to normalize image: {exc}") from exc

    return output_path


def _guess_source_type(value: str | int | Path) -> str | None:
    if isinstance(value, int) or parse_wb_nm_id(value) is not None:
        return "wb_nm"
    if isinstance(value, str):
        if is_wb_url(value):
            return "wb_url"
        if Path(value).exists():
            return "file"
    if isinstance(value, Path) and value.exists():
        return "file"
    return None


def _resolve_output_dir(output_dir: str | Path | None) -> Path:
    if output_dir is None:
        return Path(default_settings.paths.output)
    return Path(output_dir)


def _download_image_bytes(url: str, timeout: float = 15.0) -> bytes:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ImageDownloadError(f"unsupported image URL scheme: {parsed.scheme}")
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ImageDownloadError(f"failed to download image from {url}: {exc}") from exc
    return response.content


def resolve_input(
    value: str | int | Path,
    *,
    wb_client: WBPublic | None = None,
    output_dir: str | Path | None = None,
) -> ResolvedInput:
    original = str(value) if not isinstance(value, str) else value
    source_type = _guess_source_type(value)

    if source_type is None:
        raise InvalidInputError(
            f"could not recognize input as WB article, WB URL, or local image: {original!r}"
        )

    out_dir = _resolve_output_dir(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = _query_jpg_path(out_dir)

    client = wb_client if wb_client is not None else WBPublic()

    try:
        if source_type == "wb_nm":
            nm_id = parse_wb_nm_id(value)
            if nm_id is None:
                raise InvalidInputError(f"invalid WB article id: {original!r}")
            product = client.get_detail(nm_id)
            if not product.img_url:
                raise ImageDownloadError(
                    f"WB product {nm_id} has no image URL"
                )
            image_bytes = _download_image_bytes(product.img_url)
            normalize_image_to_query_jpg(image_bytes, output_path)
            return ResolvedInput(
                query_image_path=output_path,
                source_type="wb_nm",
                nmId=nm_id,
                product=product,
                original_input=original,
                meta={"img_url": product.img_url},
            )

        if source_type == "wb_url":
            nm_id = extract_wb_nm_id_from_url(original)
            if nm_id is None:
                raise InvalidInputError(f"could not extract article id from URL: {original!r}")
            product = client.get_detail(nm_id)
            if not product.img_url:
                raise ImageDownloadError(
                    f"WB product {nm_id} has no image URL"
                )
            image_bytes = _download_image_bytes(product.img_url)
            normalize_image_to_query_jpg(image_bytes, output_path)
            return ResolvedInput(
                query_image_path=output_path,
                source_type="wb_url",
                nmId=nm_id,
                product=product,
                original_input=original,
                meta={"img_url": product.img_url},
            )

        if source_type == "file":
            src_path = Path(value)
            if not src_path.exists():
                raise InvalidInputError(f"local image not found: {src_path}")
            suffix = src_path.suffix.lower()
            if suffix not in _ALLOWED_SUFFIXES:
                raise ImageValidationError(
                    f"unsupported image extension: {suffix}; allowed: {', '.join(sorted(_ALLOWED_SUFFIXES))}"
                )
            normalize_image_to_query_jpg(src_path, output_path)
            return ResolvedInput(
                query_image_path=output_path,
                source_type="file",
                nmId=None,
                product=None,
                original_input=original,
                meta={"source_path": str(src_path.resolve())},
            )
    finally:
        if wb_client is None:
            client.close()

    raise InvalidInputError(f"could not resolve input: {original!r}")


__all__ = [
    "InputResolverError",
    "InvalidInputError",
    "ImageDownloadError",
    "ImageValidationError",
    "ResolvedInput",
    "parse_wb_nm_id",
    "is_wb_url",
    "extract_wb_nm_id_from_url",
    "normalize_image_to_query_jpg",
    "resolve_input",
]
