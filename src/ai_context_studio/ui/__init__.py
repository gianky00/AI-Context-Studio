# -*- coding: utf-8 -*-
"""
UI components for AI Context Studio.

This package contains all graphical user interface components
built with CustomTkinter.
"""

from .tooltip import ToolTip, add_tooltip
from .event_queue import UIEventQueue
from .file_tree import OptimizedFileTree
from .panels import SmartPresetPanel, GuidePanel
from .tabs import SetupTab, GeneratorTab, PreviewTab

__all__ = [
    'ToolTip',
    'add_tooltip',
    'UIEventQueue',
    'OptimizedFileTree',
    'SmartPresetPanel',
    'GuidePanel',
    'SetupTab',
    'GeneratorTab',
    'PreviewTab',
]
