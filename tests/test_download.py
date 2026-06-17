from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from core.models import VideoAsset
from harvest.download import (
    VideoContentTypeError,
    VideoDownloadError,
    VideoHTTPError,
    VideoTooSmallError,
    download_video,
    download_videos,
    safe_video_filename,
    video_output_dir,
)


class FakeResponse:
    """Minimal httpx.Response double that supports streaming chunks."""

    def __init__(
        self,
        content: bytes,
        *,
        status_code: int = 200,
        content_type: str = "video/mp4",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = headers or {"content-type": content_type}
        self._chunk_size = 16 * 1024

    def iter_bytes(self, chunk_size: int = 64 * 1024) -> Any:
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = MagicMock()
            request.url = "https://example.com/video.mp4"
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)


class FakeClient:
    """httpx.Client double with optional failure injection."""

    def __init__(
        self,
        responses: list[FakeResponse] | None = None,
        *,
        fail_status: int | None = None,
        fail_count: int = 0,
        fail_class: type[Exception] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self._responses = list(responses or [])
        self._fail_status = fail_status
        self._fail_count = fail_count
        self._fail_class = fail_class
        self._attempt = 0
        self.closed = False

    def get(self, url: str, *, timeout: float = 60.0, follow_redirects: bool = True) -> FakeResponse:
        self.calls.append(url)
        self._attempt += 1

        if self._fail_count and self._attempt <= self._fail_count:
            if self._fail_class is not None:
                raise self._fail_class("injected failure")
            # Default injected failure mimics a network/timeout problem.
            raise TimeoutError("injected timeout")

        if self._responses:
            return self._responses.pop(0)

        content = b"fake video content for " + url.encode()
        return FakeResponse(content, status_code=self._fail_status or 200)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    return tmp_path / "output"


class TestSafeVideoFilename:
    def test_china_first_index(self) -> None:
        assert safe_video_filename("china", 1) == "china_1.mp4"

    def test_wb_review_second_index(self) -> None:
        assert safe_video_filename("wb_review", 2) == "wb_review_2.mp4"

    def test_zero_index_normalized(self) -> None:
        assert safe_video_filename("china", 0) == "china_1.mp4"

    def test_negative_index_normalized(self) -> None:
        assert safe_video_filename("wb_review", -3) == "wb_review_1.mp4"

    def test_custom_extension(self) -> None:
        assert safe_video_filename("china", 1, ext=".mov") == "china_1.mov"

    def test_extension_without_dot(self) -> None:
        assert safe_video_filename("china", 1, ext="mov") == "china_1.mov"

    def test_sanitizes_dangerous_source(self) -> None:
        assert safe_video_filename("../evil", 1) == "___evil_1.mp4"


class TestVideoOutputDir:
    def test_creates_video_nmId_directory(self, tmp_output: Path) -> None:
        d = video_output_dir(123456, base_output=tmp_output)
        assert d == tmp_output / "video" / "123456"
        assert d.exists()

    def test_returns_existing_directory(self, tmp_output: Path) -> None:
        first = video_output_dir(42, base_output=tmp_output)
        second = video_output_dir(42, base_output=tmp_output)
        assert first == second


class TestDownloadVideo:
    def test_successful_download_returns_video_asset(self, tmp_output: Path) -> None:
        url = "https://example.com/video.mp4"
        client = FakeClient([FakeResponse(b"\x00" * 2048, content_type="video/mp4")])

        asset = download_video(
            url=url,
            nmId=123456,
            source="china",
            index=1,
            client=client,
            output_root=tmp_output,
            min_bytes=1024,
        )

        assert isinstance(asset, VideoAsset)
        assert asset.source == "china"
        assert asset.nmId == 123456
        assert asset.src_url == url
        expected_path = tmp_output / "video" / "123456" / "china_1.mp4"
        assert asset.local_path == str(expected_path)
        assert expected_path.exists()
        assert expected_path.read_bytes() == b"\x00" * 2048
        assert not (tmp_output / "video" / "123456" / "china_1.mp4.part").exists()
        assert client.closed is False  # injected client is not closed by us

    def test_path_includes_source_and_index(self, tmp_output: Path) -> None:
        url = "https://example.com/review.mp4"
        client = FakeClient([FakeResponse(b"\x01" * 4096, content_type="video/mp4")])

        asset = download_video(
            url=url,
            nmId=999,
            source="wb_review",
            index=3,
            client=client,
            output_root=tmp_output,
        )

        assert asset.local_path == str(tmp_output / "video" / "999" / "wb_review_3.mp4")
        assert (tmp_output / "video" / "999" / "wb_review_3.mp4").exists()

    def test_octet_stream_accepted(self, tmp_output: Path) -> None:
        client = FakeClient(
            [FakeResponse(b"\x02" * 2048, content_type="application/octet-stream")]
        )

        asset = download_video(
            url="https://example.com/file",
            nmId=7,
            source="china",
            client=client,
            output_root=tmp_output,
            min_bytes=1024,
        )

        assert asset.source == "china"
        assert (tmp_output / "video" / "7" / "china_1.mp4").exists()

    def test_bad_status_raises_video_http_error(self, tmp_output: Path) -> None:
        client = FakeClient(
            [FakeResponse(b"", status_code=403, content_type="video/mp4")]
        )

        with pytest.raises(VideoHTTPError) as exc_info:
            download_video(
                url="https://example.com/video.mp4",
                nmId=1,
                source="china",
                client=client,
                output_root=tmp_output,
            )

        assert exc_info.value.status_code == 403
        assert not (tmp_output / "video" / "1" / "china_1.mp4.part").exists()
        assert not (tmp_output / "video" / "1" / "china_1.mp4").exists()

    def test_too_small_file_raises_and_removes_part(self, tmp_output: Path) -> None:
        client = FakeClient([FakeResponse(b"small", content_type="video/mp4")])

        with pytest.raises(VideoTooSmallError) as exc_info:
            download_video(
                url="https://example.com/video.mp4",
                nmId=2,
                source="wb_review",
                client=client,
                output_root=tmp_output,
                min_bytes=1024,
            )

        assert exc_info.value.size == 5
        assert not (tmp_output / "video" / "2" / "wb_review_1.mp4.part").exists()
        assert not (tmp_output / "video" / "2" / "wb_review_1.mp4").exists()

    def test_invalid_content_type_raises(self, tmp_output: Path) -> None:
        client = FakeClient([FakeResponse(b"\x00" * 2048, content_type="text/html")])

        with pytest.raises(VideoContentTypeError) as exc_info:
            download_video(
                url="https://example.com/page",
                nmId=3,
                source="china",
                client=client,
                output_root=tmp_output,
                min_bytes=1024,
            )

        assert exc_info.value.content_type == "text/html"
        assert not (tmp_output / "video" / "3" / "china_1.mp4.part").exists()

    def test_empty_url_raises(self, tmp_output: Path) -> None:
        with pytest.raises(VideoDownloadError):
            download_video(
                url="",
                nmId=4,
                source="china",
                output_root=tmp_output,
            )

    def test_video_extension_bypasses_content_type(self, tmp_output: Path) -> None:
        # Unknown type but URL ends with .mp4 → allowed.
        client = FakeClient([FakeResponse(b"\x03" * 2048, content_type="foo/bar")])

        asset = download_video(
            url="https://example.com/video.mp4",
            nmId=5,
            source="wb_review",
            client=client,
            output_root=tmp_output,
            min_bytes=1024,
        )

        assert asset.local_path == str(tmp_output / "video" / "5" / "wb_review_1.mp4")

    def test_owns_client_gets_closed(self, tmp_output: Path) -> None:
        client = FakeClient([FakeResponse(b"\x00" * 2048, content_type="video/mp4")])
        # We pass the client so ownership is False; verify not closed.
        asset = download_video(
            url="https://example.com/video.mp4",
            nmId=6,
            source="china",
            client=client,
            output_root=tmp_output,
            min_bytes=1024,
        )
        assert asset.local_path
        assert client.closed is False


class TestDownloadVideos:
    def test_batch_download_returns_list_of_assets(self, tmp_output: Path) -> None:
        urls = [
            "https://example.com/a.mp4",
            "https://example.com/b.mp4",
        ]
        client = FakeClient(
            [
                FakeResponse(b"\x10" * 2048, content_type="video/mp4"),
                FakeResponse(b"\x11" * 2048, content_type="video/mp4"),
            ]
        )

        assets = download_videos(
            urls,
            nmId=100,
            source="china",
            client=client,
            output_root=tmp_output,
            min_bytes=1024,
        )

        assert len(assets) == 2
        assert assets[0].source == "china"
        assert assets[0].nmId == 100
        assert assets[0].src_url == urls[0]
        assert assets[0].local_path == str(tmp_output / "video" / "100" / "china_1.mp4")
        assert assets[1].local_path == str(tmp_output / "video" / "100" / "china_2.mp4")

    def test_batch_skips_failed_downloads(self, tmp_output: Path) -> None:
        urls = [
            "https://example.com/good.mp4",
            "https://example.com/bad.mp4",
        ]
        client = FakeClient(
            [
                FakeResponse(b"\x20" * 2048, content_type="video/mp4"),
                FakeResponse(b"", status_code=500, content_type="video/mp4"),
            ]
        )

        assets = download_videos(
            urls,
            nmId=200,
            source="wb_review",
            client=client,
            output_root=tmp_output,
            min_bytes=1024,
        )

        assert len(assets) == 1
        assert assets[0].local_path == str(tmp_output / "video" / "200" / "wb_review_1.mp4")
        assert (tmp_output / "video" / "200" / "wb_review_2.mp4.part").exists() is False


class TestPublicAPI:
    def test_import_aliases(self) -> None:
        from harvest.download import download_video, download_videos

        assert callable(download_video)
        assert callable(download_videos)
