# -*- coding: utf-8 -*-
"""
Tooltip system for AI Context Studio.

Provides hover tooltips for UI widgets to help users
understand functionality.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ToolTip:
    """
    Tooltip widget that appears on hover.

    Displays helpful text when the user hovers over a widget
    for a specified delay period.

    Attributes:
        widget: The widget this tooltip is attached to
        text: The tooltip text to display
        delay: Milliseconds to wait before showing tooltip
    """

    def __init__(
        self,
        widget: Any,
        text: str,
        delay: int = 500
    ) -> None:
        """
        Initialize a tooltip for a widget.

        Args:
            widget: The widget to attach the tooltip to.
            text: Text to display in the tooltip.
            delay: Delay in milliseconds before showing (default 500).
        """
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window: Optional[tk.Toplevel] = None
        self.scheduled_id: Optional[str] = None

        # Bind events
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<Button-1>", self._on_leave)

    def _on_enter(self, event: Optional[tk.Event] = None) -> None:
        """
        Handle mouse enter event.

        Args:
            event: The tkinter event (unused).
        """
        self.scheduled_id = self.widget.after(self.delay, self._show_tooltip)

    def _on_leave(self, event: Optional[tk.Event] = None) -> None:
        """
        Handle mouse leave event.

        Args:
            event: The tkinter event (unused).
        """
        if self.scheduled_id:
            self.widget.after_cancel(self.scheduled_id)
            self.scheduled_id = None
        self._hide_tooltip()

    def _show_tooltip(self) -> None:
        """Display the tooltip window."""
        if self.tooltip_window:
            return

        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

            self.tooltip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")

            frame = tk.Frame(
                tw,
                background="#1e293b",
                borderwidth=1,
                relief="solid"
            )
            frame.pack()

            label = tk.Label(
                frame,
                text=self.text,
                background="#1e293b",
                foreground="white",
                font=("Segoe UI", 10),
                padx=10,
                pady=6,
                wraplength=300,
                justify="left"
            )
            label.pack()

        except Exception as e:
            logger.debug("Failed to show tooltip: %s", e)

    def _hide_tooltip(self) -> None:
        """Hide and destroy the tooltip window."""
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass
            self.tooltip_window = None


def add_tooltip(widget: Any, text: str, delay: int = 500) -> ToolTip:
    """
    Add a tooltip to a widget.

    Convenience function for creating tooltips.

    Args:
        widget: Widget to add tooltip to.
        text: Tooltip text.
        delay: Display delay in milliseconds.

    Returns:
        The created ToolTip instance.
    """
    return ToolTip(widget, text, delay)
