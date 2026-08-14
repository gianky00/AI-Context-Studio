# -*- coding: utf-8 -*-
"""Facade tests for ``ai_context_studio.ui.tabs``.

Imports public tab classes without instantiating Tk or starting the GUI.
"""

from __future__ import annotations

import importlib
import inspect
import tkinter as tk

from ai_context_studio.ui import cost_history_window, generator_tab, preview_tab, setup_tab
from ai_context_studio.ui.tabs import (
    CostHistoryWindow,
    GeneratorTab,
    PreviewTab,
    SetupTab,
)


class TestTabsFacadeImports:
    """Public tab classes remain importable from the thin re-export facade."""

    def test_setup_tab_is_reexported(self) -> None:
        assert SetupTab is setup_tab.SetupTab
        assert inspect.isclass(SetupTab)

    def test_generator_tab_is_reexported(self) -> None:
        assert GeneratorTab is generator_tab.GeneratorTab
        assert inspect.isclass(GeneratorTab)

    def test_preview_tab_is_reexported(self) -> None:
        assert PreviewTab is preview_tab.PreviewTab
        assert inspect.isclass(PreviewTab)

    def test_cost_history_window_is_reexported(self) -> None:
        assert CostHistoryWindow is cost_history_window.CostHistoryWindow
        assert inspect.isclass(CostHistoryWindow)

    def test_all_lists_public_tab_classes(self) -> None:
        from ai_context_studio.ui import tabs as tabs_mod

        assert tabs_mod.__all__ == [
            "CostHistoryWindow",
            "SetupTab",
            "GeneratorTab",
            "PreviewTab",
        ]

    def test_importing_facade_does_not_start_gui(self) -> None:
        root_before = tk._default_root
        importlib.reload(importlib.import_module("ai_context_studio.ui.tabs"))
        assert tk._default_root is root_before
        assert not isinstance(SetupTab, tk.Misc)
        assert not isinstance(GeneratorTab, tk.Misc)
        assert not isinstance(PreviewTab, tk.Misc)
        assert not isinstance(CostHistoryWindow, tk.Misc)
