# -*- coding: utf-8 -*-
"""Package-level tests for ``ai_context_studio.ui``.

Imports public names via importlib/getattr without instantiating Tk or starting the GUI.
"""

from __future__ import annotations

import importlib
import inspect
import tkinter as tk

_TAB_CLASS_NAMES = ("SetupTab", "GeneratorTab", "PreviewTab")


class TestUiPackageReexports:
    """``ai_context_studio.ui`` re-exports tab classes without starting Tk."""

    def test_tab_classes_import_via_getattr(self) -> None:
        ui = importlib.import_module("ai_context_studio.ui")
        for name in _TAB_CLASS_NAMES:
            exported = getattr(ui, name)
            assert inspect.isclass(exported)

    def test_all_public_names_are_getattr_reachable(self) -> None:
        ui = importlib.import_module("ai_context_studio.ui")
        public_names = getattr(ui, "__all__")
        assert isinstance(public_names, list)
        for name in public_names:
            assert getattr(ui, name) is not None
        for name in _TAB_CLASS_NAMES:
            assert name in public_names

    def test_importing_ui_package_does_not_start_gui(self) -> None:
        root_before = tk._default_root
        ui = importlib.reload(importlib.import_module("ai_context_studio.ui"))
        assert tk._default_root is root_before
        for name in _TAB_CLASS_NAMES:
            exported = getattr(ui, name)
            assert not isinstance(exported, tk.Misc)
