import os
from typing import Optional, Callable
import customtkinter as ctk
from tkinter import ttk

from ...core.models import FileInfo
from ...config.settings import TOKEN_FACTOR

class OptimizedFileTree(ctk.CTkFrame):
    """
    File Tree ottimizzato usando ttk.Treeview.
    Molto più performante del widget con checkbox individuali.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._files: list[FileInfo] = []
        self._on_change_callback: Optional[Callable] = None

        # Style per Treeview
        style = ttk.Style()
        style.configure("Custom.Treeview",
                       font=('Segoe UI', 10),
                       rowheight=25)
        style.configure("Custom.Treeview.Heading",
                       font=('Segoe UI', 10, 'bold'))

        # Frame container
        tree_container = ctk.CTkFrame(self, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Treeview con colonne
        columns = ("size", "tokens", "status")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            selectmode="extended",
            style="Custom.Treeview"
        )

        # Configurazione colonne
        self.tree.heading("#0", text="📄 File", anchor="w")
        self.tree.heading("size", text="Dimensione", anchor="e")
        self.tree.heading("tokens", text="Token", anchor="e")
        self.tree.heading("status", text="Stato", anchor="center")

        self.tree.column("#0", width=400, minwidth=200)
        self.tree.column("size", width=100, minwidth=80)
        self.tree.column("tokens", width=80, minwidth=60)
        self.tree.column("status", width=80, minwidth=60)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(
            btn_frame, text="✓ Seleziona Tutti", width=120,
            command=self._select_all
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="✗ Deseleziona Tutti", width=120,
            command=self._deselect_all
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="↔ Inverti Selezione", width=120,
            command=self._toggle_selected
        ).pack(side="left", padx=2)

        # Bind double-click per toggle
        self.tree.bind("<Double-1>", self._on_double_click)

        # Tags per colori
        self.tree.tag_configure("included", foreground="black")
        self.tree.tag_configure("excluded", foreground="gray")

    def set_on_change_callback(self, callback: Callable) -> None:
        self._on_change_callback = callback

    def load_files(self, files: list[FileInfo]) -> None:
        """Carica lista file nel tree."""
        self._files = files

        # Pulisci tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Organizza per directory
        dirs: dict[str, list[FileInfo]] = {}
        for f in files:
            parts = f.relative_path.split(os.sep)
            if len(parts) > 1:
                dir_name = parts[0]
            else:
                dir_name = "."

            if dir_name not in dirs:
                dirs[dir_name] = []
            dirs[dir_name].append(f)

        # Popola tree
        for dir_name in sorted(dirs.keys()):
            dir_files = dirs[dir_name]

            if dir_name != ".":
                # Crea nodo directory
                dir_id = self.tree.insert(
                    "", "end",
                    text=f"📁 {dir_name}",
                    values=("", "", ""),
                    open=False
                )
                parent = dir_id
            else:
                parent = ""

            for f in sorted(dir_files, key=lambda x: x.relative_path):
                display_name = os.path.basename(f.relative_path)
                icon = self._get_icon(f.extension)
                size_str = self._format_size(f.size)
                tokens = f.size // TOKEN_FACTOR
                status = "✓" if f.included else "✗"
                tag = "included" if f.included else "excluded"

                self.tree.insert(
                    parent, "end",
                    text=f"{icon} {display_name}",
                    values=(size_str, str(tokens), status),
                    tags=(tag, f.relative_path)
                )

    def _get_icon(self, ext: str) -> str:
        icons = {
            '.py': '🐍', '.js': '📜', '.ts': '📘', '.jsx': '⚛️', '.tsx': '⚛️',
            '.html': '🌐', '.css': '🎨', '.json': '📋', '.md': '📝',
            '.sql': '🗄️', '.java': '☕', '.cpp': '⚙️', '.go': '🐹',
            '.rs': '🦀', '.rb': '💎', '.php': '🐘',
        }
        return icons.get(ext, '📄')

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def _on_double_click(self, event) -> None:
        """Toggle inclusione su double-click."""
        item = self.tree.identify_row(event.y)
        if not item:
            return

        tags = self.tree.item(item, "tags")
        if len(tags) >= 2:
            rel_path = tags[1]
            for f in self._files:
                if f.relative_path == rel_path:
                    f.included = not f.included
                    new_status = "✓" if f.included else "✗"
                    new_tag = "included" if f.included else "excluded"
                    self.tree.item(item, values=(
                        self.tree.item(item, "values")[0],
                        self.tree.item(item, "values")[1],
                        new_status
                    ), tags=(new_tag, rel_path))
                    break

        self._notify_change()

    def _select_all(self) -> None:
        for f in self._files:
            f.included = True
        self.load_files(self._files)
        self._notify_change()

    def _deselect_all(self) -> None:
        for f in self._files:
            f.included = False
        self.load_files(self._files)
        self._notify_change()

    def _toggle_selected(self) -> None:
        selected = self.tree.selection()
        for item in selected:
            tags = self.tree.item(item, "tags")
            if len(tags) >= 2:
                rel_path = tags[1]
                for f in self._files:
                    if f.relative_path == rel_path:
                        f.included = not f.included
                        break
        self.load_files(self._files)
        self._notify_change()

    def _notify_change(self) -> None:
        if self._on_change_callback:
            self._on_change_callback()

    def get_included_files(self) -> list[FileInfo]:
        return [f for f in self._files if f.included]
