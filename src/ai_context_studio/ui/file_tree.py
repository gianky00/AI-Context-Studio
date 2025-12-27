# -*- coding: utf-8 -*-
"""
Optimized file tree widget for AI Context Studio.

Provides a tree view of project files with selection capabilities.
"""

from __future__ import annotations

import logging
import os
from tkinter import ttk
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..constants import COLORS, FILE_ICONS, TOKEN_FACTOR
from ..models import FileInfo
from .tooltip import add_tooltip

logger = logging.getLogger(__name__)


class OptimizedFileTree(ctk.CTkFrame):
    """
    File tree widget using ttk.Treeview.

    Displays project files in a tree structure with:
    - File size and token count display
    - Include/exclude toggle via double-click
    - Bulk selection operations

    Attributes:
        _files: List of FileInfo objects
        _on_change_callback: Callback for selection changes
        tree: The ttk.Treeview widget
    """

    def __init__(self, master: Any, **kwargs: Any) -> None:
        """
        Initialize the file tree.

        Args:
            master: Parent widget.
            **kwargs: Additional frame arguments.
        """
        super().__init__(master, **kwargs)

        self._files: list[FileInfo] = []
        self._on_change_callback: Optional[Callable[[], None]] = None

        self._setup_style()
        self._setup_ui()

    def _setup_style(self) -> None:
        """Configure ttk styles for the tree."""
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            font=('Segoe UI', 10),
            rowheight=26
        )
        style.configure(
            "Custom.Treeview.Heading",
            font=('Segoe UI', 10, 'bold')
        )

    def _setup_ui(self) -> None:
        """Set up the file tree UI."""
        # Info header
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=5, pady=(5, 0))

        ctk.CTkLabel(
            info_frame,
            text="\U0001F4A1 Doppio click per includere/escludere file",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        ).pack(side="left")

        # Tree container
        tree_container = ctk.CTkFrame(self, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Create treeview
        columns = ("size", "tokens", "status")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            selectmode="extended",
            style="Custom.Treeview"
        )

        # Configure columns
        self.tree.heading("#0", text="\U0001F4C4 File", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("tokens", text="Token", anchor="e")
        self.tree.heading("status", text="", anchor="center")

        self.tree.column("#0", width=350, minwidth=200)
        self.tree.column("size", width=80, minwidth=60)
        self.tree.column("tokens", width=70, minwidth=50)
        self.tree.column("status", width=50, minwidth=40)

        # Scrollbar
        vsb = ttk.Scrollbar(
            tree_container,
            orient="vertical",
            command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=vsb.set)

        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # Button frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))

        # Selection buttons
        btn_all = ctk.CTkButton(
            btn_frame,
            text="\u2713 Tutti",
            width=80,
            height=28,
            command=self._select_all
        )
        btn_all.pack(side="left", padx=2)
        add_tooltip(btn_all, "Seleziona tutti i file per includerli nella generazione")

        btn_none = ctk.CTkButton(
            btn_frame,
            text="\u2717 Nessuno",
            width=80,
            height=28,
            command=self._deselect_all
        )
        btn_none.pack(side="left", padx=2)
        add_tooltip(btn_none, "Deseleziona tutti i file")

        btn_toggle = ctk.CTkButton(
            btn_frame,
            text="\u2194 Inverti",
            width=80,
            height=28,
            command=self._toggle_all
        )
        btn_toggle.pack(side="left", padx=2)
        add_tooltip(
            btn_toggle,
            "Inverti la selezione: i selezionati diventano esclusi e viceversa"
        )

        # Bind events
        self.tree.bind("<Double-1>", self._on_double_click)

        # Configure tags
        self.tree.tag_configure("included", foreground="black")
        self.tree.tag_configure("excluded", foreground="#aaa")

    def set_on_change_callback(self, callback: Callable[[], None]) -> None:
        """
        Set callback for selection changes.

        Args:
            callback: Function to call when selection changes.
        """
        self._on_change_callback = callback

    def load_files(self, files: list[FileInfo]) -> None:
        """
        Load files into the tree.

        Args:
            files: List of FileInfo objects to display.
        """
        self._files = files

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Group by directory
        dirs: dict[str, list[FileInfo]] = {}
        for f in files:
            parts = f.relative_path.split(os.sep)
            dir_name = parts[0] if len(parts) > 1 else "."
            if dir_name not in dirs:
                dirs[dir_name] = []
            dirs[dir_name].append(f)

        # Add to tree
        for dir_name in sorted(dirs.keys()):
            dir_files = dirs[dir_name]

            if dir_name != ".":
                dir_id = self.tree.insert(
                    "",
                    "end",
                    text=f"\U0001F4C1 {dir_name}",
                    values=("", "", ""),
                    open=False
                )
                parent = dir_id
            else:
                parent = ""

            for f in sorted(dir_files, key=lambda x: x.relative_path):
                self._add_file_item(f, parent)

        logger.debug("Loaded %d files into tree", len(files))

    def _add_file_item(self, file_info: FileInfo, parent: str) -> None:
        """
        Add a file item to the tree.

        Args:
            file_info: File information.
            parent: Parent tree item ID.
        """
        display_name = os.path.basename(file_info.relative_path)
        icon = FILE_ICONS.get(file_info.extension, '\U0001F4C4')

        # Format size
        if file_info.size >= 1024:
            size_str = f"{file_info.size / 1024:.1f}K"
        else:
            size_str = f"{file_info.size}B"

        tokens = file_info.size // TOKEN_FACTOR
        status = "\u2713" if file_info.included else "\u2717"
        tag = "included" if file_info.included else "excluded"

        self.tree.insert(
            parent,
            "end",
            text=f"{icon} {display_name}",
            values=(size_str, str(tokens), status),
            tags=(tag, file_info.relative_path)
        )

    def _on_double_click(self, event: Any) -> None:
        """
        Handle double-click to toggle file inclusion.

        Args:
            event: The tkinter event.
        """
        item = self.tree.identify_row(event.y)
        if not item:
            return

        tags = self.tree.item(item, "tags")
        if len(tags) >= 2:
            rel_path = tags[1]
            for f in self._files:
                if f.relative_path == rel_path:
                    f.included = not f.included
                    new_status = "\u2713" if f.included else "\u2717"
                    new_tag = "included" if f.included else "excluded"
                    vals = self.tree.item(item, "values")
                    self.tree.item(
                        item,
                        values=(vals[0], vals[1], new_status),
                        tags=(new_tag, rel_path)
                    )
                    break

        self._notify_change()

    def _select_all(self) -> None:
        """Select all files."""
        for f in self._files:
            f.included = True
        self.load_files(self._files)
        self._notify_change()

    def _deselect_all(self) -> None:
        """Deselect all files."""
        for f in self._files:
            f.included = False
        self.load_files(self._files)
        self._notify_change()

    def _toggle_all(self) -> None:
        """Toggle all file selections."""
        for f in self._files:
            f.included = not f.included
        self.load_files(self._files)
        self._notify_change()

    def _notify_change(self) -> None:
        """Notify callback of selection change."""
        if self._on_change_callback:
            self._on_change_callback()

    def get_included_files(self) -> list[FileInfo]:
        """
        Get list of included files.

        Returns:
            List of FileInfo objects marked as included.
        """
        return [f for f in self._files if f.included]
