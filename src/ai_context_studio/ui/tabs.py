# -*- coding: utf-8 -*-
"""
Tab components for AI Context Studio.

Contains the main application tabs:
- SetupTab: API configuration and project scanning
- GeneratorTab: Document generation controls
- PreviewTab: Document preview and editing
"""

from __future__ import annotations

import logging
import os
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..api_client import GeminiAPIClient
from ..config import ConfigManager
from ..constants import COLORS, TOKEN_FACTOR
from ..models import (
    FileInfo,
    GenerationResult,
    GenerationType,
    ScanResult,
    SmartPreset,
)
from ..scanner import FastFileScanner
from ..token_estimator import TokenEstimator
from .event_queue import UIEventQueue
from .file_tree import OptimizedFileTree
from .panels import SmartPresetPanel
from .tooltip import add_tooltip

logger = logging.getLogger(__name__)

# Type aliases
StatusCallback = Callable[[str, str], None]
ProgressCallback = Callable[[str, int], None]


class SetupTab(ctk.CTkFrame):
    """
    Setup and scanning tab.

    Handles:
    - API key configuration and testing
    - Project folder selection
    - File scanning and statistics
    """

    def __init__(
        self,
        master: Any,
        config: ConfigManager,
        event_queue: UIEventQueue,
        api_client: GeminiAPIClient,
        on_status_update: StatusCallback,
        **kwargs: Any
    ) -> None:
        """
        Initialize the setup tab.

        Args:
            master: Parent widget.
            config: Configuration manager.
            event_queue: UI event queue.
            api_client: Gemini API client.
            on_status_update: Status update callback.
            **kwargs: Additional frame arguments.
        """
        super().__init__(master, **kwargs)

        self.config = config
        self.event_queue = event_queue
        self.api_client = api_client
        self._on_status_update = on_status_update
        self.scanner = FastFileScanner()

        self._scan_result: Optional[ScanResult] = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._scanning = False

        self._setup_ui()
        self._load_initial_state()

    def _setup_ui(self) -> None:
        """Set up the tab UI."""
        self._create_api_section()
        self._create_project_section()
        self._create_stats_section()
        self._create_file_tree_section()

    def _create_api_section(self) -> None:
        """Create API configuration section."""
        api_section = ctk.CTkFrame(self)
        api_section.pack(fill="x", padx=20, pady=(20, 10))

        # Header
        api_header = ctk.CTkFrame(api_section, fg_color="transparent")
        api_header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            api_header,
            text="\U0001F511 Connessione API",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        self.api_status_badge = ctk.CTkLabel(
            api_header,
            text="\u25CF Non connesso",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        )
        self.api_status_badge.pack(side="right")

        # Info box
        info_box = ctk.CTkFrame(
            api_section,
            fg_color=COLORS['bg_light'],
            corner_radius=6
        )
        info_box.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(
            info_box,
            text="\U0001F4A1 Non hai una API Key? Ottienila gratis su: https://makersuite.google.com/app/apikey",
            font=ctk.CTkFont(size=10),
            text_color=COLORS['text_muted']
        ).pack(pady=8)

        # API key row
        api_row = ctk.CTkFrame(api_section, fg_color="transparent")
        api_row.pack(fill="x", padx=15, pady=(0, 15))

        self.api_key_entry = ctk.CTkEntry(
            api_row,
            placeholder_text="Inserisci Google Gemini API Key...",
            show="\u2022",
            width=400,
            height=38
        )
        self.api_key_entry.pack(side="left", padx=(0, 10))
        add_tooltip(
            self.api_key_entry,
            "La tua API Key Google Gemini. Viene salvata in modo sicuro sul tuo computer."
        )

        self.show_key_btn = ctk.CTkButton(
            api_row,
            text="\U0001F441",
            width=38,
            height=38,
            command=self._toggle_key_visibility
        )
        self.show_key_btn.pack(side="left", padx=(0, 10))
        add_tooltip(self.show_key_btn, "Mostra/nascondi la API Key")

        self.connect_btn = ctk.CTkButton(
            api_row,
            text="\U0001F50C Connetti e Salva",
            width=140,
            height=38,
            fg_color=COLORS['primary'],
            hover_color=COLORS['primary_hover'],
            command=self._connect_api
        )
        self.connect_btn.pack(side="left")
        add_tooltip(self.connect_btn, "Testa la connessione e salva la API Key")

    def _create_project_section(self) -> None:
        """Create project selection section."""
        project_section = ctk.CTkFrame(self)
        project_section.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            project_section,
            text="\U0001F4C2 Progetto da Analizzare",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Path row
        path_row = ctk.CTkFrame(project_section, fg_color="transparent")
        path_row.pack(fill="x", padx=15, pady=(0, 10))

        self.path_entry = ctk.CTkEntry(
            path_row,
            placeholder_text="Seleziona la cartella root del progetto...",
            width=500,
            height=38
        )
        self.path_entry.pack(side="left", padx=(0, 10))
        add_tooltip(
            self.path_entry,
            "Il percorso della cartella principale del tuo progetto"
        )

        browse_btn = ctk.CTkButton(
            path_row,
            text="\U0001F4C1 Sfoglia",
            width=100,
            height=38,
            command=self._browse_folder
        )
        browse_btn.pack(side="left", padx=(0, 10))
        add_tooltip(browse_btn, "Apri il file browser per selezionare la cartella")

        self.scan_btn = ctk.CTkButton(
            path_row,
            text="\U0001F50D Scansiona",
            width=120,
            height=38,
            fg_color=COLORS['success'],
            hover_color=COLORS['success_hover'],
            command=self._start_scan
        )
        self.scan_btn.pack(side="left")
        add_tooltip(
            self.scan_btn,
            "Avvia la scansione del progetto per trovare tutti i file di codice"
        )

        # Progress
        self.progress_frame = ctk.CTkFrame(project_section, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            width=600,
            height=8
        )
        self.progress_bar.pack(side="left", padx=(0, 10))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        )
        self.progress_label.pack(side="left")

    def _create_stats_section(self) -> None:
        """Create statistics display section."""
        stats_section = ctk.CTkFrame(self)
        stats_section.pack(fill="x", padx=20, pady=10)

        stats_header = ctk.CTkFrame(stats_section, fg_color="transparent")
        stats_header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            stats_header,
            text="\U0001F4CA Statistiche Progetto",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            stats_header,
            text="Questi dati aiutano a stimare il costo della generazione",
            font=ctk.CTkFont(size=10),
            text_color=COLORS['text_muted']
        ).pack(side="right")

        stats_grid = ctk.CTkFrame(stats_section, fg_color="transparent")
        stats_grid.pack(fill="x", padx=15, pady=(0, 15))

        self.stat_cards: dict[str, ctk.CTkLabel] = {}
        stats_config = [
            ("files", "\U0001F4C4", "File", "--", "Numero di file di codice trovati"),
            ("dirs", "\U0001F4C1", "Cartelle", "--", "Numero di cartelle"),
            ("size", "\U0001F4BE", "Dimensione", "--", "Dimensione totale del codice"),
            ("tokens", "\U0001F3AF", "Token Stimati", "--", "Token stimati per l'AI"),
            ("context", "\U0001F4CF", "Context Usage", "--", "Percentuale del context window utilizzato")
        ]

        for i, (key, icon, label, default, tooltip_text) in enumerate(stats_config):
            card = ctk.CTkFrame(stats_grid, width=140, height=80)
            card.grid(row=0, column=i, padx=8, pady=5)
            card.grid_propagate(False)

            ctk.CTkLabel(
                card,
                text=f"{icon} {label}",
                font=ctk.CTkFont(size=10),
                text_color=COLORS['text_muted']
            ).pack(pady=(12, 2))

            value_label = ctk.CTkLabel(
                card,
                text=default,
                font=ctk.CTkFont(size=18, weight="bold")
            )
            value_label.pack()

            self.stat_cards[key] = value_label
            add_tooltip(card, tooltip_text)

    def _create_file_tree_section(self) -> None:
        """Create file tree section."""
        tree_section = ctk.CTkFrame(self)
        tree_section.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        tree_header = ctk.CTkFrame(tree_section, fg_color="transparent")
        tree_header.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            tree_header,
            text="\U0001F333 File Trovati",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        self.file_tree = OptimizedFileTree(tree_section)
        self.file_tree.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        self.file_tree.set_on_change_callback(self._update_stats)

    def _load_initial_state(self) -> None:
        """Load saved configuration."""
        saved_key = self.config.get_api_key()
        if saved_key:
            self.api_key_entry.insert(0, saved_key)
            self._connect_api(silent=True)

        last_path = self.config.get_last_project_path()
        if last_path and Path(last_path).exists():
            self.path_entry.insert(0, last_path)

    def _toggle_key_visibility(self) -> None:
        """Toggle API key visibility."""
        current = self.api_key_entry.cget("show")
        self.api_key_entry.configure(show="" if current else "\u2022")
        self.show_key_btn.configure(text="\U0001F512" if current else "\U0001F441")

    def _connect_api(self, silent: bool = False) -> None:
        """Connect to the API."""
        key = self.api_key_entry.get().strip()
        if not key:
            if not silent:
                self._on_status_update("\u26A0\uFE0F Inserisci una API Key", "warning")
            return

        self.connect_btn.configure(state="disabled", text="\u23F3 Connessione...")

        def task() -> None:
            self.api_client.configure(key)
            success, message, count = self.api_client.test_connection()
            if success:
                self.api_client.get_available_models()
                self.config.set_api_key(key)
            self.event_queue.put(
                self._on_connect_result,
                success,
                message,
                count,
                silent
            )

        self._executor.submit(task)

    def _on_connect_result(
        self,
        success: bool,
        message: str,
        count: int,
        silent: bool
    ) -> None:
        """Handle API connection result."""
        self.connect_btn.configure(
            state="normal",
            text="\U0001F50C Connetti e Salva"
        )

        if success:
            self.api_status_badge.configure(
                text=f"\u25CF Connesso ({count} modelli)",
                text_color=COLORS['success']
            )
            if not silent:
                self._on_status_update(
                    f"\u2705 {message} - {count} modelli disponibili",
                    "success"
                )
        else:
            self.api_status_badge.configure(
                text="\u25CF Errore",
                text_color=COLORS['danger']
            )
            if not silent:
                self._on_status_update(f"\u274C {message}", "error")

    def _browse_folder(self) -> None:
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(title="Seleziona la root del progetto")
        if folder:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)
            self.config.set_last_project_path(folder)

    def _start_scan(self) -> None:
        """Start project scanning."""
        if self._scanning:
            return

        path = self.path_entry.get().strip()
        if not path or not Path(path).exists():
            self._on_status_update(
                "\u26A0\uFE0F Seleziona una cartella valida",
                "warning"
            )
            return

        self._scanning = True
        self.scan_btn.configure(state="disabled", text="\u23F3 Scansione...")
        self.progress_bar.set(0)

        def scan_task() -> None:
            self.scanner.set_progress_callback(
                lambda msg, pct: self.event_queue.put(
                    self._update_progress, msg, pct
                )
            )
            result = self.scanner.scan(Path(path))
            self.event_queue.put(self._on_scan_complete, result)

        self._executor.submit(scan_task)

    def _update_progress(self, message: str, percent: int) -> None:
        """Update progress display."""
        self.progress_bar.set(percent / 100)
        self.progress_label.configure(text=message)

    def _on_scan_complete(self, result: ScanResult) -> None:
        """Handle scan completion."""
        self._scan_result = result
        self._scanning = False
        self.scan_btn.configure(state="normal", text="\U0001F50D Scansiona")
        self.progress_bar.set(1)
        self.progress_label.configure(text="\u2705 Completato!")

        self.file_tree.load_files(result.files)
        self._update_stats()

        self._on_status_update(
            f"\u2705 Scansione completata: {len(result.files)} file trovati",
            "success"
        )

    def _update_stats(self) -> None:
        """Update statistics display."""
        if not self._scan_result:
            return

        included = self.file_tree.get_included_files()
        total_size = sum(f.size for f in included)
        tokens = total_size // TOKEN_FACTOR

        dirs = set()
        for f in included:
            parts = f.relative_path.split(os.sep)
            if len(parts) > 1:
                dirs.add(parts[0])

        self.stat_cards["files"].configure(text=str(len(included)))
        self.stat_cards["dirs"].configure(text=str(len(dirs)))

        if total_size < 1024:
            size_str = f"{total_size} B"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size / 1024:.1f} KB"
        else:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"

        self.stat_cards["size"].configure(text=size_str)
        self.stat_cards["tokens"].configure(text=f"{tokens:,}")

        usage = TokenEstimator.calculate_usage_percentage(tokens, "gemini-1.5-pro")
        if usage < 50:
            color = COLORS['success']
        elif usage < 80:
            color = COLORS['warning']
        else:
            color = COLORS['danger']
        self.stat_cards["context"].configure(text=f"{usage:.1f}%", text_color=color)

    def get_scan_result(self) -> Optional[ScanResult]:
        """Get the current scan result."""
        return self._scan_result

    def get_included_files(self) -> list[FileInfo]:
        """Get list of included files."""
        return self.file_tree.get_included_files()

    def read_file_contents(
        self,
        progress_callback: Optional[ProgressCallback] = None
    ) -> None:
        """Read contents of included files."""
        if self._scan_result:
            included = self.file_tree.get_included_files()
            for f in self._scan_result.files:
                f.included = any(
                    inc.relative_path == f.relative_path
                    for inc in included
                )
            self.scanner.read_files(self._scan_result, progress_callback)

    def is_api_connected(self) -> bool:
        """Check if API is connected."""
        return "Connesso" in self.api_status_badge.cget("text")


class GeneratorTab(ctk.CTkFrame):
    """
    Document generation tab.

    Handles single and batch document generation.
    """

    ALL_DOC_TYPES: list[GenerationType] = [
        GenerationType.ARCHITECTURE,
        GenerationType.RULES,
        GenerationType.CONTEXT,
        GenerationType.API_DOCS,
        GenerationType.TESTING,
        GenerationType.SECURITY,
        GenerationType.ONBOARDING
    ]

    def __init__(
        self,
        master: Any,
        config: ConfigManager,
        api_client: GeminiAPIClient,
        event_queue: UIEventQueue,
        setup_tab: SetupTab,
        on_generation_complete: Callable[[GenerationResult], None],
        on_status_update: StatusCallback,
        **kwargs: Any
    ) -> None:
        """Initialize the generator tab."""
        super().__init__(master, **kwargs)

        self.config = config
        self.api_client = api_client
        self.event_queue = event_queue
        self.setup_tab = setup_tab
        self._on_generation_complete = on_generation_complete
        self._on_status_update = on_status_update

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._generating = False
        self._cancel_generation = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the tab UI."""
        # Two-column layout
        left_panel = ctk.CTkFrame(self)
        left_panel.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)

        self.smart_preset_panel = SmartPresetPanel(left_panel)
        self.smart_preset_panel.pack(fill="both", expand=True)

        right_panel = ctk.CTkFrame(self)
        right_panel.pack(side="right", fill="both", padx=(10, 20), pady=20, ipadx=10)

        self._create_model_section(right_panel)
        self._create_bundle_section(right_panel)
        self._create_single_generators(right_panel)
        self._create_status_section(right_panel)

        self._load_models_from_cache()

    def _create_model_section(self, parent: ctk.CTkFrame) -> None:
        """Create model selection section."""
        model_section = ctk.CTkFrame(parent)
        model_section.pack(fill="x", padx=15, pady=(15, 10))

        model_header = ctk.CTkFrame(model_section, fg_color="transparent")
        model_header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            model_header,
            text="\U0001F916 Modello AI",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            model_header,
            text="Modelli piu' recenti = migliori risultati",
            font=ctk.CTkFont(size=9),
            text_color=COLORS['text_muted']
        ).pack(side="right")

        model_row = ctk.CTkFrame(model_section, fg_color="transparent")
        model_row.pack(fill="x", padx=10, pady=(0, 10))

        self.model_combo = ctk.CTkComboBox(
            model_row,
            values=["Connetti API per caricare..."],
            width=250,
            state="readonly"
        )
        self.model_combo.pack(side="left", padx=(0, 10))
        add_tooltip(
            self.model_combo,
            "Seleziona il modello Gemini da usare. I modelli 'pro' sono piu' potenti."
        )

        self.refresh_btn = ctk.CTkButton(
            model_row,
            text="\U0001F504",
            width=35,
            height=28,
            command=self._refresh_models
        )
        self.refresh_btn.pack(side="left")
        add_tooltip(self.refresh_btn, "Ricarica la lista dei modelli disponibili")

    def _create_bundle_section(self, parent: ctk.CTkFrame) -> None:
        """Create bundle generation section."""
        bundle_section = ctk.CTkFrame(
            parent,
            fg_color=COLORS['bg_light'],
            corner_radius=8
        )
        bundle_section.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            bundle_section,
            text="\u2B50 Generazione Completa",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=12, pady=(12, 5))

        ctk.CTkLabel(
            bundle_section,
            text="Genera tutti i 7 documenti in sequenza automaticamente",
            font=ctk.CTkFont(size=10),
            text_color=COLORS['text_muted']
        ).pack(anchor="w", padx=12, pady=(0, 8))

        self.bundle_btn = ctk.CTkButton(
            bundle_section,
            text="\U0001F680 GENERA TUTTI (7 documenti)",
            width=280,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS['success'],
            hover_color=COLORS['success_hover'],
            command=self._start_bundle_generation
        )
        self.bundle_btn.pack(pady=(0, 12))
        add_tooltip(
            self.bundle_btn,
            "Genera tutti i 7 tipi di documento in sequenza."
        )

    def _create_single_generators(self, parent: ctk.CTkFrame) -> None:
        """Create single document generation buttons."""
        gen_section = ctk.CTkFrame(parent)
        gen_section.pack(fill="both", expand=True, padx=15, pady=10)

        gen_header = ctk.CTkFrame(gen_section, fg_color="transparent")
        gen_header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            gen_header,
            text="\U0001F4C4 Generatori Singoli",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            gen_header,
            text="Oppure genera un documento specifico",
            font=ctk.CTkFont(size=9),
            text_color=COLORS['text_muted']
        ).pack(side="right")

        gen_grid = ctk.CTkFrame(gen_section, fg_color="transparent")
        gen_grid.pack(fill="both", expand=True, padx=10, pady=5)

        self.gen_buttons: dict[GenerationType, ctk.CTkButton] = {}

        for i, gt in enumerate(self.ALL_DOC_TYPES):
            btn = ctk.CTkButton(
                gen_grid,
                text=f"{gt.icon}\n{gt.label}",
                width=130,
                height=60,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=gt.color,
                command=lambda t=gt: self._start_single_generation(t)
            )
            btn.grid(row=i // 2, column=i % 2, padx=5, pady=5, sticky="nsew")
            self.gen_buttons[gt] = btn
            add_tooltip(btn, gt.description)

        gen_grid.grid_columnconfigure(0, weight=1)
        gen_grid.grid_columnconfigure(1, weight=1)

    def _create_status_section(self, parent: ctk.CTkFrame) -> None:
        """Create status display section."""
        status_section = ctk.CTkFrame(parent)
        status_section.pack(fill="x", padx=15, pady=(10, 15))

        self.gen_progress = ctk.CTkProgressBar(status_section, width=280, height=10)
        self.gen_progress.pack(pady=(15, 5))
        self.gen_progress.set(0)

        self.gen_status = ctk.CTkLabel(
            status_section,
            text="\u2728 Pronto per generare",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        )
        self.gen_status.pack(pady=(0, 5))

        self.cancel_btn = ctk.CTkButton(
            status_section,
            text="\u23F9 Interrompi",
            width=100,
            height=28,
            fg_color=COLORS['danger'],
            hover_color=COLORS['danger_hover'],
            command=self._cancel_current_generation
        )

    def _load_models_from_cache(self) -> None:
        """Load cached models list."""
        cached = self.config.get_cached_models()
        if cached:
            self.model_combo.configure(values=cached)
            self.model_combo.set(cached[0])

    def _refresh_models(self) -> None:
        """Refresh available models list."""
        if not self.setup_tab.is_api_connected():
            self._on_status_update(
                "\u26A0\uFE0F Connetti prima l'API nella tab Setup",
                "warning"
            )
            return

        self.refresh_btn.configure(state="disabled")

        def task() -> None:
            models = self.api_client.get_available_models(force_refresh=True)
            self.event_queue.put(self._on_models_loaded, models)

        self._executor.submit(task)

    def _on_models_loaded(self, models: list[str]) -> None:
        """Handle models list loaded."""
        self.refresh_btn.configure(state="normal")

        if models:
            self.model_combo.configure(values=models)
            self.model_combo.set(models[0])
            self._on_status_update(f"\u2705 {len(models)} modelli caricati", "success")
        else:
            self._on_status_update("\u274C Errore caricamento modelli", "error")

    def _validate_and_prepare(
        self
    ) -> Optional[tuple[str, str, SmartPreset]]:
        """Validate and prepare for generation."""
        if not self.setup_tab.is_api_connected():
            self._on_status_update(
                "\u26A0\uFE0F Connetti prima l'API nella tab Setup",
                "warning"
            )
            return None

        scan_result = self.setup_tab.get_scan_result()
        if not scan_result:
            self._on_status_update(
                "\u26A0\uFE0F Scansiona prima un progetto nella tab Setup",
                "warning"
            )
            return None

        selected_model = self.model_combo.get()
        if "Connetti" in selected_model:
            self._on_status_update("\u26A0\uFE0F Seleziona un modello", "warning")
            return None

        # Read file contents
        self._update_gen_status("\U0001F4D6 Lettura file...", 5)
        self.setup_tab.read_file_contents(
            lambda msg, pct: self.event_queue.put(
                self._update_gen_status, msg, int(pct * 0.1)
            )
        )

        if not scan_result.content_map:
            self._on_status_update(
                "\u26A0\uFE0F Nessun file da analizzare",
                "warning"
            )
            return None

        # Build code content
        included = self.setup_tab.get_included_files()
        included_paths = {f.relative_path for f in included}

        code_content = ""
        for path, content in scan_result.content_map.items():
            if path in included_paths:
                code_content += f"\n\n{'=' * 60}\nFILE: {path}\n{'=' * 60}\n{content}"

        if not code_content:
            self._on_status_update("\u26A0\uFE0F Nessun file selezionato", "warning")
            return None

        smart_preset = self.smart_preset_panel.get_preset()

        return selected_model, code_content, smart_preset

    def _set_generating_state(self, generating: bool) -> None:
        """Set UI state during generation."""
        self._generating = generating
        state = "disabled" if generating else "normal"

        self.bundle_btn.configure(state=state)
        for btn in self.gen_buttons.values():
            btn.configure(state=state)

        if generating:
            self.cancel_btn.pack(pady=(5, 15))
        else:
            self.cancel_btn.pack_forget()

    def _cancel_current_generation(self) -> None:
        """Request cancellation of current generation."""
        self._cancel_generation = True
        self._update_gen_status("\u23F9 Interruzione in corso...", 0)

    def _start_single_generation(self, gen_type: GenerationType) -> None:
        """Start single document generation."""
        if self._generating:
            self._on_status_update(
                "\u23F3 Generazione gia' in corso...",
                "warning"
            )
            return

        prepared = self._validate_and_prepare()
        if not prepared:
            return

        selected_model, code_content, smart_preset = prepared

        self._set_generating_state(True)
        self._cancel_generation = False
        self._on_status_update(
            f"\U0001F680 Generazione {gen_type.label} in corso...",
            "info"
        )

        def task() -> None:
            result = self.api_client.generate_documentation(
                model_name=selected_model,
                code_content=code_content,
                doc_type=gen_type,
                smart_preset=smart_preset,
                progress_callback=lambda msg, pct: self.event_queue.put(
                    self._update_gen_status, msg, pct
                )
            )
            self.event_queue.put(self._on_single_generation_done, result)

        self._executor.submit(task)

    def _on_single_generation_done(self, result: GenerationResult) -> None:
        """Handle single generation completion."""
        self._set_generating_state(False)
        self.gen_progress.set(1 if result.success else 0)

        if result.success:
            time_str = f"{result.generation_time:.1f}s"
            self.gen_status.configure(
                text=f"\u2705 {result.doc_type.label} completato in {time_str}"
            )
            self._on_status_update(
                f"\u2705 {result.doc_type.filename} generato ({result.tokens_used:,} token)",
                "success"
            )
        else:
            self.gen_status.configure(text="\u274C Errore")
            self._on_status_update(
                f"\u274C Errore: {result.error_message[:80]}...",
                "error"
            )

        self._on_generation_complete(result)

    def _start_bundle_generation(self) -> None:
        """Start bundle generation of all documents."""
        if self._generating:
            self._on_status_update(
                "\u23F3 Generazione gia' in corso...",
                "warning"
            )
            return

        prepared = self._validate_and_prepare()
        if not prepared:
            return

        selected_model, code_content, smart_preset = prepared

        self._set_generating_state(True)
        self._cancel_generation = False
        self._on_status_update(
            "\U0001F680 Generazione completa avviata (7 documenti)...",
            "info"
        )

        def bundle_task() -> None:
            total_docs = len(self.ALL_DOC_TYPES)
            completed = 0
            failed = 0

            for i, doc_type in enumerate(self.ALL_DOC_TYPES):
                if self._cancel_generation:
                    self.event_queue.put(
                        self._on_bundle_complete,
                        completed,
                        failed,
                        total_docs,
                        True
                    )
                    return

                base_pct = (i / total_docs) * 100
                self.event_queue.put(
                    self._update_gen_status,
                    f"\U0001F4C4 [{i + 1}/{total_docs}] Generando {doc_type.label}...",
                    int(base_pct)
                )

                result = self.api_client.generate_documentation(
                    model_name=selected_model,
                    code_content=code_content,
                    doc_type=doc_type,
                    smart_preset=smart_preset,
                    progress_callback=lambda msg, pct: self.event_queue.put(
                        self._update_gen_status,
                        f"\U0001F4C4 [{i + 1}/{total_docs}] {msg}",
                        int(base_pct + (pct / total_docs))
                    )
                )

                if result.success:
                    completed += 1
                    self.event_queue.put(self._on_generation_complete, result)
                else:
                    failed += 1
                    self.event_queue.put(
                        self._on_status_update,
                        f"\u26A0\uFE0F {doc_type.label} fallito: {result.error_message[:50]}...",
                        "warning"
                    )

                if i < total_docs - 1:
                    time.sleep(1)

            self.event_queue.put(
                self._on_bundle_complete,
                completed,
                failed,
                total_docs,
                False
            )

        self._executor.submit(bundle_task)

    def _on_bundle_complete(
        self,
        completed: int,
        failed: int,
        total: int,
        cancelled: bool = False
    ) -> None:
        """Handle bundle generation completion."""
        self._set_generating_state(False)
        self.gen_progress.set(1)

        if cancelled:
            self.gen_status.configure(
                text=f"\u23F9 Interrotto ({completed}/{total} completati)"
            )
            self._on_status_update(
                f"\u23F9 Generazione interrotta: {completed}/{total} documenti completati",
                "warning"
            )
        elif failed == 0:
            self.gen_status.configure(
                text=f"\u2705 Tutti i {total} documenti generati!"
            )
            self._on_status_update(
                f"\U0001F389 Generazione completa: tutti i {total} documenti creati!",
                "success"
            )
        else:
            self.gen_status.configure(
                text=f"\u26A0\uFE0F {completed}/{total} completati ({failed} errori)"
            )
            self._on_status_update(
                f"\u26A0\uFE0F Generazione parziale: {completed}/{total} completati",
                "warning"
            )

    def _update_gen_status(self, message: str, percent: int) -> None:
        """Update generation status display."""
        self.gen_status.configure(text=message)
        self.gen_progress.set(percent / 100)


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
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="Modifica i documenti prima di salvarli",
            font=ctk.CTkFont(size=11),
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
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 10))

        self.doc_combo = ctk.CTkComboBox(
            sel_row,
            values=["Nessun documento generato"],
            width=300,
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
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        )
        self.char_label.pack(side="left")

    def _create_editor(self) -> None:
        """Create editor section."""
        editor_frame = ctk.CTkFrame(self)
        editor_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.editor = ctk.CTkTextbox(
            editor_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
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
            text="\U0001F4BE Salva File",
            width=120,
            height=38,
            fg_color=COLORS['success'],
            hover_color=COLORS['success_hover'],
            command=self._save_current
        )
        save_btn.pack(side="left", padx=5)
        add_tooltip(
            save_btn,
            "Salva il documento corrente nella cartella docs/ del progetto"
        )

        save_all_btn = ctk.CTkButton(
            btn_row,
            text="\U0001F4E6 Salva Tutti",
            width=120,
            height=38,
            fg_color=COLORS['primary'],
            hover_color=COLORS['primary_hover'],
            command=self._save_all
        )
        save_all_btn.pack(side="left", padx=5)
        add_tooltip(
            save_all_btn,
            "Salva tutti i documenti generati nella cartella docs/"
        )

        copy_btn = ctk.CTkButton(
            btn_row,
            text="\U0001F4CB Copia",
            width=100,
            height=38,
            command=self._copy
        )
        copy_btn.pack(side="left", padx=5)
        add_tooltip(copy_btn, "Copia il contenuto negli appunti")

        clear_btn = ctk.CTkButton(
            btn_row,
            text="\U0001F5D1\uFE0F Pulisci",
            width=100,
            height=38,
            fg_color=COLORS['slate'],
            command=self._clear_all
        )
        clear_btn.pack(side="left", padx=5)
        add_tooltip(clear_btn, "Elimina tutti i documenti generati")

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
            docs_dir.mkdir(exist_ok=True)
            save_path = docs_dir / self._current_file
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

        docs_dir.mkdir(exist_ok=True)
        saved = 0

        for filename, content in self._results.items():
            try:
                (docs_dir / filename).write_text(content, encoding='utf-8')
                saved += 1
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
