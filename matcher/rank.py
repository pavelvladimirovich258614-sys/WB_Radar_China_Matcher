from __future__ import annotations

import hashlib
import io
import logging
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image

import imagehash
from core.config import settings
from core.models import Candidate
from core.storage import Storage


logger = logging.getLogger(__name__)


__all__ = [
    "RankError",
    "ImageLoadError",
    "ClipUnavailableError",
    "load_image_rgb",
    "perceptual_hash",
    "phash_similarity",
    "image_phash_similarity",
    "normalize_score",
    "combine_scores",
    "cosine_similarity",
    "ClipImageEmbedder",
    "load_candidate_image",
    "ChinaCandidateRanker",
    "rank_candidates",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RankError(Exception):
    """Base class for ranking failures."""


class ImageLoadError(RankError):
    """Failed to load or convert an image to RGB."""


class ClipUnavailableError(RankError):
    """open_clip/torch are unavailable when CLIP-based ranking is requested."""


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def load_image_rgb(src: Path | str | bytes | Image.Image) -> Image.Image:
    """Open and convert *src* to a non-mutated RGB :class:`PIL.Image.Image`.

    Accepts:
    - a local file path (:class:`pathlib.Path` or ``str``);
    - raw image bytes (``bytes``);
    - an already-opened :class:`PIL.Image.Image`.

    The input image, if already opened, is not mutated. A fresh RGB copy is
    returned.
    """
    try:
        if isinstance(src, Image.Image):
            image = src
        elif isinstance(src, (str, Path)):
            image = Image.open(src)
        elif isinstance(src, bytes):
            image = Image.open(io.BytesIO(src))
        else:
            raise TypeError(f"Unsupported image source type: {type(src).__name__}")
    except ImageLoadError:
        raise
    except Exception as exc:
        raise ImageLoadError(f"Cannot open image: {exc}") from exc

    try:
        if image.mode != "RGB":
            converted = image.convert("RGB")
            if converted is not image:
                return converted
        return image.copy()
    except Exception as exc:
        raise ImageLoadError(f"Cannot convert image to RGB: {exc}") from exc


# ---------------------------------------------------------------------------
# pHash helpers
# ---------------------------------------------------------------------------


def perceptual_hash(image: Image.Image, *, hash_size: int = 16) -> str:
    """Compute a pHash string for *image* using ``imagehash.phash``."""
    try:
        hash_value = imagehash.phash(image, hash_size=hash_size)
    except Exception as exc:
        raise RankError(f"imagehash unavailable or failed: {exc}") from exc
    return str(hash_value)


def phash_similarity(hash_a: str, hash_b: str) -> float:
    """Return a perceptual-hash similarity between two pHash strings.

    Uses Hamming distance between *hash_a* and *hash_b*.  Identical hashes
    yield ``1.0``; maximally different hashes yield ``0.0``.

    Args:
        hash_a: pHash string as returned by :func:`perceptual_hash`.
        hash_b: pHash string as returned by :func:`perceptual_hash`.

    Returns:
        Similarity in ``[0.0, 1.0]``.
    """
    a = imagehash.hex_to_hash(hash_a)
    b = imagehash.hex_to_hash(hash_b)
    distance = a - b
    max_distance = a.hash.size
    score = 1.0 - distance / max_distance
    return max(0.0, min(1.0, score))


def image_phash_similarity(
    image_a: Path | str | bytes | Image.Image,
    image_b: Path | str | bytes | Image.Image,
    *,
    hash_size: int = 16,
) -> float:
    """Return a perceptual-hash similarity between two images.

    Both inputs support the same types as :func:`load_image_rgb`.

    Steps:
    1. Load each image to RGB.
    2. Compute ``imagehash.phash`` for both.
    3. Calculate Hamming distance.
    4. Score = ``1 - distance / (hash_size * hash_size)`` clamped to ``[0.0, 1.0]``.

    Identical images yield ``1.0``. Maximally different hashes yield ``0.0``.
    """
    a_rgb = load_image_rgb(image_a)
    b_rgb = load_image_rgb(image_b)
    a_hash = perceptual_hash(a_rgb, hash_size=hash_size)
    b_hash = perceptual_hash(b_rgb, hash_size=hash_size)
    return phash_similarity(a_hash, b_hash)


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------


def normalize_score(value: float | None, default: float = 0.0) -> float:
    """Clamp *value* to ``[0.0, 1.0]``. Return *default* for ``None``.

    Non-finite values (``NaN``, ``inf``, ``-inf``) are mapped into the range:
    ``NaN`` becomes *default*, ``inf`` becomes ``1.0``, ``-inf`` becomes ``0.0``.
    """
    if value is None:
        return default
    if math.isnan(value):
        return default
    if math.isinf(value):
        return 1.0 if value > 0 else 0.0
    return max(0.0, min(1.0, float(value)))


def combine_scores(
    clip_score: float | None,
    phash_score: float | None,
    *,
    clip_weight: float = 0.7,
    phash_weight: float = 0.3,
) -> float:
    """Combine CLIP and pHash scores into a single ``[0.0, 1.0]`` similarity.

    Rules:
    - Both scores present: weighted sum, then normalized.
    - Only ``clip_score`` present: normalized ``clip_score``.
    - Only ``phash_score`` present: normalized ``phash_score``.
    - Both ``None``: ``0.0``.
    """
    if clip_score is not None and phash_score is not None:
        combined = clip_score * clip_weight + phash_score * phash_weight
        return normalize_score(combined)
    if clip_score is not None:
        return normalize_score(clip_score)
    if phash_score is not None:
        return normalize_score(phash_score)
    return 0.0


def cosine_similarity(vec_a: Any, vec_b: Any) -> float:
    """Return cosine similarity between two vectors mapped to ``[0.0, 1.0]``.

    Accepts lists, tuples, ``numpy.ndarray`` or ``torch.Tensor``.  Vectors are
    L2-normalized internally; result is raw cosine clipped to ``[-1, 1]`` and
    then mapped to ``[0, 1]`` via ``(cosine + 1) / 2``.

    Returns ``0.0`` for invalid/empty/NaN inputs instead of raising.
    """
    try:
        a = _to_numpy(vec_a)
        b = _to_numpy(vec_b)
    except (TypeError, ValueError) as exc:
        logger.debug("cosine_similarity: cannot convert input to vector: %s", exc)
        return 0.0

    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return 0.0

    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        return 0.0

    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0

    cosine = float(np.dot(a, b) / (a_norm * b_norm))
    if math.isnan(cosine) or math.isinf(cosine):
        return 0.0
    cosine = max(-1.0, min(1.0, cosine))
    return (cosine + 1.0) / 2.0


def _to_numpy(value: Any) -> np.ndarray:
    """Convert a vector value to a 1-D float numpy array."""
    if isinstance(value, np.ndarray):
        arr = value
    elif hasattr(value, "detach") and callable(value.detach):
        # torch.Tensor
        arr = value.detach().cpu().numpy()
    elif isinstance(value, (list, tuple)):
        arr = np.asarray(value, dtype=float)
    else:
        arr = np.asarray(value, dtype=float)

    arr = np.asarray(arr, dtype=float).reshape(-1)
    return arr


# ---------------------------------------------------------------------------
# CLIP embedder (lazy open_clip/torch)
# ---------------------------------------------------------------------------


class ClipImageEmbedder:
    """Lazy CLIP image embedder.

    ``open_clip`` and ``torch`` are imported only on first real use, so
    importing this module never downloads or loads the model.  If CLIP is
    unavailable, :meth:`is_available` returns ``False`` and construction/embed
    raise :class:`ClipUnavailableError`.
    """

    DEFAULT_MODEL = "ViT-B-32"
    DEFAULT_PRETRAINED = "laion2b_s34b_b79k"

    def __init__(
        self,
        model_name: str | None = None,
        pretrained: str | None = None,
        device: str | None = None,
        *,
        _model: Any = None,
        _preprocess: Any = None,
    ) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL
        self.pretrained = pretrained or self.DEFAULT_PRETRAINED
        self.device = device

        # Dependency-injection escape hatch for tests / callers who already
        # have a loaded model+preprocess pair.
        self._model: Any = _model
        self._preprocess: Any = _preprocess
        self._initialized = _model is not None and _preprocess is not None

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` if both ``open_clip`` and ``torch`` are importable."""
        try:
            import open_clip  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_model(self) -> None:
        """Lazy-load CLIP model and preprocess pipeline."""
        if self._initialized:
            return

        if not self.is_available():
            raise ClipUnavailableError(
                "open_clip/torch are not installed; CLIP ranking is unavailable"
            )

        import open_clip
        import torch

        device = self.device
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            model, _, preprocess = open_clip.create_model_and_transforms(
                model_name=self.model_name,
                pretrained=self.pretrained,
                device=device,
            )
        except Exception as exc:
            raise ClipUnavailableError(f"Failed to load CLIP model: {exc}") from exc

        self._model = model
        self._preprocess = preprocess
        self.device = device
        self._initialized = True

    def embed_image(self, image: Path | str | bytes | Image.Image) -> np.ndarray:
        """Return a normalized CLIP embedding vector for *image*."""
        self._ensure_model()

        import torch

        rgb_image = load_image_rgb(image)
        preprocessed = self._preprocess(rgb_image)
        # Allow injected fake preprocess to return a tensor-like object directly.
        if hasattr(preprocessed, "unsqueeze") and callable(preprocessed.unsqueeze):
            tensor = preprocessed.unsqueeze(0).to(self.device)
        else:
            tensor = preprocessed

        with torch.no_grad():
            raw_features = self._model(tensor) if callable(self._model) else self._model.encode_image(tensor)
            features = raw_features
            if hasattr(features, "float") and callable(features.float):
                features = features.float()
            if hasattr(features, "norm") and callable(features.norm):
                norm = features.norm(dim=-1, keepdim=True)
                features = features / norm
            else:
                # Normalization was already applied or is not applicable for
                # injected test doubles; keep the raw vector as-is.
                pass

        result = features.squeeze(0)
        if hasattr(result, "cpu"):
            cpu_attr = result.cpu
            result = cpu_attr() if callable(cpu_attr) else cpu_attr
        if hasattr(result, "numpy") and callable(result.numpy):
            result = result.numpy()
        return np.asarray(result, dtype=float)


# ---------------------------------------------------------------------------
# Candidate image loader
# ---------------------------------------------------------------------------


CANDIDATE_IMAGE_TIMEOUT = 30.0


def load_candidate_image(
    candidate: Candidate,
    *,
    client: httpx.Client | None = None,
) -> Image.Image:
    """Resolve a candidate thumbnail to an RGB image.

    Supports:
    - ``http://`` / ``https://`` URLs (downloaded via httpx);
    - local file paths in ``thumb_url``;
    - already-opened image objects are not expected here but are handled.

    The optional *client* allows dependency injection for tests.  A fresh
    client is created only when a network fetch is actually required.
    """
    thumb_url = candidate.thumb_url
    if not thumb_url:
        raise ImageLoadError("Candidate has no thumb_url")

    if isinstance(thumb_url, Image.Image):
        return load_image_rgb(thumb_url)

    thumb_str = str(thumb_url)
    if thumb_str.startswith(("http://", "https://")):
        try:
            fetch_client = client or httpx.Client(timeout=CANDIDATE_IMAGE_TIMEOUT)
            response = fetch_client.get(thumb_str)
            response.raise_for_status()
            data = response.content
        except Exception as exc:
            raise ImageLoadError(f"Cannot download thumb {thumb_str}: {exc}") from exc
        finally:
            if client is None and "fetch_client" in locals():
                fetch_client.close()
        return load_image_rgb(data)

    # Treat as local path (absolute or relative)
    path = Path(thumb_str)
    return load_image_rgb(path)


# ---------------------------------------------------------------------------
# High-level ranker
# ---------------------------------------------------------------------------


class ChinaCandidateRanker:
    """Rank China marketplace candidates against a query image.

    Combines CLIP and pHash similarity.  CLIP is loaded lazily and disabled
    automatically if unavailable.  Per-candidate failures are logged and result
    in ``similarity=0.0`` for that candidate rather than failing the whole
    ranking.
    """

    DEFAULT_CLIP_WEIGHT = 0.7
    DEFAULT_PHASH_WEIGHT = 0.3
    CACHE_NAMESPACE = "rank:image_similarity"

    def __init__(
        self,
        *,
        clip_embedder: ClipImageEmbedder | None = None,
        image_loader: Callable[[Candidate], Image.Image | Path | str | bytes] | None = None,
        use_clip: bool = True,
        use_phash: bool = True,
        clip_weight: float = DEFAULT_CLIP_WEIGHT,
        phash_weight: float = DEFAULT_PHASH_WEIGHT,
        similarity_threshold: float | None = None,
        max_candidates: int | None = None,
        hash_size: int = 16,
        use_cache: bool = True,
        storage: Storage | None = None,
    ) -> None:
        self.clip_embedder = clip_embedder
        self.image_loader = image_loader or load_candidate_image
        self.use_clip = use_clip
        self.use_phash = use_phash
        self.clip_weight = clip_weight
        self.phash_weight = phash_weight
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.matcher.similarity_threshold
        )
        self.max_candidates = (
            max_candidates if max_candidates is not None else settings.matcher.max_candidates
        )
        self.hash_size = hash_size
        self.use_cache = use_cache
        self.storage = storage if storage is not None else Storage()

    def _clip_available(self) -> bool:
        """Return True only when an embedder is present and CLIP can be used."""
        if not self.use_clip or self.clip_embedder is None:
            return False
        return self.clip_embedder.is_available()

    def _embed(self, image: Image.Image) -> np.ndarray | None:
        """Embed *image* with CLIP, returning ``None`` on any failure."""
        if self.clip_embedder is None:
            return None
        try:
            return self.clip_embedder.embed_image(image)
        except ClipUnavailableError:
            logger.warning("CLIP unavailable; falling back to pHash-only ranking")
            return None
        except Exception as exc:
            logger.debug("CLIP embedding failed: %s", exc)
            return None

    def _cache_key(
        self,
        query_image: Image.Image,
        candidate: Candidate,
    ) -> str:
        """Stable cache key for a (query, candidate) pair."""
        buffer = io.BytesIO()
        query_image.save(buffer, format="PNG")
        query_sha256 = hashlib.sha256(buffer.getvalue()).hexdigest()
        payload = {
            "query_sha256": query_sha256,
            "thumb_url": candidate.thumb_url,
            "clip_weight": self.clip_weight,
            "phash_weight": self.phash_weight,
            "use_clip": self.use_clip,
            "use_phash": self.use_phash,
            "hash_size": self.hash_size,
        }
        return Storage.make_cache_key(self.CACHE_NAMESPACE, payload)

    def _score_pair(
        self,
        query_image: Image.Image,
        candidate_image: Image.Image,
    ) -> float:
        """Compute combined similarity for one query/candidate image pair."""
        clip_score: float | None = None
        phash_score: float | None = None

        if self._clip_available():
            query_vec = self._embed(query_image)
            cand_vec = self._embed(candidate_image)
            if query_vec is not None and cand_vec is not None:
                clip_score = cosine_similarity(query_vec, cand_vec)

        if self.use_phash:
            try:
                query_hash = perceptual_hash(query_image, hash_size=self.hash_size)
                cand_hash = perceptual_hash(candidate_image, hash_size=self.hash_size)
                phash_score = phash_similarity(query_hash, cand_hash)
            except Exception as exc:
                logger.debug("pHash computation failed: %s", exc)
                phash_score = None

        return combine_scores(
            clip_score,
            phash_score,
            clip_weight=self.clip_weight,
            phash_weight=self.phash_weight,
        )

    def rank(
        self,
        query_image: Path | str | bytes | Image.Image,
        candidates: list[Candidate],
    ) -> list[Candidate]:
        """Rank *candidates* against *query_image* and return sorted top results."""
        if not candidates:
            return []

        query_rgb = load_image_rgb(query_image)
        query_vec: np.ndarray | None = None
        if self._clip_available():
            query_vec = self._embed(query_rgb)

        scored: list[tuple[float, Candidate]] = []

        for candidate in candidates:
            score: float | None = None

            if self.use_cache:
                cache_key = self._cache_key(query_rgb, candidate)
                try:
                    cached = self.storage.get(cache_key)
                    if isinstance(cached, (int, float)):
                        score = float(cached)
                except Exception as exc:
                    logger.debug("Cache read failed for %s: %s", candidate.thumb_url, exc)

            if score is None:
                try:
                    raw_image = self.image_loader(candidate)
                    candidate_rgb = load_image_rgb(raw_image)
                except Exception as exc:
                    logger.debug(
                        "Cannot load candidate image %s: %s", candidate.thumb_url, exc
                    )
                    score = 0.0
                else:
                    clip_score: float | None = None
                    if self._clip_available() and query_vec is not None:
                        cand_vec = self._embed(candidate_rgb)
                        if cand_vec is not None:
                            clip_score = cosine_similarity(query_vec, cand_vec)

                    phash_score: float | None = None
                    if self.use_phash:
                        try:
                            query_hash = perceptual_hash(
                                query_rgb, hash_size=self.hash_size
                            )
                            cand_hash = perceptual_hash(
                                candidate_rgb, hash_size=self.hash_size
                            )
                            phash_score = phash_similarity(query_hash, cand_hash)
                        except Exception as exc:
                            logger.debug("pHash failed for candidate: %s", exc)
                            phash_score = None

                    score = combine_scores(
                        clip_score,
                        phash_score,
                        clip_weight=self.clip_weight,
                        phash_weight=self.phash_weight,
                    )

                if self.use_cache:
                    cache_key = self._cache_key(query_rgb, candidate)
                    try:
                        self.storage.set(
                            cache_key,
                            score,
                            namespace=self.CACHE_NAMESPACE,
                        )
                    except Exception as exc:
                        logger.debug("Cache write failed for %s: %s", candidate.thumb_url, exc)

            scored.append((score, candidate))

        filtered = [
            (score, candidate)
            for score, candidate in scored
            if score >= self.similarity_threshold
        ]
        filtered.sort(key=lambda item: item[0], reverse=True)

        result: list[Candidate] = []
        for score, candidate in filtered[: self.max_candidates]:
            updated = candidate.model_copy(update={"similarity": score})
            result.append(updated)

        return result


def rank_candidates(
    query_image: Path | str | bytes | Image.Image,
    candidates: list[Candidate],
    **kwargs: Any,
) -> list[Candidate]:
    """Convenience wrapper creating :class:`ChinaCandidateRanker` and ranking."""
    ranker = ChinaCandidateRanker(**kwargs)
    return ranker.rank(query_image, candidates)
