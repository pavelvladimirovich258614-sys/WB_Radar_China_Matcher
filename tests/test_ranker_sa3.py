from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageDraw

import sys

from core.models import Candidate
from core.storage import Storage
from matcher.rank import (
    ClipImageEmbedder,
    ClipUnavailableError,
    ChinaCandidateRanker,
    ImageLoadError,
    RankError,
    cosine_similarity,
    image_phash_similarity,
    load_candidate_image,
    load_image_rgb,
    perceptual_hash,
    phash_similarity,
    rank_candidates,
)


def _make_rgb(size: tuple[int, int] = (64, 64), color: tuple[int, int, int] = (255, 0, 0)) -> Image.Image:
    return Image.new("RGB", size, color)


def _image_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def _make_patterned() -> Image.Image:
    """Create a structured image guaranteed to differ from solid colors pHash-wise."""
    image = Image.new("RGB", (256, 256), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 128, 256], fill=(0, 0, 255))
    draw.rectangle([128, 0, 256, 256], fill=(0, 255, 0))
    return image


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.5, abs=1e-6)

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_numpy_vectors(self) -> None:
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-6)

    def test_torch_vectors(self) -> None:
        torch = pytest.importorskip("torch")
        a = torch.tensor([1.0, 0.0, 0.0])
        b = torch.tensor([0.0, 1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(0.5, abs=1e-6)

    def test_empty_vectors(self) -> None:
        assert cosine_similarity([], []) == 0.0

    def test_different_shapes(self) -> None:
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0

    def test_nan_input(self) -> None:
        assert cosine_similarity([float("nan")], [1.0]) == 0.0

    def test_zero_norm_vector(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestClipImageEmbedder:
    def test_is_available_when_packages_installed(self) -> None:
        assert ClipImageEmbedder.is_available() is True

    def test_is_available_false_when_open_clip_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force ImportError for open_clip inside is_available by replacing the
        # real import machinery for these two names.
        saved_modules: dict[str, Any] = {}
        for name in ("open_clip", "torch"):
            saved_modules[name] = sys.modules.get(name)
            sys.modules[name] = None  # type: ignore[assignment]

        try:
            assert ClipImageEmbedder.is_available() is False
        finally:
            for name, module in saved_modules.items():
                if module is not None:
                    sys.modules[name] = module
                else:
                    sys.modules.pop(name, None)

    def test_fake_embedder_without_model_load(self) -> None:
        class FakeTensor:
            def __init__(self, data: np.ndarray, device: str = "cpu") -> None:
                self._data = data
                self.device = device

            def to(self, device: str) -> "FakeTensor":
                return FakeTensor(self._data, device)

            def squeeze(self, dim: int) -> "FakeTensor":
                return FakeTensor(self._data)

            @property
            def cpu(self) -> "FakeTensor":
                return self

            def numpy(self) -> np.ndarray:
                return self._data

        def fake_preprocess(image: Image.Image) -> Any:
            return FakeTensor(np.array([[[1.0, 0.0]]]))

        def fake_model(image_tensor: Any) -> Any:
            return FakeTensor(np.array([1.0, 0.0]))

        embedder = ClipImageEmbedder(_model=fake_model, _preprocess=fake_preprocess)
        vec = embedder.embed_image(_make_rgb())
        assert isinstance(vec, np.ndarray)
        assert len(vec) == 2
        assert pytest.approx(vec[0], abs=1e-6) == 1.0

    def test_real_clip_is_lazy(self) -> None:
        # Constructor must not raise even if model would download later.
        embedder = ClipImageEmbedder()
        assert embedder._model is None
        assert embedder._preprocess is None


class TestLoadCandidateImage:
    def test_local_path(self, tmp_path: Path) -> None:
        path = tmp_path / "thumb.png"
        _make_rgb().save(path)
        candidate = Candidate(site="alibaba", title="x", thumb_url=str(path))
        result = load_candidate_image(candidate)
        assert result.mode == "RGB"

    def test_missing_local_path_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.png"
        candidate = Candidate(site="alibaba", title="x", thumb_url=str(path))
        with pytest.raises(ImageLoadError):
            load_candidate_image(candidate)


class TestChinaCandidateRanker:
    def test_empty_candidates(self) -> None:
        ranker = ChinaCandidateRanker(use_clip=False, similarity_threshold=0.0)
        result = ranker.rank(_make_rgb(), [])
        assert result == []

    def test_duplicate_ranks_higher_than_irrelevant(self, tmp_path: Path) -> None:
        query = _make_rgb()
        duplicate = tmp_path / "dup.png"
        irrelevant = tmp_path / "irr.png"
        query.save(duplicate)
        _make_patterned().save(irrelevant)

        candidates = [
            Candidate(site="alibaba", title="dup", thumb_url=str(duplicate)),
            Candidate(site="alibaba", title="irr", thumb_url=str(irrelevant)),
        ]
        ranker = ChinaCandidateRanker(use_clip=False, similarity_threshold=0.0)
        ranked = ranker.rank(query, candidates)

        assert len(ranked) == 2
        assert ranked[0].title == "dup"
        assert ranked[0].similarity > ranked[1].similarity

    def test_threshold_filters_results(self, tmp_path: Path) -> None:
        query = _make_rgb()
        duplicate = tmp_path / "dup.png"
        irrelevant = tmp_path / "irr.png"
        query.save(duplicate)
        _make_patterned().save(irrelevant)

        candidates = [
            Candidate(site="alibaba", title="dup", thumb_url=str(duplicate)),
            Candidate(site="alibaba", title="irr", thumb_url=str(irrelevant)),
        ]
        ranker = ChinaCandidateRanker(use_clip=False, similarity_threshold=0.95)
        ranked = ranker.rank(query, candidates)

        assert all(c.similarity >= 0.95 for c in ranked)
        assert any(c.title == "dup" for c in ranked)

    def test_max_candidates_limits_output(self, tmp_path: Path) -> None:
        query = _make_rgb()
        candidates = []
        for i in range(5):
            path = tmp_path / f"cand_{i}.png"
            _make_rgb().save(path)
            candidates.append(Candidate(site="alibaba", title=f"c{i}", thumb_url=str(path)))

        ranker = ChinaCandidateRanker(use_clip=False, max_candidates=2, similarity_threshold=0.0)
        ranked = ranker.rank(query, candidates)
        assert len(ranked) == 2

    def test_use_clip_false_uses_phash(self, tmp_path: Path) -> None:
        query = _make_rgb()
        duplicate = tmp_path / "dup.png"
        query.save(duplicate)

        candidates = [Candidate(site="alibaba", title="dup", thumb_url=str(duplicate))]
        ranker = ChinaCandidateRanker(use_clip=False, use_phash=True)
        ranked = ranker.rank(query, candidates)
        assert ranked[0].similarity == pytest.approx(1.0, abs=1e-6)

    def test_both_clip_and_phash_false_gives_zero(self, tmp_path: Path) -> None:
        query = _make_rgb()
        duplicate = tmp_path / "dup.png"
        query.save(duplicate)

        candidates = [Candidate(site="alibaba", title="dup", thumb_url=str(duplicate))]
        ranker = ChinaCandidateRanker(
            use_clip=False, use_phash=False, similarity_threshold=0.0
        )
        ranked = ranker.rank(query, candidates)
        assert ranked[0].similarity == 0.0

    def test_broken_candidate_does_not_crash(self, tmp_path: Path) -> None:
        query = _make_rgb()
        good = tmp_path / "good.png"
        bad = tmp_path / "bad.png"
        query.save(good)
        bad.write_bytes(b"not an image")

        candidates = [
            Candidate(site="alibaba", title="good", thumb_url=str(good)),
            Candidate(site="alibaba", title="bad", thumb_url=str(bad)),
        ]
        ranker = ChinaCandidateRanker(use_clip=False, similarity_threshold=0.0)
        ranked = ranker.rank(query, candidates)

        assert len(ranked) == 2
        assert ranked[0].similarity >= ranked[1].similarity
        assert ranked[1].similarity == 0.0

    def test_candidate_model_copy_preserves_fields(self, tmp_path: Path) -> None:
        query = _make_rgb()
        thumb = tmp_path / "thumb.png"
        query.save(thumb)

        original = Candidate(
            site="alibaba",
            title="Original",
            url="https://example.com/item",
            thumb_url=str(thumb),
            price=9.99,
            has_video=True,
            video_url="https://example.com/video.mp4",
        )
        ranker = ChinaCandidateRanker(use_clip=False)
        ranked = ranker.rank(query, [original])

        assert len(ranked) == 1
        updated = ranked[0]
        assert updated is not original
        assert updated.site == "alibaba"
        assert updated.title == "Original"
        assert updated.url == "https://example.com/item"
        assert updated.thumb_url == str(thumb)
        assert updated.price == 9.99
        assert updated.has_video is True
        assert updated.video_url == "https://example.com/video.mp4"
        assert updated.similarity > 0.0

    def test_fake_embedder_ranks_with_clip(self) -> None:
        query = _make_rgb(color=(255, 0, 0))
        dup = _make_rgb(color=(255, 0, 0))
        irr = _make_patterned()

        def fake_embed(image: Any) -> np.ndarray:
            rgb = load_image_rgb(image)
            # Same image -> [1, 0]; different -> [0, 1].
            if perceptual_hash(rgb) == perceptual_hash(query):
                return np.array([1.0, 0.0])
            return np.array([0.0, 1.0])

        embedder = ClipImageEmbedder(_model=None, _preprocess=None)
        embedder.embed_image = fake_embed  # type: ignore[method-assign]

        candidates = [
            Candidate(site="alibaba", title="irr", thumb_url="irr"),
            Candidate(site="alibaba", title="dup", thumb_url="dup"),
        ]

        def fake_loader(candidate: Candidate) -> Image.Image:
            if candidate.title == "dup":
                return dup
            return irr

        ranker = ChinaCandidateRanker(
            clip_embedder=embedder,
            image_loader=fake_loader,
            use_clip=True,
            use_phash=False,
            similarity_threshold=0.0,
        )
        ranked = ranker.rank(query, candidates)

        assert ranked[0].title == "dup"
        assert ranked[0].similarity > ranked[1].similarity

    def test_rank_candidates_helper(self, tmp_path: Path) -> None:
        query = _make_rgb()
        duplicate = tmp_path / "dup.png"
        query.save(duplicate)

        candidates = [Candidate(site="alibaba", title="dup", thumb_url=str(duplicate))]
        ranked = rank_candidates(query, candidates, use_clip=False)
        assert len(ranked) == 1
        assert ranked[0].similarity == pytest.approx(1.0, abs=1e-6)

    def test_cache_hit_skips_loader(self, tmp_path: Path) -> None:
        query = _make_rgb()
        thumb = tmp_path / "thumb.png"
        query.save(thumb)

        candidate = Candidate(site="alibaba", title="dup", thumb_url=str(thumb))
        storage = Storage(db_path=str(tmp_path / "cache.db"))

        ranker = ChinaCandidateRanker(use_clip=False, storage=storage)
        ranked1 = ranker.rank(query, [candidate])
        assert ranked1[0].similarity == pytest.approx(1.0, abs=1e-6)

        call_count = 0

        def counting_loader(c: Candidate) -> Image.Image:
            nonlocal call_count
            call_count += 1
            return load_image_rgb(c.thumb_url)

        ranker2 = ChinaCandidateRanker(
            use_clip=False,
            storage=storage,
            image_loader=counting_loader,
        )
        ranked2 = ranker2.rank(query, [candidate])
        assert ranked2[0].similarity == pytest.approx(1.0, abs=1e-6)
        assert call_count == 0

    def test_use_cache_false_recaclulates(self, tmp_path: Path) -> None:
        query = _make_rgb()
        thumb = tmp_path / "thumb.png"
        query.save(thumb)

        candidate = Candidate(site="alibaba", title="dup", thumb_url=str(thumb))
        storage = Storage(db_path=str(tmp_path / "cache.db"))

        ranker = ChinaCandidateRanker(use_clip=False, storage=storage, use_cache=False)
        ranked1 = ranker.rank(query, [candidate])
        assert ranked1[0].similarity == pytest.approx(1.0, abs=1e-6)

        call_count = 0

        def counting_loader(c: Candidate) -> Image.Image:
            nonlocal call_count
            call_count += 1
            return load_image_rgb(c.thumb_url)

        ranker2 = ChinaCandidateRanker(
            use_clip=False,
            storage=storage,
            use_cache=False,
            image_loader=counting_loader,
        )
        ranked2 = ranker2.rank(query, [candidate])
        assert ranked2[0].similarity == pytest.approx(1.0, abs=1e-6)
        assert call_count == 1


class TestPublicApiSa3:
    def test_all_public_names_exported(self) -> None:
        from matcher import rank as rank_module

        for name in rank_module.__all__:
            assert hasattr(rank_module, name)

    def test_can_import_sa3_names(self) -> None:
        from matcher.rank import (
            ClipImageEmbedder,
            ChinaCandidateRanker,
            cosine_similarity,
            load_candidate_image,
            rank_candidates,
        )

        assert ClipImageEmbedder is not None
        assert ChinaCandidateRanker is not None
        assert cosine_similarity is not None
        assert load_candidate_image is not None
        assert rank_candidates is not None
