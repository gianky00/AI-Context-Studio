# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..api_client import GeminiAPIClient
from ..config import ConfigManager
from ..constants import COLORS, FONTS, TOKEN_FACTOR
from ..models import (
    FileInfo,
    ScanResult,
)
from ..scanner import FastFileScanner
from ..token_estimator import (
    CostCalculator,
    CostHistoryManager,
    Currency,
    ModelRegistry,
)
from .event_queue import UIEventQueue
from .file_tree import OptimizedFileTree
from .tooltip import add_tooltip
from .cost_history_window import CostHistoryWindow

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str, str], None]
ProgressCallback = Callable[[str, int], None]

MARKDOWN_FENCE_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".bat": "batch",
    ".ps1": "powershell",
}

_MISSING_FILE_CONTENT = "[Content not loaded]"
_BUNDLE_FILE_SEPARATOR = "-" * 80


def markdown_fence_language(extension: str) -> str:
    """Return the markdown fence language for a file extension.

    Matching is case-insensitive (``.PY`` → ``python``). Unknown extensions
    return an empty string so the fence is untagged.
    """
    key = extension.lower()
    if key and not key.startswith("."):
        key = f".{key}"
    return MARKDOWN_FENCE_LANGUAGES.get(key, "")


def api_status_is_connected(badge_text: str) -> bool:
    """Return True when the API status badge text indicates a live connection.

    Matches the historical ``is_api_connected`` check: the Italian label
    ``Connesso`` must appear as a case-sensitive substring. ``Non connesso``
    (lowercase c) does not match.
    """
    return "Connesso" in badge_text


def api_key_is_usable(key: object) -> bool:
    """Return True when *key* is a non-empty printable API key string.

    Non-strings, whitespace-only values, and any string containing C0
    controls (ord < 32) or DEL (ord == 127) are rejected. ``str.strip``
    does not remove NUL, so ``"\\x00"`` must not be treated as usable.
    """
    if not isinstance(key, str):
        return False
    if not key.strip():
        return False
    return not any(ord(ch) < 32 or ord(ch) == 127 for ch in key)


def project_path_is_usable(path: object) -> bool:
    """Return True when *path* is a non-empty printable project folder string.

    Non-strings, whitespace-only values, and any string containing C0
    controls (ord < 32) or DEL (ord == 127) are rejected. ``str.strip``
    does not remove embedded newlines or NUL, so those must not be
    treated as a usable scan path.
    """
    if not isinstance(path, str):
        return False
    if not path.strip():
        return False
    return not any(ord(ch) < 32 or ord(ch) == 127 for ch in path)


def shutdown_scan_resources(scanner: object, executor: object) -> None:
    """Cancel an in-flight scan, then shut down the worker executor.

    Missing ``cancel`` / ``shutdown`` is skipped. Exceptions from
    ``cancel()`` are logged and swallowed so executor shutdown still runs.
    """
    cancel = getattr(scanner, "cancel", None)
    if callable(cancel):
        try:
            cancel()
        except Exception:
            logger.exception("Scan cancel failed")

    shutdown = getattr(executor, "shutdown", None)
    if callable(shutdown):
        shutdown(wait=False, cancel_futures=True)


def _longest_backtick_run(text: str) -> int:
    """Return the length of the longest consecutive backtick run in ``text``."""
    longest = 0
    current = 0
    for ch in text:
        if ch == "`":
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return longest


def _sanitize_bundle_header_path(text: str) -> str:
    """Flatten line breaks and drop C0/DEL so bundle headers stay one line.

    File *content* is not passed through this helper. ``str.strip`` does not
    remove NUL or DEL, so those must be filtered by ordinal.
    """
    flattened = " ".join(text.splitlines())
    return "".join(
        ch for ch in flattened if not (ord(ch) < 32 or ord(ch) == 127)
    )


def format_bundle_file_section(
    relative_path: str,
    path: str,
    size: int,
    content: str,
) -> str:
    """Assemble one context-bundle file section (header + fenced content).

    Does not touch the filesystem. Unknown extensions produce an untagged fence.
    Opening/closing fences are longer than any backtick run in ``content`` so
    nested markdown fences cannot close the section early.
    Header paths are sanitized so newlines/C0/DEL cannot inject extra headings.
    """
    safe_relative = _sanitize_bundle_header_path(relative_path)
    safe_path = _sanitize_bundle_header_path(path)
    lang = markdown_fence_language(Path(safe_relative).suffix)
    fence = "`" * max(3, _longest_backtick_run(content) + 1)
    return "\n".join(
        [
            f"## FILE: {safe_relative}",
            f"## Path: {safe_path}",
            f"## Size: {size:,} bytes",
            "",
            f"{fence}{lang}",
            content,
            fence,
            "",
            _BUNDLE_FILE_SEPARATOR,
            "",
        ]
    )


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

        # Financial Dashboard
        self._current_currency = Currency.EUR
        self._cost_calculator = CostCalculator(default_currency=self._current_currency)
        self._cost_history = CostHistoryManager()

        self._setup_ui()
        self._load_initial_state()

    def _setup_ui(self) -> None:
        """Set up the tab UI."""
        self._create_api_section()
        self._create_project_section()
        self._create_stats_section()
        self._create_financial_section()
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
            font=ctk.CTkFont(size=FONTS['header'], weight="bold")
        ).pack(side="left")

        self.api_status_badge = ctk.CTkLabel(
            api_header,
            text="\u25CF Non connesso",
            font=ctk.CTkFont(size=FONTS['body_small']),
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
            font=ctk.CTkFont(size=FONTS['body_small']),
            text_color=COLORS['text_muted']
        ).pack(pady=10)

        # API key row
        api_row = ctk.CTkFrame(api_section, fg_color="transparent")
        api_row.pack(fill="x", padx=15, pady=(0, 15))

        self.api_key_entry = ctk.CTkEntry(
            api_row,
            placeholder_text="Inserisci Google Gemini API Key...",
            show="\u2022",
            width=420,
            height=42,
            font=ctk.CTkFont(size=FONTS['body'])
        )
        self.api_key_entry.pack(side="left", padx=(0, 10))
        add_tooltip(
            self.api_key_entry,
            "La tua API Key Google Gemini. Viene salvata in modo sicuro sul tuo computer."
        )

        self.show_key_btn = ctk.CTkButton(
            api_row,
            text="\U0001F441",
            width=42,
            height=42,
            font=ctk.CTkFont(size=FONTS['button']),
            command=self._toggle_key_visibility
        )
        self.show_key_btn.pack(side="left", padx=(0, 10))
        add_tooltip(self.show_key_btn, "Mostra/nascondi la API Key")

        self.connect_btn = ctk.CTkButton(
            api_row,
            text="\U0001F50C Connetti e Salva",
            width=160,
            height=42,
            font=ctk.CTkFont(size=FONTS['button'], weight="bold"),
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
            font=ctk.CTkFont(size=FONTS['header'], weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Path row
        path_row = ctk.CTkFrame(project_section, fg_color="transparent")
        path_row.pack(fill="x", padx=15, pady=(0, 10))

        self.path_entry = ctk.CTkEntry(
            path_row,
            placeholder_text="Seleziona la cartella root del progetto... (Ctrl+O)",
            width=520,
            height=42,
            font=ctk.CTkFont(size=FONTS['body'])
        )
        self.path_entry.pack(side="left", padx=(0, 10))
        add_tooltip(
            self.path_entry,
            "Il percorso della cartella principale del tuo progetto - Scorciatoia: Ctrl+O"
        )

        browse_btn = ctk.CTkButton(
            path_row,
            text="\U0001F4C1 Sfoglia",
            width=110,
            height=42,
            font=ctk.CTkFont(size=FONTS['button']),
            command=self._browse_folder
        )
        browse_btn.pack(side="left", padx=(0, 10))
        add_tooltip(browse_btn, "Apri il file browser - Scorciatoia: Ctrl+O")

        self.scan_btn = ctk.CTkButton(
            path_row,
            text="\U0001F50D Scansiona",
            width=140,
            height=42,
            font=ctk.CTkFont(size=FONTS['button'], weight="bold"),
            fg_color=COLORS['success'],
            hover_color=COLORS['success_hover'],
            command=self._start_scan
        )
        self.scan_btn.pack(side="left")
        add_tooltip(
            self.scan_btn,
            "Avvia la scansione del progetto - Scorciatoia: Ctrl+Enter"
        )

        # Progress
        self.progress_frame = ctk.CTkFrame(project_section, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            width=620,
            height=10
        )
        self.progress_bar.pack(side="left", padx=(0, 10))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(size=FONTS['body_small']),
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
            font=ctk.CTkFont(size=FONTS['header'], weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            stats_header,
            text="Questi dati aiutano a stimare il costo della generazione",
            font=ctk.CTkFont(size=FONTS['body_small']),
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
            card = ctk.CTkFrame(stats_grid, width=155, height=90)
            card.grid(row=0, column=i, padx=8, pady=5)
            card.grid_propagate(False)

            ctk.CTkLabel(
                card,
                text=f"{icon} {label}",
                font=ctk.CTkFont(size=FONTS['body_small']),
                text_color=COLORS['text_muted']
            ).pack(pady=(14, 4))

            value_label = ctk.CTkLabel(
                card,
                text=default,
                font=ctk.CTkFont(size=20, weight="bold")
            )
            value_label.pack()

            self.stat_cards[key] = value_label
            add_tooltip(card, tooltip_text)

    def _create_financial_section(self) -> None:
        """Create financial dashboard section with cost estimation."""
        finance_section = ctk.CTkFrame(self)
        finance_section.pack(fill="x", padx=20, pady=10)

        # Header row with title and currency selector
        finance_header = ctk.CTkFrame(finance_section, fg_color="transparent")
        finance_header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            finance_header,
            text="\U0001F4B0 Financial Dashboard",
            font=ctk.CTkFont(size=FONTS['header'], weight="bold")
        ).pack(side="left")

        # Currency selector
        currency_frame = ctk.CTkFrame(finance_header, fg_color="transparent")
        currency_frame.pack(side="right")

        ctk.CTkLabel(
            currency_frame,
            text="Valuta:",
            font=ctk.CTkFont(size=FONTS['body_small']),
            text_color=COLORS['text_muted']
        ).pack(side="left", padx=(0, 8))

        self.currency_selector = ctk.CTkSegmentedButton(
            currency_frame,
            values=["EUR", "USD"],
            command=self._on_currency_change,
            font=ctk.CTkFont(size=FONTS['body_small']),
            width=120
        )
        self.currency_selector.set("EUR")
        self.currency_selector.pack(side="left")
        # Note: CTkSegmentedButton doesn't support tooltips

        # Cost cards row
        cost_grid = ctk.CTkFrame(finance_section, fg_color="transparent")
        cost_grid.pack(fill="x", padx=15, pady=(0, 10))

        # Card 1: Costo Stimato (current model - Flash by default)
        self.cost_card_flash = self._create_cost_card(
            cost_grid, 0,
            "\u26A1 Flash",
            "Gemini Flash (economico)",
            COLORS['success']
        )

        # Card 2: Costo Pro
        self.cost_card_pro = self._create_cost_card(
            cost_grid, 1,
            "\U0001F31F Pro",
            "Gemini Pro (potente)",
            COLORS['primary']
        )

        # Card 3: Risparmio
        self.cost_card_savings = self._create_cost_card(
            cost_grid, 2,
            "\U0001F4B5 Risparmio",
            "Quanto risparmi con Flash",
            "#10b981"
        )

        # Card 4: Storico Totale
        self.cost_card_total = self._create_cost_card(
            cost_grid, 3,
            "\U0001F4CA Totale 30gg",
            "Spesa totale ultimi 30 giorni",
            COLORS['warning']
        )

        # History button
        history_btn_frame = ctk.CTkFrame(finance_section, fg_color="transparent")
        history_btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.history_btn = ctk.CTkButton(
            history_btn_frame,
            text="\U0001F4C8 Vedi Storico Costi",
            font=ctk.CTkFont(size=FONTS['body_small']),
            fg_color=COLORS['slate'],
            hover_color="#475569",
            height=32,
            width=160,
            command=self._show_cost_history
        )
        self.history_btn.pack(side="left")
        add_tooltip(self.history_btn, "Visualizza lo storico delle generazioni e i costi")

        # Info label
        ctk.CTkLabel(
            history_btn_frame,
            text="I costi si aggiornano automaticamente quando selezioni/deselezioni file",
            font=ctk.CTkFont(size=FONTS['small']),
            text_color=COLORS['text_muted']
        ).pack(side="right")

        # Initialize cost display
        self._update_cost_display()

    def _create_cost_card(
        self,
        parent: ctk.CTkFrame,
        column: int,
        title: str,
        tooltip_text: str,
        accent_color: str
    ) -> dict[str, ctk.CTkLabel]:
        """Create a cost card widget."""
        card = ctk.CTkFrame(parent, width=180, height=90)
        card.grid(row=0, column=column, padx=8, pady=5)
        card.grid_propagate(False)

        # Title with accent bar
        title_frame = ctk.CTkFrame(card, fg_color="transparent")
        title_frame.pack(fill="x", padx=10, pady=(10, 4))

        accent_bar = ctk.CTkFrame(title_frame, width=4, height=16, fg_color=accent_color, corner_radius=2)
        accent_bar.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            title_frame,
            text=title,
            font=ctk.CTkFont(size=FONTS['body_small']),
            text_color=COLORS['text_muted']
        ).pack(side="left")

        # Value
        value_label = ctk.CTkLabel(
            card,
            text="--",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        value_label.pack()

        # Subtitle
        subtitle_label = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=FONTS['small']),
            text_color=COLORS['text_muted']
        )
        subtitle_label.pack()

        add_tooltip(card, tooltip_text)

        return {"value": value_label, "subtitle": subtitle_label, "card": card}

    def _on_currency_change(self, value: str) -> None:
        """Handle currency change."""
        self._current_currency = Currency[value]
        self._cost_calculator = CostCalculator(default_currency=self._current_currency)
        self._update_cost_display()

    def _update_cost_display(self) -> None:
        """Update the financial dashboard with current costs."""
        if not self._scan_result:
            self.cost_card_flash["value"].configure(text="--")
            self.cost_card_flash["subtitle"].configure(text="Scansiona un progetto")
            self.cost_card_pro["value"].configure(text="--")
            self.cost_card_pro["subtitle"].configure(text="")
            self.cost_card_savings["value"].configure(text="--")
            self.cost_card_savings["subtitle"].configure(text="")
        else:
            # Get current token count
            included = self.file_tree.get_included_files()
            total_size = sum(f.size for f in included)
            tokens = total_size // TOKEN_FACTOR

            # Calculate costs for Flash
            flash_estimate = self._cost_calculator.calculate_from_tokens(
                tokens, "gemini-1.5-flash", self._current_currency
            )

            # Calculate costs for Pro
            pro_estimate = self._cost_calculator.calculate_from_tokens(
                tokens, "gemini-1.5-pro", self._current_currency
            )

            # Update Flash card
            self.cost_card_flash["value"].configure(
                text=flash_estimate.format_cost(),
                text_color=COLORS['success']
            )
            self.cost_card_flash["subtitle"].configure(
                text=f"~{flash_estimate.total_tokens:,} token"
            )

            # Update Pro card
            self.cost_card_pro["value"].configure(
                text=pro_estimate.format_cost(),
                text_color=COLORS['primary']
            )
            self.cost_card_pro["subtitle"].configure(
                text=f"~{pro_estimate.total_tokens:,} token"
            )

            # Calculate savings
            savings = pro_estimate.total_cost - flash_estimate.total_cost
            if savings > 0:
                savings_pct = (savings / pro_estimate.total_cost) * 100 if pro_estimate.total_cost > 0 else 0
                self.cost_card_savings["value"].configure(
                    text=flash_estimate.format_cost(savings),
                    text_color="#10b981"
                )
                self.cost_card_savings["subtitle"].configure(
                    text=f"-{savings_pct:.0f}% con Flash"
                )
            else:
                self.cost_card_savings["value"].configure(text="--")
                self.cost_card_savings["subtitle"].configure(text="")

        # Update total spend (always show)
        currency_str = self._current_currency.value
        total_spend = self._cost_history.get_total_spend(currency_str, days=30)
        symbol = self._current_currency.symbol

        if total_spend < 0.01:
            total_str = f"{symbol}0.00"
        elif total_spend < 1:
            total_str = f"{symbol}{total_spend:.3f}"
        else:
            total_str = f"{symbol}{total_spend:.2f}"

        self.cost_card_total["value"].configure(text=total_str)
        self.cost_card_total["subtitle"].configure(text="ultimi 30 giorni")

    def _show_cost_history(self) -> None:
        """Show cost history modal window."""
        CostHistoryWindow(self, self._cost_history, self._current_currency)

    def _create_file_tree_section(self) -> None:
        """Create file tree section."""
        tree_section = ctk.CTkFrame(self)
        tree_section.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        tree_header = ctk.CTkFrame(tree_section, fg_color="transparent")
        tree_header.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            tree_header,
            text="\U0001F333 File Trovati",
            font=ctk.CTkFont(size=FONTS['header'], weight="bold")
        ).pack(side="left")

        # Export context bundle button
        self.export_bundle_btn = ctk.CTkButton(
            tree_header,
            text="\U0001F4E6 Esporta Context Bundle",
            font=ctk.CTkFont(size=FONTS['body_small']),
            fg_color=COLORS['primary'],
            hover_color="#2563eb",
            height=32,
            width=180,
            command=self._export_context_bundle
        )
        self.export_bundle_btn.pack(side="right")
        add_tooltip(
            self.export_bundle_btn,
            "Esporta tutti i file selezionati in un unico file .txt per AI"
        )

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
        if not api_key_is_usable(key):
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
        if not project_path_is_usable(path) or not Path(path).is_dir():
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

        # Detect existing documentation files
        self.scanner.detect_existing_docs(result)

        self.file_tree.load_files(result.files)
        self._update_stats()

        # Build status message with existing docs info
        status_msg = f"\u2705 Scansione completata: {len(result.files)} file trovati"
        if result.existing_docs:
            status_msg += f" | {len(result.existing_docs)} doc .md esistenti"
        self._on_status_update(status_msg, "success")

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

        # Calculate context usage percentage
        model = ModelRegistry.get_model("gemini-1.5-pro")
        usage = (tokens / model.context_window) * 100 if model.context_window > 0 else 0
        if usage < 50:
            color = COLORS['success']
        elif usage < 80:
            color = COLORS['warning']
        else:
            color = COLORS['danger']
        self.stat_cards["context"].configure(text=f"{usage:.1f}%", text_color=color)

        # Update financial dashboard
        self._update_cost_display()

    def get_scan_result(self) -> Optional[ScanResult]:
        """Get the current scan result."""
        return self._scan_result

    def get_included_files(self) -> list[FileInfo]:
        """Get list of included files."""
        return self.file_tree.get_included_files()

    def shutdown(self) -> None:
        """Stop background workers and cancel an in-flight scan."""
        shutdown_scan_resources(self.scanner, self._executor)

    def record_generation_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Persist an estimated generation cost entry."""
        estimate = self._cost_calculator.calculate_from_tokens(
            input_tokens,
            model_name,
            self._current_currency,
            include_output=True,
        )
        self._cost_history.add_entry(
            estimate,
            actual_tokens=input_tokens + output_tokens,
        )
        self._update_cost_display()

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

    def _export_context_bundle(self) -> None:
        """Export all selected files as a single context bundle file."""
        if not self._scan_result:
            self._on_status_update("\u26A0\uFE0F Scansiona prima un progetto", "warning")
            return

        included_files = self.file_tree.get_included_files()
        if not included_files:
            self._on_status_update("\u26A0\uFE0F Nessun file selezionato", "warning")
            return

        # Ask for save location
        save_path = filedialog.asksaveasfilename(
            title="Salva Context Bundle",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("All files", "*.*")
            ],
            initialfile="context_bundle.txt"
        )

        if not save_path:
            return

        try:
            # Read file contents if not already read
            self.read_file_contents()

            # Build the bundle content
            bundle_parts: list[str] = []

            # Header
            project_name = self._scan_result.root_path.name if self._scan_result.root_path else "Project"
            bundle_parts.append(f"# Context Bundle: {project_name}")
            bundle_parts.append("# Generated by AI Context Studio")
            bundle_parts.append(f"# Files: {len(included_files)}")
            bundle_parts.append(f"# Total size: {sum(f.size for f in included_files):,} bytes")
            bundle_parts.append("")
            bundle_parts.append("=" * 80)
            bundle_parts.append("")

            # File index
            bundle_parts.append("## FILE INDEX")
            bundle_parts.append("")
            for i, f in enumerate(included_files, 1):
                bundle_parts.append(f"{i}. {f.relative_path}")
            bundle_parts.append("")
            bundle_parts.append("=" * 80)
            bundle_parts.append("")

            # File contents
            for f in included_files:
                content = self._scan_result.content_map.get(
                    f.relative_path, _MISSING_FILE_CONTENT
                )
                bundle_parts.append(
                    format_bundle_file_section(
                        f.relative_path,
                        str(f.path),
                        f.size,
                        content,
                    )
                )

            # Write to file
            bundle_content = "\n".join(bundle_parts)
            Path(save_path).write_text(bundle_content, encoding='utf-8')

            self._on_status_update(
                f"\u2705 Context Bundle salvato: {Path(save_path).name}",
                "success"
            )

        except Exception as e:
            logger.error("Failed to export context bundle: %s", e)
            self._on_status_update(f"\u274C Errore esportazione: {e}", "error")

    def is_api_connected(self) -> bool:
        """Check if API is connected."""
        return api_status_is_connected(self.api_status_badge.cget("text"))
