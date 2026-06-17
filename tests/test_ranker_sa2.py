from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from matcher.rank import (
    ClipUnavailableError,
    ImageLoadError,
    RankError,
    combine_scores,
    image_phash_similarity,
    load_image_rgb,
    perceptual_hash,
    phash_similarity,
)


def _make_rgb(size: tuple[int, int] = (64, 64), color: tuple[int, int, int] = (255, 0, 0)) -> Image.Image:
    return Image.new("RGB", size, color)


def _make_rgba(size: tuple[int, int] = (64, 64)) -> Image.Image:
    image = Image.new("RGBA", size, (255, 0, 0, 128))
    return image


def _image_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


class TestRankErrors:
    def test_hierarchy(self) -> None:
        assert issubclass(ImageLoadError, RankError)
        assert issubclass(ClipUnavailableError, RankError)


class TestLoadImageRgb:
    def test_from_path(self, tmp_path: Path) -> None:
        path = tmp_path / "red.png"
        _make_rgb().save(path)
        result = load_image_rgb(path)
        assert isinstance(result, Image.Image)
        assert result.mode == "RGB"

    def test_from_str_path(self, tmp_path: Path) -> None:
        path = tmp_path / "red.png"
        _make_rgb().save(path)
        result = load_image_rgb(str(path))
        assert result.mode == "RGB"

    def test_from_bytes(self) -> None:
        raw = _image_to_bytes(_make_rgb())
        result = load_image_rgb(raw)
        assert result.mode == "RGB"

    def test_from_pil_image(self) -> None:
        original = _make_rgb()
        result = load_image_rgb(original)
        assert result is not original
        assert result.mode == "RGB"
        assert original.mode == "RGB"

    def test_rgba_converted_to_rgb(self) -> None:
        original = _make_rgba()
        result = load_image_rgb(original)
        assert result.mode == "RGB"
        assert result.size == original.size

    def test_broken_bytes_raises(self) -> None:
        with pytest.raises(ImageLoadError):
            load_image_rgb(b"not an image")

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ImageLoadError):
            load_image_rgb(tmp_path / "missing.png")


class TestPerceptualHash:
    def test_returns_string(self) -> None:
        image = _make_rgb()
        h = perceptual_hash(image)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_identical_images_same_hash(self) -> None:
        a = _make_rgb()
        b = _make_rgb()
        assert perceptual_hash(a) == perceptual_hash(b)


class TestPhashSimilarity:
    def test_identical_hashes(self) -> None:
        image = _make_rgb()
        h = perceptual_hash(image)
        score = phash_similarity(h, h)
        assert score == pytest.approx(1.0, abs=1e-12)

    def test_different_hashes(self) -> None:
        red = _make_rgb(color=(255, 0, 0))
        # Solid colors collapse to the same pHash for simple images, so use
        # a structured image to guarantee perceptual difference.
        patterned = Image.new("RGB", (256, 256), (255, 255, 255))
        draw = ImageDraw.Draw(patterned)
        draw.rectangle([0, 0, 128, 256], fill=(0, 0, 255))
        draw.rectangle([128, 0, 256, 256], fill=(0, 255, 0))
        score = phash_similarity(perceptual_hash(red), perceptual_hash(patterned))
        assert 0.0 <= score < 1.0

    def test_maximally_different_hashes(self) -> None:
        # 16x16 hash: all-0 vs all-1 gives maximum Hamming distance.
        size = 16
        zeros = "0" * (size * size)
        ones = "f" * (size * size)
        score = phash_similarity(zeros, ones)
        assert score == pytest.approx(0.0, abs=1e-12)


class TestImagePhashSimilarity:
    def test_identical_images(self) -> None:
        image = _make_rgb()
        score = image_phash_similarity(image, image)
        assert 0.99 <= score <= 1.0

    def test_different_images_lower_score(self) -> None:
        red = _make_rgb(color=(255, 0, 0))
        # Solid colors collapse to the same pHash for simple images, so use
        # a structured image to guarantee perceptual difference.
        patterned = Image.new("RGB", (256, 256), (255, 255, 255))
        draw = ImageDraw.Draw(patterned)
        draw.rectangle([0, 0, 128, 256], fill=(0, 0, 255))
        draw.rectangle([128, 0, 256, 256], fill=(0, 255, 0))
        score = image_phash_similarity(red, patterned)
        assert 0.0 <= score < 1.0

    def test_broken_candidate_raises(self, tmp_path: Path) -> None:
        good = tmp_path / "good.png"
        bad = tmp_path / "bad.png"
        _make_rgb().save(good)
        bad.write_bytes(b"not an image")
        with pytest.raises(ImageLoadError):
            image_phash_similarity(good, bad)

    def test_broken_query_raises(self, tmp_path: Path) -> None:
        good = tmp_path / "good.png"
        bad = tmp_path / "bad.png"
        _make_rgb().save(good)
        bad.write_bytes(b"not an image")
        with pytest.raises(ImageLoadError):
            image_phash_similarity(bad, good)


class TestCombineScores:
    def test_both_present(self) -> None:
        score = combine_scores(0.9, 0.8)
        assert score == pytest.approx(0.87, abs=1e-6)
        assert 0.0 <= score <= 1.0

    def test_only_clip_present(self) -> None:
        assert combine_scores(0.75, None) == pytest.approx(0.75)

    def test_only_phash_present(self) -> None:
        assert combine_scores(None, 0.4) == pytest.approx(0.4)

    def test_both_none(self) -> None:
        assert combine_scores(None, None) == 0.0

    def test_out_of_range_clipped(self) -> None:
        assert combine_scores(-0.5, 1.5) == pytest.approx(0.1, abs=1e-12)
        assert combine_scores(-1.0, None) == 0.0
        assert combine_scores(None, 2.0) == 1.0

    def test_custom_weights(self) -> None:
        score = combine_scores(1.0, 0.0, clip_weight=0.2, phash_weight=0.8)
        assert score == pytest.approx(0.2, abs=1e-6)

    def test_result_normalized_after_weighted_sum(self) -> None:
        assert combine_scores(1.0, 1.0, clip_weight=0.7, phash_weight=0.3) == 1.0
        assert combine_scores(0.0, 0.0, clip_weight=0.7, phash_weight=0.3) == 0.0


class TestPublicApi:
    def test_all_public_names_exported(self) -> None:
        from matcher import rank as rank_module

        for name in rank_module.__all__:
            assert hasattr(rank_module, name)
