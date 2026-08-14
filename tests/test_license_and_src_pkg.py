# -*- coding: utf-8 -*-
"""Packaging tests for LICENSE and the ``src`` layout root.

Reads LICENSE and pyproject.toml as text. Does not call pip, does not
install packages, and does not use the network.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LICENSE_PATH = REPO_ROOT / "LICENSE"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SRC_INIT_PATH = REPO_ROOT / "src" / "__init__.py"


class TestLicenseFile:
    """The repository must ship an MIT license file."""

    def test_license_exists(self) -> None:
        assert LICENSE_PATH.is_file()

    def test_license_contains_mit(self) -> None:
        text = LICENSE_PATH.read_text(encoding="utf-8")
        assert "MIT" in text

    def test_license_names_author(self) -> None:
        text = LICENSE_PATH.read_text(encoding="utf-8")
        assert "Giancarlo Allegretti" in text


class TestPyprojectMitClassifier:
    """pyproject classifiers must declare the MIT license."""

    def test_pyproject_exists(self) -> None:
        assert PYPROJECT_PATH.is_file()

    def test_classifiers_mention_mit(self) -> None:
        text = PYPROJECT_PATH.read_text(encoding="utf-8")
        assert "License :: OSI Approved :: MIT License" in text
        assert "MIT" in text


class TestSrcPackageInit:
    """``src/__init__.py`` marks the source layout root."""

    def test_src_init_exists(self) -> None:
        assert SRC_INIT_PATH.is_file()
