# -*- coding: utf-8 -*-
"""Console-script entry and Python floor in ``pyproject.toml``.

Parses the file as text. Uses ``tomllib`` on Python 3.11+; falls back to
regex/text on 3.9/3.10. Does not call pip, does not install packages,
and does not launch the GUI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

EXPECTED_SCRIPT_NAME = "ai-context-studio"
EXPECTED_SCRIPT_TARGET = "ai_context_studio.main:main"
EXPECTED_REQUIRES_PYTHON = ">=3.9"

_TOML_TABLE = re.compile(
    r"^\[(?P<header>[^\]]+)\]\s*\n(?P<body>.*?)(?=^\[|\Z)",
    re.MULTILINE | re.DOTALL,
)
_QUOTED_KV = re.compile(
    r"""^([A-Za-z0-9][A-Za-z0-9._-]*)\s*=\s*["']([^"']+)["']""",
    re.MULTILINE,
)
_REQUIRES_PYTHON = re.compile(
    r"""^requires-python\s*=\s*["']([^"']+)["']""",
    re.MULTILINE,
)


def _read_pyproject() -> str:
    return PYPROJECT_PATH.read_text(encoding="utf-8")


def _toml_table(text: str, header: str) -> str:
    for match in _TOML_TABLE.finditer(text):
        if match.group("header") == header:
            return match.group("body")
    return ""


def parse_project_scripts_regex(text: str) -> dict[str, str]:
    """Console-script name -> object path via regex/text (no tomllib)."""
    body = _toml_table(text, "project.scripts")
    return {m.group(1): m.group(2) for m in _QUOTED_KV.finditer(body)}


def parse_requires_python_regex(text: str) -> str:
    """``requires-python`` value via regex/text (no tomllib)."""
    project = _toml_table(text, "project")
    match = _REQUIRES_PYTHON.search(project)
    return match.group(1) if match else ""


def parse_project_scripts(text: str) -> dict[str, str]:
    """Return console-script name -> object path from ``[project.scripts]``."""
    if sys.version_info >= (3, 11):
        import tomllib

        data: dict[str, Any] = tomllib.loads(text)
        scripts = data.get("project", {}).get("scripts", {})
        return {str(k): str(v) for k, v in scripts.items()}
    return parse_project_scripts_regex(text)


def parse_requires_python(text: str) -> str:
    """Return the ``requires-python`` value from ``[project]``."""
    if sys.version_info >= (3, 11):
        import tomllib

        data: dict[str, Any] = tomllib.loads(text)
        value = data.get("project", {}).get("requires-python", "")
        return str(value)
    return parse_requires_python_regex(text)


class TestPyprojectScripts:
    """``[project.scripts]`` must expose the desktop CLI entry point."""

    def test_pyproject_exists(self) -> None:
        assert PYPROJECT_PATH.is_file()

    def test_console_script_maps_to_main(self) -> None:
        scripts = parse_project_scripts(_read_pyproject())
        assert EXPECTED_SCRIPT_NAME in scripts
        assert scripts[EXPECTED_SCRIPT_NAME] == EXPECTED_SCRIPT_TARGET

    def test_regex_fallback_maps_console_script(self) -> None:
        scripts = parse_project_scripts_regex(_read_pyproject())
        assert scripts.get(EXPECTED_SCRIPT_NAME) == EXPECTED_SCRIPT_TARGET


class TestRequiresPython:
    """Declared interpreter floor must be Python 3.9 or newer."""

    def test_requires_python_is_at_least_3_9(self) -> None:
        value = parse_requires_python(_read_pyproject())
        assert value == EXPECTED_REQUIRES_PYTHON

    def test_regex_fallback_requires_python(self) -> None:
        value = parse_requires_python_regex(_read_pyproject())
        assert value == EXPECTED_REQUIRES_PYTHON
