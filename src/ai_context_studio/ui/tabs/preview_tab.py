import json
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

from ...config import ConfigManager
from ...core.models import GenerationResult, GenerationType
from ...config.settings import TOKEN_FACTOR

class PreviewTab(ctk.CTkFrame):
    """Tab per anteprima e modifica documenti."""

    def __init__(self, master, config: ConfigManager, get_scan_result, **kwargs):
        super().__init__(master, **kwargs)

        self.config = config
        self._get_scan_result = get_scan_result
        self._results: dict[str, str] = {}
        self._current_file: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        # ═══ SELETTORE ═══
        sel_frame = ctk.CTkFrame(self)
        sel_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            sel_frame, text="📄 Documento",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        sel_row = ctk.CTkFrame(sel_frame, fg_color="transparent")
        sel_row.pack(fill="x", padx=10, pady=(0, 10))

        self.doc_combo = ctk.CTkComboBox(
            sel_row, values=["Nessun documento"],
            width=300, state="readonly",
            command=self._on_doc_selected
        )
        self.doc_combo.pack(side="left", padx=(0, 10))

        self.char_label = ctk.CTkLabel(sel_row, text="", font=ctk.CTkFont(size=11))
        self.char_label.pack(side="left", padx=10)

        # ═══ EDITOR ═══
        editor_frame = ctk.CTkFrame(self)
        editor_frame.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(
            editor_frame, text="✏️ Editor Markdown",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self.editor = ctk.CTkTextbox(
            editor_frame, font=ctk.CTkFont(family="Consolas", size=12), wrap="word"
        )
        self.editor.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.editor.bind("<KeyRelease>", self._on_text_change)

        # ═══ AZIONI ═══
        actions_frame = ctk.CTkFrame(self)
        actions_frame.pack(fill="x", padx=15, pady=(0, 15))

        btn_row = ctk.CTkFrame(actions_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            btn_row, text="💾 Salva File", width=120, height=35,
            fg_color="#28a745", hover_color="#218838",
            command=self._save_current
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_row, text="📦 Salva Tutti", width=120, height=35,
            fg_color="#17a2b8", hover_color="#138496",
            command=self._save_all
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_row, text="📋 Copia", width=100, height=35,
            command=self._copy
        ).pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(actions_frame, text="", font=ctk.CTkFont(size=11))
        self.status_label.pack(anchor="w", padx=10, pady=(0, 10))

    def add_result(self, result: GenerationResult) -> None:
        if not result.success:
            return

        if result.doc_type == GenerationType.BUNDLE:
            try:
                docs = json.loads(result.content)
                for filename, content in docs.items():
                    self._results[filename] = content
            except json.JSONDecodeError:
                self._results[result.filename] = result.content
        else:
            self._results[result.filename] = result.content

        self.doc_combo.configure(values=list(self._results.keys()))
        first_file = result.filename if result.doc_type != GenerationType.BUNDLE else list(self._results.keys())[0]
        self.doc_combo.set(first_file)
        self._on_doc_selected(first_file)

    def _on_doc_selected(self, filename: str) -> None:
        if filename not in self._results:
            return

        self._current_file = filename
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self._results[filename])
        self._update_char_count()

    def _on_text_change(self, event=None) -> None:
        if self._current_file:
            self._results[self._current_file] = self.editor.get("1.0", "end-1c")
        self._update_char_count()

    def _update_char_count(self) -> None:
        content = self.editor.get("1.0", "end-1c")
        chars = len(content)
        tokens = chars // TOKEN_FACTOR
        self.char_label.configure(text=f"Caratteri: {chars:,} | Token: {tokens:,}")

    def _save_current(self) -> None:
        if not self._current_file:
            return

        scan_result = self._get_scan_result()
        if scan_result:
            docs_dir = scan_result.root_path / "docs"
            docs_dir.mkdir(exist_ok=True)
            save_path = docs_dir / self._current_file
        else:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown", "*.md")],
                initialfile=self._current_file
            )
            if not save_path:
                return
            save_path = Path(save_path)

        try:
            content = self.editor.get("1.0", "end-1c")
            save_path.write_text(content, encoding='utf-8')
            self.status_label.configure(text=f"✅ Salvato: {save_path}", text_color="green")
        except Exception as e:
            self.status_label.configure(text=f"❌ Errore: {e}", text_color="red")

    def _save_all(self) -> None:
        if not self._results:
            return

        scan_result = self._get_scan_result()
        if scan_result:
            docs_dir = scan_result.root_path / "docs"
        else:
            save_dir = filedialog.askdirectory(title="Seleziona cartella")
            if not save_dir:
                return
            docs_dir = Path(save_dir) / "docs"

        docs_dir.mkdir(exist_ok=True)
        saved = 0

        for filename, content in self._results.items():
            try:
                (docs_dir / filename).write_text(content, encoding='utf-8')
                saved += 1
            except Exception:
                pass

        self.status_label.configure(
            text=f"✅ Salvati {saved}/{len(self._results)} in {docs_dir}",
            text_color="green"
        )

    def _copy(self) -> None:
        content = self.editor.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_label.configure(text="✅ Copiato!", text_color="green")
