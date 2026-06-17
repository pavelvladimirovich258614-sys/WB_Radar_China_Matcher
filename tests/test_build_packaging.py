"""Packaging/build tests for F28.

These tests do not actually run PyInstaller; they verify that the build script,
README and run.py entry point are configured correctly and that no secrets or
output folders are accidentally committed.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def readme() -> str:
    path = PROJECT_ROOT / "README.md"
    assert path.exists(), "README.md must exist"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def build_script() -> str:
    path = PROJECT_ROOT / "scripts" / "build_windows.ps1"
    assert path.exists(), "scripts/build_windows.ps1 must exist"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def gitignore() -> str:
    path = PROJECT_ROOT / ".gitignore"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def test_run_py_imports_gui_main() -> None:
    """run.py must delegate to gui.app.main so the packaged app opens GUI."""
    run_py = PROJECT_ROOT / "run.py"
    text = run_py.read_text(encoding="utf-8")
    assert "from gui.app import main" in text
    assert 'if __name__ == "__main__":' in text
    assert "main()" in text


def test_build_script_exists_and_uses_pyinstaller(build_script: str) -> None:
    assert "PyInstaller" in build_script or "pyinstaller" in build_script.lower()


def test_build_script_checks_venv(build_script: str) -> None:
    assert ".venv" in build_script
    assert "python.exe" in build_script


def test_build_script_runs_tests_or_supports_skip(build_script: str) -> None:
    assert '-m "not live"' in build_script or "-m 'not live'" in build_script
    assert "SkipTests" in build_script


def test_build_script_excludes_secrets_and_work_folders(build_script: str) -> None:
    for token in (".env", "sessions", "output", ".venv", "build", "dist"):
        assert token in build_script, f"build script should mention {token}"


def test_build_script_does_not_embed_secrets(build_script: str) -> None:
    """Ensure the build script does not hardcode API keys or passwords."""
    sensitive_patterns = [
        r"sk-[a-zA-Z0-9]{10,}",
        r"OPENROUTER_API_KEY\s*=\s*['\"][^'\"]+['\"]",
        r"ZAI_API_KEY\s*=\s*['\"][^'\"]+['\"]",
        r"GROQ_API_KEY\s*=\s*['\"][^'\"]+['\"]",
    ]
    for pattern in sensitive_patterns:
        assert not re.search(pattern, build_script), f"possible secret in build script: {pattern}"


def test_readme_has_exe_build_section(readme: str) -> None:
    assert "Windows .exe" in readme or ".exe" in readme
    assert "build_windows.ps1" in readme


def test_readme_lists_excluded_items(readme: str) -> None:
    for token in (".env", "sessions", "output"):
        assert token in readme


def test_gitignore_excludes_build_artifacts(gitignore: str) -> None:
    required = {"build/", "dist/", ".env", "sessions/", "output/", ".venv/", "*.db", "__pycache__/"}
    for item in required:
        assert item in gitignore or item.rstrip("/") in gitignore, f".gitignore should exclude {item}"


def test_gui_app_main_is_callable() -> None:
    from gui.app import main

    assert callable(main)


def test_import_of_app_does_not_start_window() -> None:
    """Importing gui.app must not open a window or hang inside the venv."""
    import subprocess

    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    result = subprocess.run(
        [str(venv_python), "-c", "from gui.app import create_app; print('import ok')"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "import ok" in result.stdout
