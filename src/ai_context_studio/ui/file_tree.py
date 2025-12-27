# -*- coding: utf-8 -*-
"""
Optimized file tree widget for AI Context Studio.

Provides a tree view of project files with selection capabilities.
"""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..constants import COLORS, FILE_ICONS, FONTS, TOKEN_FACTOR
from ..models import FileInfo
from .tooltip import add_tooltip

logger = logging.getLogger(__name__)


class OptimizedFileTree(ctk.CTkFrame):
    """
    File tree widget using ttk.Treeview.

    Displays project files in a tree structure with:
    - File size and token count display
    - Include/exclude toggle via double-click or right-click menu
    - Bulk selection operations
    - Visual indicators for selection state

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
        self._setup_context_menu()

    def _setup_style(self) -> None:
        """Configure ttk styles for the tree."""
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            font=('Segoe UI', FONTS['body']),
            rowheight=30
        )
        style.configure(
            "Custom.Treeview.Heading",
            font=('Segoe UI', FONTS['body'], 'bold')
        )

    def _setup_ui(self) -> None:
        """Set up the file tree UI."""
        # Info header
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=5, pady=(5, 0))

        ctk.CTkLabel(
            info_frame,
            text="\U0001F4A1 Doppio click o tasto destro per selezionare/deselezionare",
            font=ctk.CTkFont(size=FONTS['body']),
            text_color=COLORS['text_muted']
        ).pack(side="left")

        # Tree container
        tree_container = ctk.CTkFrame(self, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Create treeview with selection column
        columns = ("size", "tokens", "status")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            selectmode="extended",
            style="Custom.Treeview"
        )

        # Configure columns - headers aligned LEFT
        self.tree.heading("#0", text="\U0001F4C4 File", anchor="w")
        self.tree.heading("size", text="Dimensione", anchor="w")
        self.tree.heading("tokens", text="Token", anchor="w")
        self.tree.heading("status", text="Selezione", anchor="w")

        self.tree.column("#0", width=320, minwidth=200, anchor="w")
        self.tree.column("size", width=90, minwidth=70, anchor="w")
        self.tree.column("tokens", width=80, minwidth=60, anchor="w")
        self.tree.column("status", width=90, minwidth=70, anchor="w")

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
            text="\u2713 Seleziona Tutti",
            width=120,
            height=34,
            font=ctk.CTkFont(size=FONTS['body']),
            fg_color=COLORS['success'],
            hover_color=COLORS['success_hover'],
            command=self._select_all
        )
        btn_all.pack(side="left", padx=3)
        add_tooltip(btn_all, "Seleziona tutti i file per includerli nella generazione")

        btn_none = ctk.CTkButton(
            btn_frame,
            text="\u2717 Deseleziona Tutti",
            width=130,
            height=34,
            font=ctk.CTkFont(size=FONTS['body']),
            fg_color=COLORS['danger'],
            hover_color=COLORS['danger_hover'],
            command=self._deselect_all
        )
        btn_none.pack(side="left", padx=3)
        add_tooltip(btn_none, "Deseleziona tutti i file")

        btn_toggle = ctk.CTkButton(
            btn_frame,
            text="\u2194 Inverti",
            width=90,
            height=34,
            font=ctk.CTkFont(size=FONTS['body']),
            fg_color=COLORS['slate'],
            command=self._toggle_all
        )
        btn_toggle.pack(side="left", padx=3)
        add_tooltip(
            btn_toggle,
            "Inverti la selezione: i selezionati diventano esclusi e viceversa"
        )

        # Bind events
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        # Configure tags for visual styling
        self.tree.tag_configure("included", foreground="#1a1a1a")
        self.tree.tag_configure("excluded", foreground="#999999")
        self.tree.tag_configure("folder", foreground="#555555")

    def _setup_context_menu(self) -> None:
        """Create right-click context menu."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.configure(
            font=('Segoe UI', 11),
            bg='white',
            fg='black',
            activebackground=COLORS['primary'],
            activeforeground='white'
        )
        self.context_menu.add_command(
            label="\u2713  Seleziona",
            command=self._select_selected_items
        )
        self.context_menu.add_command(
            label="\u2717  Deseleziona",
            command=self._deselect_selected_items
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="\u2194  Inverti selezione",
            command=self._toggle_selected_items
        )

    def _on_right_click(self, event: Any) -> None:
        """
        Handle right-click to show context menu.

        Args:
            event: The tkinter event.
        """
        # Select the item under cursor if not already selected
        item = self.tree.identify_row(event.y)
        if item:
            selected = self.tree.selection()
            if item not in selected:
                self.tree.selection_set(item)

        # Show context menu
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _select_selected_items(self) -> None:
        """Select (include) all tree-selected items."""
        selected = self.tree.selection()
        self._set_items_included(selected, True)

    def _deselect_selected_items(self) -> None:
        """Deselect (exclude) all tree-selected items."""
        selected = self.tree.selection()
        self._set_items_included(selected, False)

    def _toggle_selected_items(self) -> None:
        """Toggle selection for all tree-selected items."""
        selected = self.tree.selection()
        for item in selected:
            tags = self.tree.item(item, "tags")
            if len(tags) >= 2:
                rel_path = tags[1]
                for f in self._files:
                    if f.relative_path == rel_path:
                        f.included = not f.included
                        self._update_item_display(item, f)
                        break
        self._notify_change()

    def _set_items_included(self, items: tuple, included: bool) -> None:
        """
        Set included status for multiple items.

        Args:
            items: Tree item IDs.
            included: Whether to include or exclude.
        """
        for item in items:
            tags = self.tree.item(item, "tags")
            if len(tags) >= 2:
                rel_path = tags[1]
                for f in self._files:
                    if f.relative_path == rel_path:
                        f.included = included
                        self._update_item_display(item, f)
                        break
        self._notify_change()

    def _update_item_display(self, item: str, file_info: FileInfo) -> None:
        """
        Update the visual display of a tree item.

        Args:
            item: Tree item ID.
            file_info: File information.
        """
        vals = self.tree.item(item, "values")
        if file_info.included:
            new_status = "\u2713 Incluso"
            new_tag = "included"
        else:
            new_status = "\u2717 Escluso"
            new_tag = "excluded"

        self.tree.item(
            item,
            values=(vals[0], vals[1], new_status),
            tags=(new_tag, file_info.relative_path)
        )

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
                # Count included files in this folder
                included_count = sum(1 for f in dir_files if f.included)
                total_count = len(dir_files)
                folder_status = f"{included_count}/{total_count}"

                dir_id = self.tree.insert(
                    "",
                    "end",
                    text=f"\U0001F4C1 {dir_name}",
                    values=("", "", folder_status),
                    open=False,
                    tags=("folder",)
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
        if file_info.size >= 1024 * 1024:
            size_str = f"{file_info.size / (1024 * 1024):.1f} MB"
        elif file_info.size >= 1024:
            size_str = f"{file_info.size / 1024:.1f} KB"
        else:
            size_str = f"{file_info.size} B"

        tokens = file_info.size // TOKEN_FACTOR

        # Status with text
        if file_info.included:
            status = "\u2713 Incluso"
            tag = "included"
        else:
            status = "\u2717 Escluso"
            tag = "excluded"

        self.tree.insert(
            parent,
            "end",
            text=f"{icon} {display_name}",
            values=(size_str, f"{tokens:,}", status),
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
        if len(tags) >= 2 and tags[0] != "folder":
            rel_path = tags[1]
            for f in self._files:
                if f.relative_path == rel_path:
                    f.included = not f.included
                    self._update_item_display(item, f)
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
