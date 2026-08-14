# -*- coding: utf-8 -*-
"""``.gitignore`` must ignore local caches, secrets, and logs.

Reads ``.gitignore`` as text. Does not call git, does not inspect the
index, and does not require network access.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

REQUIRED_PATTERNS = (
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".env",
    "*.log",
)


def _read_gitignore() -> str:
    """Return ``.gitignore`` as a UTF-8 string."""
    return GITIGNORE_PATH.read_text(encoding="utf-8")


class TestGitignore:
    """Static checks against repository ignore rules."""

    def test_gitignore_exists(self) -> None:
        assert GITIGNORE_PATH.is_file()

    def test_required_patterns_appear_in_gitignore_text(self) -> None:
        text = _read_gitignore()
        missing = [pattern for pattern in REQUIRED_PATTERNS if pattern not in text]
        assert missing == [], (
            ".gitignore is missing required patterns: " + ", ".join(missing)
        )

    def test_each_required_pattern_is_present(self) -> None:
        text = _read_gitignore()
        for pattern in REQUIRED_PATTERNS:
            assert pattern in text, f"{pattern!r} must appear in .gitignore"
