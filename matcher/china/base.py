from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from core.models import Candidate


@runtime_checkable
class ChinaSearchDriver(Protocol):
    """Common interface for image-search drivers on China marketplaces.

    Implementations are not required to inherit from a concrete base class;
    the protocol only defines the public contract so callers can rely on
    ``search_by_image(path) -> list[Candidate]``.
    """

    def search_by_image(
        self,
        image_path: str | Path,
        *,
        max_results: int | None = None,
        use_cache: bool = True,
    ) -> list[Candidate]:
        ...
