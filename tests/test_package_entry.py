# -*- coding: utf-8 -*-
"""Tests for package exports and ``python -m ai_context_studio`` entry.

Does not launch the GUI. ``main.main`` is mocked whenever the ``__main__``
module is executed as a script.
"""

from __future__ import annotations

import importlib
import runpy
import sys

import pytest

from ai_context_studio.constants import APP_VERSION


class TestPackageVersion:
    """Package metadata must stay in sync with constants (Open/Closed)."""

    def test_import_exposes_version(self) -> None:
        import ai_context_studio

        version = getattr(ai_context_studio, "__version__", None)
        app_version = getattr(ai_context_studio, "APP_VERSION", None)
        assert version is not None or app_version is not None
        if version is not None:
            assert version == APP_VERSION
        if app_version is not None:
            assert app_version == APP_VERSION

    def test_app_version_matches_constants(self) -> None:
        import ai_context_studio

        assert ai_context_studio.APP_VERSION == APP_VERSION


class TestDunderMain:
    """``python -m ai_context_studio`` must delegate to ``main.main``."""

    def test_importing_dunder_main_does_not_call_main(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ai_context_studio.main as main_mod

        def _fail() -> int:
            raise AssertionError("main.main must not run on import")

        monkeypatch.setattr(main_mod, "main", _fail)
        importlib.reload(importlib.import_module("ai_context_studio.__main__"))

    def test_dunder_main_binds_main_module(self) -> None:
        import ai_context_studio.main as main_mod

        dunder = importlib.reload(importlib.import_module("ai_context_studio.__main__"))
        assert dunder.main is main_mod
        assert callable(dunder.main.main)

    def test_run_as_main_calls_main_main(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ai_context_studio.main as main_mod

        calls: list[int] = []

        def fake_main() -> int:
            calls.append(1)
            return 0

        monkeypatch.setattr(main_mod, "main", fake_main)
        sys.modules.pop("ai_context_studio.__main__", None)

        with pytest.raises(SystemExit) as excinfo:
            runpy.run_module("ai_context_studio", run_name="__main__")

        assert excinfo.value.code == 0
        assert calls == [1]
