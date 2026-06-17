from __future__ import annotations

import logging
import os
import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import settings as default_settings
from core.models import VideoAsset

logger = logging.getLogger(__name__)

VideoSource = Literal["china", "wb_review"]

_ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/webm",
    "video/quicktime",
    "video/x-matroska",
    "video/avi",
    "video/msvideo",
    "application/mp4",
    "application/octet-stream",
    "binary/octet-stream",
}

_ALLOWED_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv", ".avi")


class VideoDownloadError(Exception):
    """Base class for video download failures."""


class VideoHTTPError(VideoDownloadError):
    """HTTP-level failure while fetching a video."""

    def __init__(self, url: str, status_code: int, message: str | None = None) -> None:
        self.url = url
        self.status_code = status_code
        super().__init__(message or f"HTTP {status_code} for {url}")


class VideoContentTypeError(VideoDownloadError):
    """The response does not look like a video stream."""

    def __init__(self, url: str, content_type: str | None) -> None:
        self.url = url
        self.content_type = content_type
        super().__init__(f"Unexpected content-type {content_type!r} for {url}")


class VideoTooSmallError(VideoDownloadError):
    """Downloaded file is smaller than the configured minimum."""

    def __init__(self, url: str, size: int, min_bytes: int) -> None:
        self.url = url
        self.size = size
        self.min_bytes = min_bytes
        super().__init__(
            f"Downloaded file for {url} is too small ({size} < {min_bytes} bytes)"
        )


class VideoTimeoutError(VideoDownloadError):
    """The video request timed out."""


class VideoNetworkError(VideoDownloadError):
    """Network/transport error while downloading a video."""


def safe_video_filename(source: VideoSource, index: int, ext: str = ".mp4") -> str:
    """Return a sanitized filename such as ``china_1.mp4``."""
    if not ext.startswith("."):
        ext = "." + ext
    if len(ext) <= 1:
        ext = ".mp4"
    safe_source = str(source).replace(".", "_").replace("/", "_").replace("\\", "_")
    safe_index = max(1, int(index))
    return f"{safe_source}_{safe_index}{ext}"


def video_output_dir(nmId: int, base_output: str | Path | None = None) -> Path:
    """Return ``output/video/<nmId>`` directory, creating it if needed."""
    if base_output is None:
        base_output = default_settings.paths.output
    root = Path(base_output).expanduser().resolve()
    target = root / "video" / str(nmId)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _is_allowed_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    normalized = content_type.lower().strip()
    # Direct match or broad video/* family.
    if normalized in _ALLOWED_CONTENT_TYPES:
        return True
    if normalized.startswith("video/"):
        return True
    # application/* with explicit video extension in the type (e.g., "application/mp4").
    if normalized.startswith("application/") and any(
        video_token in normalized for video_token in ("mp4", "video", "octet-stream")
    ):
        return True
    return False


def _is_allowed_url(url: str) -> bool:
    """Best-effort check: URL path ends with a known video extension."""
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return any(path.endswith(ext) for ext in _ALLOWED_EXTENSIONS)


def _default_timeout(timeout: float | None) -> float:
    if timeout is None or timeout <= 0:
        return 60.0
    return float(timeout)


def _default_min_bytes(min_bytes: int | None) -> int:
    if min_bytes is None or min_bytes < 0:
        return 1024
    return int(min_bytes)


def _get_http_error_class(exc: httpx.HTTPStatusError) -> type[VideoHTTPError]:
    """Map httpx status errors to our specific exception class."""
    return VideoHTTPError


@retry(
    retry=retry_if_exception_type(
        (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError)
    ),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _download_with_retry(
    client: httpx.Client,
    url: str,
    timeout: float,
) -> httpx.Response:
    try:
        return client.get(url, timeout=timeout, follow_redirects=True)
    except httpx.TimeoutException as exc:
        raise VideoTimeoutError(f"Timeout downloading {url}: {exc}") from exc
    except httpx.NetworkError as exc:
        raise VideoNetworkError(f"Network error downloading {url}: {exc}") from exc
    except httpx.HTTPError as exc:
        # Let tenacity retry transport-level HTTP errors; status errors are handled below.
        raise exc


def download_video(
    url: str,
    nmId: int,
    source: VideoSource,
    index: int = 1,
    client: httpx.Client | None = None,
    output_root: str | Path | None = None,
    timeout: float | None = None,
    min_bytes: int | None = None,
) -> VideoAsset:
    """Download a single video and save it under ``output/video/<nmId>``.

    The file is written to a ``.part`` file first and renamed to its final name
    only after the download completes and passes validation. If anything fails,
    the partial file is removed.

    Args:
        url: Direct URL to the video stream.
        nmId: Wildberries product id used for folder organization.
        source: Either ``"china"`` or ``"wb_review"``.
        index: Numeric suffix for the filename (1-based).
        client: Optional ``httpx.Client`` for dependency injection/tests.
        output_root: Override for the base output directory.
        timeout: Per-request timeout in seconds (default 60).
        min_bytes: Minimum acceptable file size in bytes (default 1024).

    Returns:
        A :class:`VideoAsset` describing the saved file.

    Raises:
        VideoHTTPError: on non-2xx HTTP response.
        VideoContentTypeError: when the content-type is not video-like.
        VideoTooSmallError: when the saved file is below ``min_bytes``.
        VideoTimeoutError: on repeated timeout.
        VideoNetworkError: on repeated network/transport failure.
        VideoDownloadError: for other failures.
    """
    if not url or not str(url).strip():
        raise VideoDownloadError("Video URL is empty")

    timeout_value = _default_timeout(timeout)
    min_size = _default_min_bytes(min_bytes)

    owns_client = client is None
    if owns_client:
        client = httpx.Client()

    target_dir = video_output_dir(nmId, base_output=output_root)
    filename = safe_video_filename(source, index)
    final_path = target_dir / filename
    part_path = target_dir / (filename + ".part")

    try:
        response = _download_with_retry(client, str(url), timeout=timeout_value)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise VideoHTTPError(url=url, status_code=exc.response.status_code) from exc

        content_type = response.headers.get("content-type")
        if not _is_allowed_content_type(content_type) and not _is_allowed_url(url):
            raise VideoContentTypeError(url=url, content_type=content_type)

        downloaded = 0
        with open(part_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        if downloaded < min_size:
            raise VideoTooSmallError(url=url, size=downloaded, min_bytes=min_size)

        # Atomic-ish: replace any existing final file with the validated part file.
        shutil.move(str(part_path), str(final_path))

        return VideoAsset(
            source=source,
            nmId=nmId,
            local_path=str(final_path),
            src_url=str(url),
            description=None,
        )

    except VideoDownloadError:
        # Clean up partial file on any known download failure.
        if part_path.exists():
            try:
                part_path.unlink()
            except OSError:
                logger.debug("Failed to remove partial file %s", part_path, exc_info=True)
        raise

    except Exception as exc:
        if part_path.exists():
            try:
                part_path.unlink()
            except OSError:
                logger.debug("Failed to remove partial file %s", part_path, exc_info=True)
        raise VideoDownloadError(f"Failed to download video from {url}: {exc}") from exc

    finally:
        if owns_client:
            try:
                client.close()
            except Exception:
                logger.debug("Failed to close httpx client", exc_info=True)


def download_videos(
    items: Iterable[str],
    nmId: int,
    source: VideoSource,
    *,
    client: httpx.Client | None = None,
    output_root: str | Path | None = None,
    timeout: float | None = None,
    min_bytes: int | None = None,
) -> list[VideoAsset]:
    """Download multiple video URLs for the same ``nmId`` and ``source``.

    Each URL gets an incremental 1-based index in the filename.
    Errors are caught and logged; the corresponding slot is skipped so that
    successful downloads are still returned.
    """
    assets: list[VideoAsset] = []
    for idx, url in enumerate(items, start=1):
        try:
            asset = download_video(
                url=url,
                nmId=nmId,
                source=source,
                index=idx,
                client=client,
                output_root=output_root,
                timeout=timeout,
                min_bytes=min_bytes,
            )
            assets.append(asset)
        except VideoDownloadError as exc:
            logger.warning("Skipping video download %s for nmId=%s: %s", idx, nmId, exc)
        except Exception as exc:
            logger.warning(
                "Unexpected error downloading video %s for nmId=%s: %s", idx, nmId, exc
            )
    return assets
