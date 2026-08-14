# -*- coding: utf-8 -*-
"""Pre-commit config must lint and fix whitespace, without ruff-format.

Reads ``.pre-commit-config.yaml`` as text. Does not import PyYAML,
does not invoke ``pre-commit``, and does not require network or git.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRE_COMMIT_CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"

REQUIRED_HOOK_IDS = (
    "ruff-check",
    "trailing-whitespace",
    "end-of-file-fixer",
)


def _read_pre_commit_config() -> str:
    """Return the pre-commit config as a UTF-8 string."""
    return PRE_COMMIT_CONFIG_PATH.read_text(encoding="utf-8")


def _hook_id_line(hook_id: str) -> str:
    """Return the YAML ``id:`` line that must appear for ``hook_id``."""
    return f"id: {hook_id}"


class TestPreCommitConfig:
    """Static checks against ``.pre-commit-config.yaml``."""

    def test_config_file_exists(self) -> None:
        assert PRE_COMMIT_CONFIG_PATH.is_file()

    def test_required_hook_ids_appear_in_config_text(self) -> None:
        text = _read_pre_commit_config()
        missing = [
            hook_id
            for hook_id in REQUIRED_HOOK_IDS
            if _hook_id_line(hook_id) not in text
        ]
        assert missing == [], (
            ".pre-commit-config.yaml is missing required hook ids: "
            + ", ".join(missing)
        )

    def test_each_required_hook_id_is_present(self) -> None:
        text = _read_pre_commit_config()
        for hook_id in REQUIRED_HOOK_IDS:
            assert _hook_id_line(hook_id) in text, (
                f"{hook_id!r} must appear as a hook id in .pre-commit-config.yaml"
            )

    def test_ruff_format_is_not_configured(self) -> None:
        text = _read_pre_commit_config()
        assert _hook_id_line("ruff-format") not in text
