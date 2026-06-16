from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from core.models import Product
from core.wb_public import WBPublic
from matcher.input import (
    ImageDownloadError,
    ImageValidationError,
    InvalidInputError,
    ResolvedInput,
    extract_wb_nm_id_from_url,
    is_wb_url,
    normalize_image_to_query_jpg,
    parse_wb_nm_id,
    resolve_input,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_jpeg_bytes(width: int = 100, height: int = 100, mode: str = "RGB") -> bytes:
    buffer = BytesIO()
    Image.new(mode, (width, height), color=(128, 64, 32)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _make_png_bytes(width: int = 100, height: int = 100, mode: str = "RGBA") -> bytes:
    buffer = BytesIO()
    Image.new(mode, (width, height), (0, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _make_webp_bytes(width: int = 100, height: int = 100) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(64, 128, 192)).save(buffer, format="WEBP")
    return buffer.getvalue()


class FakeWBPublic:
    def __init__(self, product: Product | None = None, *, fail: bool = False):
        self.product = product
        self.calls: list[int] = []
        self.closed = False
        self._fail = fail

    def get_detail(self, nmId: int) -> Product:
        self.calls.append(nmId)
        if self._fail:
            raise RuntimeError("network down")
        if self.product is None:
            raise RuntimeError("no product configured")
        return self.product

    def close(self) -> None:
        self.closed = True


def _build_product(nm_id: int, img_url: str | None = "https://example.com/img.jpg") -> Product:
    return Product(
        nmId=nm_id,
        imtId=nm_id * 10,
        name="Test",
        brand="Brand",
        price=100.0,
        feedbacks=5,
        rating=4.5,
        img_url=img_url,
        url=f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
    )


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------
def test_parse_wb_nm_id_from_int() -> None:
    assert parse_wb_nm_id(123456789) == 123456789
    assert parse_wb_nm_id(-1) is None
    assert parse_wb_nm_id(0) is None


def test_parse_wb_nm_id_from_string() -> None:
    assert parse_wb_nm_id("123456789") == 123456789
    assert parse_wb_nm_id("  123456789  ") == 123456789


def test_parse_wb_nm_id_invalid() -> None:
    assert parse_wb_nm_id("abc") is None
    assert parse_wb_nm_id("12.34") is None
    assert parse_wb_nm_id("1234") is None  # too short
    assert parse_wb_nm_id("1234567890123") is None  # too long


def test_is_wb_url_true() -> None:
    assert is_wb_url("https://www.wildberries.ru/catalog/123456789/detail.aspx")
    assert is_wb_url("https://wildberries.ru/catalog/123456789/detail.aspx")
    assert is_wb_url("https://www.wildberries.ru/catalog/123456789/detail.aspx?foo=bar")


def test_is_wb_url_false() -> None:
    assert not is_wb_url("https://example.com/catalog/123456789/detail.aspx")
    assert not is_wb_url("not a url")
    assert not is_wb_url("123456789")


def test_extract_wb_nm_id_from_url() -> None:
    assert extract_wb_nm_id_from_url("https://www.wildberries.ru/catalog/123456789/detail.aspx") == 123456789
    assert extract_wb_nm_id_from_url("https://wildberries.ru/catalog/987654321/detail.aspx?foo=bar") == 987654321


def test_extract_wb_nm_id_from_url_invalid() -> None:
    assert extract_wb_nm_id_from_url("https://example.com/catalog/123456789/detail.aspx") is None
    assert extract_wb_nm_id_from_url("not a url") is None


# ---------------------------------------------------------------------------
# Local file tests
# ---------------------------------------------------------------------------
def test_resolve_local_jpg(tmp_path: Path) -> None:
    src = tmp_path / "source.jpg"
    src.write_bytes(_make_jpeg_bytes())
    out_dir = tmp_path / "out"

    result = resolve_input(str(src), output_dir=out_dir)

    assert isinstance(result, ResolvedInput)
    assert result.source_type == "file"
    assert result.query_image_path == out_dir / "query.jpg"
    assert result.query_image_path.exists()
    assert result.nmId is None
    assert result.product is None


def test_resolve_local_png_with_alpha(tmp_path: Path) -> None:
    src = tmp_path / "source.png"
    src.write_bytes(_make_png_bytes())
    out_dir = tmp_path / "out"

    result = resolve_input(src, output_dir=out_dir)

    assert result.source_type == "file"
    assert result.query_image_path.exists()
    with Image.open(result.query_image_path) as img:
        assert img.mode == "RGB"
        assert img.format == "JPEG"


@pytest.mark.skipif(
    not hasattr(Image, "WEBP") or not Image.registered_extensions().get(".webp"),
    reason="WebP support not available",
)
def test_resolve_local_webp(tmp_path: Path) -> None:
    src = tmp_path / "source.webp"
    src.write_bytes(_make_webp_bytes())
    out_dir = tmp_path / "out"

    result = resolve_input(src, output_dir=out_dir)

    assert result.source_type == "file"
    assert result.query_image_path.exists()
    with Image.open(result.query_image_path) as img:
        assert img.mode == "RGB"


def test_resolve_local_unsupported_extension(tmp_path: Path) -> None:
    src = tmp_path / "source.gif"
    src.write_bytes(b"GIF89a")
    out_dir = tmp_path / "out"

    with pytest.raises(ImageValidationError):
        resolve_input(src, output_dir=out_dir)


def test_resolve_local_missing_file(tmp_path: Path) -> None:
    src = tmp_path / "missing.jpg"
    out_dir = tmp_path / "out"

    with pytest.raises(InvalidInputError):
        resolve_input(src, output_dir=out_dir)


def test_resolve_local_broken_image(tmp_path: Path) -> None:
    src = tmp_path / "broken.jpg"
    src.write_text("this is not an image")
    out_dir = tmp_path / "out"

    with pytest.raises(ImageValidationError):
        resolve_input(src, output_dir=out_dir)


# ---------------------------------------------------------------------------
# WB article / URL tests (network mocked)
# ---------------------------------------------------------------------------
def test_resolve_wb_article(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "out"
    nm_id = 123456789
    product = _build_product(nm_id, "https://example.com/img.jpg")
    fake_client = FakeWBPublic(product)

    downloaded: list[str] = []

    def fake_download(url: str, *, timeout: float = 15.0) -> bytes:
        downloaded.append(url)
        return _make_jpeg_bytes()

    monkeypatch.setattr("matcher.input._download_image_bytes", fake_download)

    result = resolve_input(str(nm_id), wb_client=fake_client, output_dir=out_dir)

    assert result.source_type == "wb_nm"
    assert result.nmId == nm_id
    assert result.product == product
    assert result.query_image_path == out_dir / "query.jpg"
    assert result.query_image_path.exists()
    assert downloaded == ["https://example.com/img.jpg"]
    assert fake_client.calls == [nm_id]
    assert fake_client.closed is False  # injected client must not be closed


def test_resolve_wb_url(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "out"
    nm_id = 987654321
    product = _build_product(nm_id, "https://example.com/img.jpg")
    fake_client = FakeWBPublic(product)

    def fake_download(url: str, *, timeout: float = 15.0) -> bytes:
        return _make_jpeg_bytes()

    monkeypatch.setattr("matcher.input._download_image_bytes", fake_download)

    result = resolve_input(
        f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx?foo=bar",
        wb_client=fake_client,
        output_dir=out_dir,
    )

    assert result.source_type == "wb_url"
    assert result.nmId == nm_id
    assert result.product == product
    assert result.query_image_path.exists()


def test_resolve_wb_article_no_image_url(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    nm_id = 123456789
    product = _build_product(nm_id, img_url=None)
    fake_client = FakeWBPublic(product)

    with pytest.raises(ImageDownloadError):
        resolve_input(str(nm_id), wb_client=fake_client, output_dir=out_dir)


def test_resolve_wb_article_download_error(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "out"
    nm_id = 123456789
    product = _build_product(nm_id, "https://example.com/img.jpg")
    fake_client = FakeWBPublic(product)

    def fake_download(*args, **kwargs) -> bytes:
        raise ImageDownloadError("boom")

    monkeypatch.setattr("matcher.input._download_image_bytes", fake_download)

    with pytest.raises(ImageDownloadError):
        resolve_input(str(nm_id), wb_client=fake_client, output_dir=out_dir)


def test_resolve_input_creates_default_wbpblic_and_closes_it(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "out"
    nm_id = 123456789
    product = _build_product(nm_id, "https://example.com/img.jpg")

    fake_client = FakeWBPublic(product)
    created: list[FakeWBPublic] = []

    def fake_wbpblic() -> FakeWBPublic:
        created.append(fake_client)
        return fake_client

    monkeypatch.setattr("matcher.input.WBPublic", fake_wbpblic)

    def fake_download(*args, **kwargs) -> bytes:
        return _make_jpeg_bytes()

    monkeypatch.setattr("matcher.input._download_image_bytes", fake_download)

    result = resolve_input(str(nm_id), output_dir=out_dir)

    assert result.source_type == "wb_nm"
    assert created == [fake_client]
    assert fake_client.closed is True


# ---------------------------------------------------------------------------
# normalize_image_to_query_jpg direct tests
# ---------------------------------------------------------------------------
def test_normalize_image_to_query_jpg_from_bytes(tmp_path: Path) -> None:
    out = tmp_path / "query.jpg"
    normalize_image_to_query_jpg(_make_jpeg_bytes(), out)
    assert out.exists()
    with Image.open(out) as img:
        assert img.mode == "RGB"


def test_normalize_image_to_query_jpg_respects_max_size(tmp_path: Path) -> None:
    out = tmp_path / "query.jpg"
    normalize_image_to_query_jpg(_make_jpeg_bytes(2000, 1000), out, max_size=(300, 300))
    with Image.open(out) as img:
        assert img.width <= 300
        assert img.height <= 300


# ---------------------------------------------------------------------------
# Error / edge tests
# ---------------------------------------------------------------------------
def test_resolve_input_unrecognized(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"

    with pytest.raises(InvalidInputError):
        resolve_input("not-a-url-and-not-an-id", output_dir=out_dir)


def test_extract_wb_nm_id_from_url_with_query_params() -> None:
    url = "https://www.wildberries.ru/catalog/123456789/detail.aspx?size=42&color=blue"
    assert extract_wb_nm_id_from_url(url) == 123456789
