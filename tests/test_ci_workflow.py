# -*- coding: utf-8 -*-
"""CI workflow must cover Windows, Python 3.9, and ruff/mypy/pytest.

Reads ``.github/workflows/ci.yml`` as text. Does not import PyYAML,
does not call GitHub, and does not require network access.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

REQUIRED_SNIPPETS = (
    "windows-latest",
    "3.9",
    "pytest",
    "ruff",
    "mypy",
)


def _read_ci_yaml() -> str:
    """Return the workflow file as a UTF-8 string."""
    return CI_WORKFLOW_PATH.read_text(encoding="utf-8")


class TestCiWorkflow:
    """Static checks against the GitHub Actions CI workflow."""

    def test_workflow_file_exists(self) -> None:
        assert CI_WORKFLOW_PATH.is_file()

    def test_required_snippets_appear_in_workflow_text(self) -> None:
        text = _read_ci_yaml()
        missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
        assert missing == [], (
            "ci.yml is missing required snippets: " + ", ".join(missing)
        )

    def test_each_required_snippet_is_present(self) -> None:
        text = _read_ci_yaml()
        for snippet in REQUIRED_SNIPPETS:
            assert snippet in text, f"{snippet!r} must appear in ci.yml"
