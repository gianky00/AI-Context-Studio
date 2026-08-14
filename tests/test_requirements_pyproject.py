# -*- coding: utf-8 -*-
"""Keep ``requirements.txt`` aligned with pyproject runtime dependencies.

Parses both files as text. Does not call pip, does not install packages,
and does not use the network. Dev extras (pytest, ruff, mypy, pre-commit)
are not required in ``requirements.txt``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"

# PEP 508 name ends at extras, version, marker, or whitespace.
_REQ_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
_QUOTED_SPEC = re.compile(r"""["']([^"']+)["']""")
_TOML_TABLE = re.compile(
    r"^\[(?P<header>[^\]]+)\]\s*\n(?P<body>.*?)(?=^\[|\Z)",
    re.MULTILINE | re.DOTALL,
)
_DEP_ARRAY = re.compile(
    r"^dependencies\s*=\s*\[(?P<body>.*?)]",
    re.MULTILINE | re.DOTALL,
)


def _normalize_name(name: str) -> str:
    """PEP 503 / packaging name normalization."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def _requirement_name(spec: str) -> str | None:
    """Return the distribution name from a PEP 508 requirement string."""
    stripped = spec.strip()
    if not stripped or stripped.startswith(("#", "-", ".")):
        return None
    match = _REQ_NAME.match(stripped)
    if match is None:
        return None
    return _normalize_name(match.group(1))


def _toml_table(text: str, header: str) -> str:
    for match in _TOML_TABLE.finditer(text):
        if match.group("header") == header:
            return match.group("body")
    return ""


def parse_pyproject_runtime_specs(text: str) -> list[str]:
    """Quoted specs from ``[project] dependencies`` (not optional-deps)."""
    project = _toml_table(text, "project")
    array = _DEP_ARRAY.search(project)
    if array is None:
        return []
    return [m.group(1).strip() for m in _QUOTED_SPEC.finditer(array.group("body"))]


def parse_requirements_specs(text: str) -> list[str]:
    """Non-comment, non-blank requirement lines (inline comments stripped)."""
    specs: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        if line:
            specs.append(line)
    return specs


def _names(specs: list[str]) -> set[str]:
    names: set[str] = set()
    for spec in specs:
        name = _requirement_name(spec)
        if name is not None:
            names.add(name)
    return names


class TestRequirementsPyproject:
    """Runtime package names in pyproject must appear in requirements.txt."""

    def test_files_exist(self) -> None:
        assert PYPROJECT_PATH.is_file()
        assert REQUIREMENTS_PATH.is_file()

    def test_every_pyproject_runtime_dep_appears_in_requirements(self) -> None:
        pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")

        runtime_specs = parse_pyproject_runtime_specs(pyproject)
        assert runtime_specs, "pyproject.toml [project.dependencies] must not be empty"

        req_names = _names(parse_requirements_specs(requirements))
        missing = []
        for spec in runtime_specs:
            name = _requirement_name(spec)
            assert name is not None, f"unparseable pyproject runtime spec: {spec!r}"
            if name not in req_names:
                missing.append(name)

        assert missing == [], (
            "runtime packages from pyproject.toml missing in requirements.txt: "
            + ", ".join(missing)
        )

    def test_expected_runtime_packages_are_listed(self) -> None:
        pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
        expected = {
            "customtkinter",
            "google-genai",
            "cryptography",
            "keyring",
            "tkinterweb",
            "pywebview",
        }
        runtime_names = _names(parse_pyproject_runtime_specs(pyproject))
        assert expected <= runtime_names

        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        req_names = _names(parse_requirements_specs(requirements))
        assert expected <= req_names

    def test_runtime_lower_bounds_copied_from_pyproject(self) -> None:
        pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        req_by_name = {
            name: spec
            for spec in parse_requirements_specs(requirements)
            if (name := _requirement_name(spec)) is not None
        }
        for spec in parse_pyproject_runtime_specs(pyproject):
            name = _requirement_name(spec)
            assert name is not None
            req_spec = req_by_name[name]
            bound = re.search(r">=\s*([0-9][0-9.]*)", spec)
            if bound is not None:
                assert bound.group(0).replace(" ", "") in req_spec.replace(" ", ""), (
                    f"{name} lower bound {bound.group(0)} from pyproject "
                    f"must appear in requirements.txt ({req_spec!r})"
                )

    def test_dev_extras_are_not_required_in_requirements(self) -> None:
        """Dev extras may be present, but the test must not require them."""
        pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        optional = _toml_table(pyproject, "project.optional-dependencies")
        dev_specs = [m.group(1).strip() for m in _QUOTED_SPEC.finditer(optional)]
        dev_names = _names(dev_specs)
        assert {"pytest", "ruff", "mypy", "pre-commit"} <= dev_names

        runtime_names = _names(parse_pyproject_runtime_specs(pyproject))
        req_names = _names(parse_requirements_specs(requirements))
        for name in runtime_names:
            assert name in req_names
        # Intentionally no assertion that pytest/ruff/mypy/pre-commit are listed.
