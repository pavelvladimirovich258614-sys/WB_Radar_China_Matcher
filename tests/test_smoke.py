import importlib

import pytest

PACKAGES = ["core", "matcher", "harvest", "gui"]


@pytest.mark.parametrize("pkg", PACKAGES)
def test_package_importable(pkg: str) -> None:
    module = importlib.import_module(pkg)
    assert module is not None
    assert module.__name__ == pkg
