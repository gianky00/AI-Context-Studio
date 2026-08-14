# -*- coding: utf-8 -*-
from __future__ import annotations

import html as html_lib
import logging
import re
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..config import ConfigManager
from ..constants import COLORS, FONTS, TOKEN_FACTOR
from ..models import (
    GenerationResult,
)
from ..path_safety import resolve_contained_file
from .setup_tab import SetupTab
from .tooltip import add_tooltip
from .visualizer_tab import MERMAID_CDN_SCRIPT_TAG, MermaidSanitizer

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str, str], None]
ProgressCallback = Callable[[str, int], None]

_MERMAID_FENCE_PATTERN = re.compile(
    r"(`{3,}|~{3,})[ \t]*(?i:mermaid)\s*([\s\S]*?)\1"
)


def extract_mermaid_blocks(documents: dict[str, str]) -> list[tuple[str, str]]:
    """Extract fenced Mermaid diagrams as ``(filename, body)`` pairs.

    Matches CommonMark `` ```mermaid `` / ``~~~mermaid`` fences (3+ of the
    same opener character; the closer must use that same character).
    The language tag is matched case-insensitively (``Mermaid``, ``MERMAID``).
    Surrounding whitespace in each diagram body is stripped.
    """
    blocks: list[tuple[str, str]] = []
    for filename, content in documents.items():
        for match in _MERMAID_FENCE_PATTERN.finditer(content):
            body = match.group(2).strip()
            if body:
                blocks.append((filename, body))
    return blocks


def _sanitize_preview_filename(filename: str) -> str:
    """Flatten newlines and drop C0/DEL before HTML-escaping a filename."""
    flattened = " ".join(filename.splitlines())
    cleaned = "".join(
        ch for ch in flattened if not (ord(ch) < 32 or ord(ch) == 127)
    )
    return html_lib.escape(cleaned, quote=True)


def build_mermaid_preview_html(diagrams: list[tuple[str, str]]) -> str:
    """Build a standalone HTML page for Mermaid diagrams extracted from docs.

    Filenames are escaped. Diagram source is sanitized then HTML-escaped.
    Mermaid is loaded from the pinned CDN used by the visualizer, with
    ``securityLevel: 'strict'``.
    """
    cards: list[str] = []
    for index, (filename, diagram) in enumerate(diagrams, 1):
        safe_name = _sanitize_preview_filename(filename)
        safe_diagram = MermaidSanitizer.escape_for_html(
            MermaidSanitizer.sanitize(diagram)
        )
        cards.append(
            f"""
            <div class="diagram-card">
                <h3>Diagramma {index} - {safe_name}</h3>
                <div class="mermaid">
{safe_diagram}
                </div>
                <details>
                    <summary>Mostra codice sorgente</summary>
                    <pre><code>{safe_diagram}</code></pre>
                </details>
            </div>
            """
        )
    diagrams_html = "".join(cards)

    return f'''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diagrammi Mermaid - AI Context Studio</title>
    {MERMAID_CDN_SCRIPT_TAG}
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: white;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.5rem;
        }}
        .subtitle {{
            color: #94a3b8;
            text-align: center;
            margin-bottom: 40px;
        }}
        .diagram-card {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }}
        .diagram-card h3 {{
            color: #1e293b;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e2e8f0;
        }}
        .mermaid {{
            display: flex;
            justify-content: center;
            padding: 20px;
            background: #f8fafc;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
        details {{
            margin-top: 15px;
        }}
        summary {{
            cursor: pointer;
            color: #3b82f6;
            font-weight: 500;
        }}
        pre {{
            background: #1e293b;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
            overflow-x: auto;
            font-size: 0.9rem;
        }}
        .footer {{
            text-align: center;
            color: #64748b;
            margin-top: 40px;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Diagrammi Mermaid</h1>
        <p class="subtitle">Generato da AI Context Studio - {len(diagrams)} diagrammi trovati</p>
        {diagrams_html}
        <div class="footer">
            <p>AI Context Studio - Knowledge Base Generator per AI Agents</p>
        </div>
    </div>
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            securityLevel: 'strict',
            flowchart: {{ htmlLabels: false }}
        }});
    </script>
</body>
</html>'''


def ensure_docs_directory(docs_dir: Path) -> Optional[str]:
    """Create ``docs_dir`` if needed; return an Italian error on failure.

    ``Path.mkdir(exist_ok=True)`` still raises ``FileExistsError`` when the
    path already exists as a file. Returns ``None`` on success.
    """
    try:
        if docs_dir.exists() and not docs_dir.is_dir():
            return (
                "\u274C Impossibile creare la cartella docs/: "
                "il percorso esiste già come file"
            )
        docs_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, FileExistsError):
        return (
            "\u274C Impossibile creare la cartella docs/: "
            "percorso non disponibile"
        )
    return None


class PreviewTab(ctk.CTkFrame):
    """
    Document preview and editing tab.

    Allows viewing and editing generated documents before saving.
    """

    def __init__(
        self,
        master: Any,
        config: ConfigManager,
        setup_tab: SetupTab,
        on_status_update: StatusCallback,
        **kwargs: Any
    ) -> None:
        """Initialize the preview tab."""
        super().__init__(master, **kwargs)

        self.config = config
        self.setup_tab = setup_tab
        self._on_status_update = on_status_update

        self._results: dict[str, str] = {}
        self._current_file: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the tab UI."""
        self._create_header()
        self._create_selector()
        self._create_editor()
        self._create_actions()

    def _create_header(self) -> None:
        """Create header section."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text="\U0001F4C4 Documenti Generati",
            font=ctk.CTkFont(size=FONTS['header'], weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="Modifica i documenti prima di salvarli (Ctrl+S salva, Ctrl+Shift+S salva tutti)",
            font=ctk.CTkFont(size=FONTS['body_small']),
            text_color=COLORS['text_muted']
        ).pack(side="right")

    def _create_selector(self) -> None:
        """Create document selector section."""
        selector_frame = ctk.CTkFrame(self)
        selector_frame.pack(fill="x", padx=20, pady=(0, 10))

        sel_row = ctk.CTkFrame(selector_frame, fg_color="transparent")
        sel_row.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(
            sel_row,
            text="\U0001F4C1 Documento:",
            font=ctk.CTkFont(size=FONTS['body'], weight="bold")
        ).pack(side="left", padx=(0, 10))

        self.doc_combo = ctk.CTkComboBox(
            sel_row,
            values=["Nessun documento generato"],
            width=340,
            height=36,
            font=ctk.CTkFont(size=FONTS['body']),
            state="readonly",
            command=self._on_doc_selected
        )
        self.doc_combo.pack(side="left", padx=(0, 20))
        add_tooltip(
            self.doc_combo,
            "Seleziona il documento da visualizzare/modificare"
        )

        self.char_label = ctk.CTkLabel(
            sel_row,
            text="",
            font=ctk.CTkFont(size=FONTS['body_small']),
            text_color=COLORS['text_muted']
        )
        self.char_label.pack(side="left")

    def _create_editor(self) -> None:
        """Create editor section."""
        editor_frame = ctk.CTkFrame(self)
        editor_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.editor = ctk.CTkTextbox(
            editor_frame,
            font=ctk.CTkFont(family="Consolas", size=FONTS['editor']),
            wrap="word"
        )
        self.editor.pack(fill="both", expand=True, padx=15, pady=15)
        self.editor.bind("<KeyRelease>", self._on_text_change)

        self.editor.insert(
            "1.0",
            "I documenti generati appariranno qui.\n\n"
            "Vai alla tab 'Generatore' per creare documentazione."
        )
        self.editor.configure(state="disabled")

    def _create_actions(self) -> None:
        """Create action buttons section."""
        actions_frame = ctk.CTkFrame(self)
        actions_frame.pack(fill="x", padx=20, pady=(0, 20))

        btn_row = ctk.CTkFrame(actions_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=15)

        save_btn = ctk.CTkButton(
            btn_row,
            text="\U0001F4BE Salva (Ctrl+S)",
            width=150,
            height=42,
            font=ctk.CTkFont(size=FONTS['button']),
            fg_color=COLORS['success'],
            hover_color=COLORS['success_hover'],
            command=self._save_current
        )
        save_btn.pack(side="left", padx=5)
        add_tooltip(
            save_btn,
            "Salva il documento corrente - Scorciatoia: Ctrl+S"
        )

        save_all_btn = ctk.CTkButton(
            btn_row,
            text="\U0001F4E6 Salva Tutti",
            width=140,
            height=42,
            font=ctk.CTkFont(size=FONTS['button']),
            fg_color=COLORS['primary'],
            hover_color=COLORS['primary_hover'],
            command=self._save_all
        )
        save_all_btn.pack(side="left", padx=5)
        add_tooltip(
            save_all_btn,
            "Salva tutti i documenti - Scorciatoia: Ctrl+Shift+S"
        )

        copy_btn = ctk.CTkButton(
            btn_row,
            text="\U0001F4CB Copia",
            width=110,
            height=42,
            font=ctk.CTkFont(size=FONTS['button']),
            command=self._copy
        )
        copy_btn.pack(side="left", padx=5)
        add_tooltip(copy_btn, "Copia il contenuto negli appunti")

        clear_btn = ctk.CTkButton(
            btn_row,
            text="\U0001F5D1\uFE0F Pulisci",
            width=110,
            height=42,
            font=ctk.CTkFont(size=FONTS['button']),
            fg_color=COLORS['slate'],
            command=self._clear_all
        )
        clear_btn.pack(side="left", padx=5)
        add_tooltip(clear_btn, "Elimina tutti i documenti generati")

        # Mermaid diagrams button
        mermaid_btn = ctk.CTkButton(
            btn_row,
            text="\U0001F4CA Diagrammi",
            width=120,
            height=42,
            font=ctk.CTkFont(size=FONTS['button']),
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            command=self._view_mermaid_diagrams
        )
        mermaid_btn.pack(side="left", padx=5)
        add_tooltip(mermaid_btn, "Visualizza i diagrammi Mermaid nel browser")

    def add_result(self, result: GenerationResult) -> None:
        """
        Add a generation result.

        Args:
            result: The generation result to add.
        """
        if not result.success:
            return

        self._results[result.doc_type.filename] = result.content

        if len(self._results) == 1:
            self.editor.configure(state="normal")
            self.editor.delete("1.0", "end")

        self.doc_combo.configure(values=list(self._results.keys()))
        self.doc_combo.set(result.doc_type.filename)
        self._on_doc_selected(result.doc_type.filename)

    def _on_doc_selected(self, filename: str) -> None:
        """Handle document selection change."""
        if filename not in self._results:
            return

        self._current_file = filename
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self._results[filename])
        self._update_char_count()

    def _on_text_change(self, event: Any = None) -> None:
        """Handle editor text change."""
        if self._current_file:
            self._results[self._current_file] = self.editor.get("1.0", "end-1c")
        self._update_char_count()

    def _update_char_count(self) -> None:
        """Update character count display."""
        content = self.editor.get("1.0", "end-1c")
        chars = len(content)
        tokens = chars // TOKEN_FACTOR
        lines = content.count('\n') + 1
        self.char_label.configure(
            text=f"\U0001F4CA {lines} righe | {chars:,} caratteri | ~{tokens:,} token"
        )

    def _save_current(self) -> None:
        """Save current document."""
        if not self._current_file:
            self._on_status_update(
                "\u26A0\uFE0F Nessun documento da salvare",
                "warning"
            )
            return

        scan_result = self.setup_tab.get_scan_result()
        if scan_result:
            docs_dir = scan_result.root_path / "docs"
            mkdir_error = ensure_docs_directory(docs_dir)
            if mkdir_error:
                self._on_status_update(mkdir_error, "error")
                return
            try:
                save_path = resolve_contained_file(docs_dir, self._current_file)
            except ValueError as e:
                logger.error("Rejected save path %s: %s", self._current_file, e)
                self._on_status_update(
                    "\u274C Nome file non valido: il salvataggio resta in docs/",
                    "error",
                )
                return
        else:
            save_path_str = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown", "*.md"), ("Tutti", "*.*")],
                initialfile=self._current_file
            )
            if not save_path_str:
                return
            save_path = Path(save_path_str)

        try:
            content = self.editor.get("1.0", "end-1c")
            save_path.write_text(content, encoding='utf-8')
            self._on_status_update(f"\u2705 Salvato: {save_path}", "success")
        except Exception as e:
            logger.error("Failed to save file: %s", e)
            self._on_status_update(f"\u274C Errore salvataggio: {e}", "error")

    def _save_all(self) -> None:
        """Save all documents."""
        if not self._results:
            self._on_status_update(
                "\u26A0\uFE0F Nessun documento da salvare",
                "warning"
            )
            return

        scan_result = self.setup_tab.get_scan_result()
        if scan_result:
            docs_dir = scan_result.root_path / "docs"
        else:
            save_dir = filedialog.askdirectory(
                title="Seleziona cartella di destinazione"
            )
            if not save_dir:
                return
            docs_dir = Path(save_dir) / "docs"

        mkdir_error = ensure_docs_directory(docs_dir)
        if mkdir_error:
            self._on_status_update(mkdir_error, "error")
            return

        saved = 0

        for filename, content in self._results.items():
            try:
                target = resolve_contained_file(docs_dir, filename)
                target.write_text(content, encoding='utf-8')
                saved += 1
            except ValueError as e:
                logger.error("Rejected save path %s: %s", filename, e)
            except Exception as e:
                logger.error("Failed to save %s: %s", filename, e)

        self._on_status_update(
            f"\u2705 Salvati {saved}/{len(self._results)} documenti in {docs_dir}",
            "success"
        )

    def _copy(self) -> None:
        """Copy editor content to clipboard."""
        content = self.editor.get("1.0", "end-1c")
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self._on_status_update("\u2705 Copiato negli appunti!", "success")

    def _clear_all(self) -> None:
        """Clear all generated documents."""
        if self._results:
            if messagebox.askyesno(
                "Conferma",
                "Vuoi eliminare tutti i documenti generati?"
            ):
                self._results.clear()
                self._current_file = None
                self.doc_combo.configure(values=["Nessun documento generato"])
                self.doc_combo.set("Nessun documento generato")
                self.editor.configure(state="normal")
                self.editor.delete("1.0", "end")
                self.editor.insert(
                    "1.0",
                    "I documenti generati appariranno qui.\n\n"
                    "Vai alla tab 'Generatore' per creare documentazione."
                )
                self.editor.configure(state="disabled")
                self.char_label.configure(text="")
                self._on_status_update(
                    "\U0001F5D1\uFE0F Documenti eliminati",
                    "info"
                )

    def _view_mermaid_diagrams(self) -> None:
        """Extract Mermaid diagrams from documents and view them in browser."""
        import tempfile
        import webbrowser

        mermaid_blocks = extract_mermaid_blocks(self._results)

        if not mermaid_blocks:
            self._on_status_update(
                "\u26A0\uFE0F Nessun diagramma Mermaid trovato nei documenti",
                "warning"
            )
            return

        # Generate HTML with Mermaid rendering
        html_content = self._generate_mermaid_html(mermaid_blocks)

        # Save to temp file and open in browser
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.html',
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(html_content)
                temp_path = f.name

            webbrowser.open(f'file://{temp_path}')
            self._on_status_update(
                f"\u2705 Aperti {len(mermaid_blocks)} diagrammi nel browser",
                "success"
            )
        except Exception as e:
            logger.error("Failed to open mermaid diagrams: %s", e)
            self._on_status_update(f"\u274C Errore: {e}", "error")

    def _generate_mermaid_html(
        self,
        diagrams: list[tuple[str, str]]
    ) -> str:
        """Generate HTML page with Mermaid diagrams."""
        return build_mermaid_preview_html(diagrams)
