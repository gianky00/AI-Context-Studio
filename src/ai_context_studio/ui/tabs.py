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
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..api_client import GeminiAPIClient
from ..config import ConfigManager
from ..constants import COLORS, FONTS, TOKEN_FACTOR
from ..models import (
    ExistingDoc,
    FileInfo,
    GenerationResult,
    GenerationType,
    ScanResult,
    SmartPreset,
)
from ..prompt_engine import PromptEngine
from ..scanner import FastFileScanner
from ..token_estimator import (
    TokenEstimator,
    CostCalculator,
    CostHistoryManager,
    Currency,
    ModelRegistry,
)
from .event_queue import UIEventQueue
from .file_tree import OptimizedFileTree
from .panels import SmartPresetPanel
from .tooltip import add_tooltip

logger = logging.getLogger(__name__)

# Type aliases
StatusCallback = Callable[[str, str], None]
ProgressCallback = Callable[[str, int], None]


class CostHistoryWindow(ctk.CTkToplevel):
    """
    Modal window displaying cost history and statistics.
    """

    def __init__(
        self,
        parent: Any,
        history_manager: CostHistoryManager,
        currency: Currency
    ) -> None:
        super().__init__(parent)

        self.history_manager = history_manager
        self.currency = currency

        self.title("Storico Costi - AI Context Studio")
        self.geometry("800x600")
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        # Center the window
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 800) // 2
        y = (self.winfo_screenheight() - 600) // 2
        self.geometry(f"800x600+{x}+{y}")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the modal UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text="\U0001F4C8 Storico Generazioni",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        # Stats summary
        stats_frame = ctk.CTkFrame(self)
        stats_frame.pack(fill="x", padx=20, pady=10)

        stats_inner = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_inner.pack(fill="x", padx=15, pady=15)

        # Get statistics
        entries = self.history_manager.get_entries(100)
        total_30d = self.history_manager.get_total_spend(self.currency.value, 30)
        total_7d = self.history_manager.get_total_spend(self.currency.value, 7)
        accuracy = self.history_manager.get_accuracy_stats()
        symbol = self.currency.symbol

        # Stat cards
        stat_configs = [
            ("\U0001F4CA Generazioni", str(len(entries)), "Totali"),
            (f"\U0001F4B0 Ultimi 7gg", f"{symbol}{total_7d:.3f}", "Spesa recente"),
            (f"\U0001F4B5 Ultimi 30gg", f"{symbol}{total_30d:.3f}", "Spesa mensile"),
            ("\U0001F3AF Precisione", f"{accuracy['average']:.1%}", f"{accuracy['count']} campioni"),
        ]

        for i, (title, value, subtitle) in enumerate(stat_configs):
            card = ctk.CTkFrame(stats_inner, width=180, height=80)
            card.grid(row=0, column=i, padx=8, pady=5)
            card.grid_propagate(False)

            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=FONTS['body_small']),
                text_color=COLORS['text_muted']
            ).pack(pady=(12, 2))

            ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(size=16, weight="bold")
            ).pack()

            ctk.CTkLabel(
                card,
                text=subtitle,
                font=ctk.CTkFont(size=FONTS['small']),
                text_color=COLORS['text_muted']
            ).pack()

        # History table
        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(
            table_frame,
            text="Ultime Generazioni",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Scrollable list
        scroll_frame = ctk.CTkScrollableFrame(
            table_frame,
            fg_color="transparent"
        )
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        if not entries:
            ctk.CTkLabel(
                scroll_frame,
                text="Nessuna generazione registrata.\nI costi verranno tracciati automaticamente.",
                font=ctk.CTkFont(size=FONTS['body']),
                text_color=COLORS['text_muted']
            ).pack(pady=40)
        else:
            # Table header
            header_row = ctk.CTkFrame(scroll_frame, fg_color=COLORS['bg_light'], corner_radius=6)
            header_row.pack(fill="x", pady=(0, 5))

            headers = ["Data", "Modello", "Token Est.", "Token Reali", "Costo"]
            widths = [140, 160, 100, 100, 100]

            for col, (h, w) in enumerate(zip(headers, widths)):
                ctk.CTkLabel(
                    header_row,
                    text=h,
                    font=ctk.CTkFont(size=FONTS['body_small'], weight="bold"),
                    width=w
                ).grid(row=0, column=col, padx=5, pady=8)

            # Data rows (most recent first)
            for entry in reversed(entries[-50:]):
                row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                row.pack(fill="x", pady=2)

                # Parse timestamp
                try:
                    dt = datetime.fromisoformat(entry.timestamp)
                    date_str = dt.strftime("%d/%m/%Y %H:%M")
                except:
                    date_str = entry.timestamp[:16]

                # Format values
                actual_tokens_str = f"{entry.actual_tokens:,}" if entry.actual_tokens else "-"
                actual_cost_str = f"{symbol}{entry.actual_cost:.4f}" if entry.actual_cost else f"~{symbol}{entry.estimated_cost:.4f}"

                values = [
                    date_str,
                    entry.model_id.replace("gemini-", ""),
                    f"{entry.estimated_tokens:,}",
                    actual_tokens_str,
                    actual_cost_str
                ]

                for col, (v, w) in enumerate(zip(values, widths)):
                    ctk.CTkLabel(
                        row,
                        text=v,
                        font=ctk.CTkFont(size=FONTS['body_small']),
                        width=w,
                        text_color=COLORS['text_muted'] if col == 0 else None
                    ).grid(row=0, column=col, padx=5, pady=4)

        # Footer buttons
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            footer,
            text="\U0001F5D1 Cancella Storico",
            font=ctk.CTkFont(size=FONTS['body_small']),
            fg_color=COLORS['danger'],
            hover_color=COLORS['danger_hover'],
            width=140,
            height=36,
            command=self._clear_history
        ).pack(side="left")

        ctk.CTkButton(
            footer,
            text="Chiudi",
            font=ctk.CTkFont(size=FONTS['body_small']),
            fg_color=COLORS['slate'],
            width=100,
            height=36,
            command=self.destroy
        ).pack(side="right")

    def _clear_history(self) -> None:
        """Clear all history after confirmation."""
        from tkinter import messagebox
        if messagebox.askyesno(
            "Conferma",
            "Vuoi eliminare tutto lo storico dei costi?\nQuesta azione non puo' essere annullata."
        ):
            self.history_manager.clear()
            self.destroy()


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
            bundle_parts.append(f"# Generated by AI Context Studio")
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
                bundle_parts.append(f"## FILE: {f.relative_path}")
                bundle_parts.append(f"## Path: {f.path}")
                bundle_parts.append(f"## Size: {f.size:,} bytes")
                bundle_parts.append("")

                # Determine language for code block
                ext = Path(f.relative_path).suffix.lower()
                lang_map = {
                    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                    '.jsx': 'jsx', '.tsx': 'tsx', '.java': 'java',
                    '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp',
                    '.cs': 'csharp', '.go': 'go', '.rs': 'rust',
                    '.rb': 'ruby', '.php': 'php', '.swift': 'swift',
                    '.kt': 'kotlin', '.scala': 'scala', '.r': 'r',
                    '.sql': 'sql', '.html': 'html', '.css': 'css',
                    '.scss': 'scss', '.json': 'json', '.xml': 'xml',
                    '.yaml': 'yaml', '.yml': 'yaml', '.md': 'markdown',
                    '.sh': 'bash', '.bat': 'batch', '.ps1': 'powershell',
                }
                lang = lang_map.get(ext, '')

                bundle_parts.append(f"```{lang}")
                content = self._scan_result.content_map.get(f.relative_path, "[Content not loaded]")
                bundle_parts.append(content)
                bundle_parts.append("```")
                bundle_parts.append("")
                bundle_parts.append("-" * 80)
                bundle_parts.append("")

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
        GenerationType.ONBOARDING,
        GenerationType.DATABASE,
        GenerationType.DEPLOYMENT,
        GenerationType.DEPENDENCIES,
        GenerationType.PERFORMANCE,
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
        self._last_errors: list[tuple[str, str]] = []  # List of (doc_type, error_message)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the tab UI."""
        # Two-column layout with proper proportions
        left_panel = ctk.CTkFrame(self)
        left_panel.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)

        self.smart_preset_panel = SmartPresetPanel(left_panel)
        self.smart_preset_panel.pack(fill="both", expand=True)

        # Right panel - fixed width, full height
        right_panel = ctk.CTkFrame(self, width=400)
        right_panel.pack(side="right", fill="y", padx=(10, 20), pady=20)
        right_panel.pack_propagate(False)

        self._create_model_section(right_panel)
        self._create_bundle_section(right_panel)
        self._create_single_generators(right_panel)
        self._create_status_section(right_panel)

        self._load_models_from_cache()

    def _create_model_section(self, parent: ctk.CTkFrame) -> None:
        """Create model selection section."""
        model_section = ctk.CTkFrame(parent)
        model_section.pack(fill="x", padx=10, pady=(10, 8))

        model_header = ctk.CTkFrame(model_section, fg_color="transparent")
        model_header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            model_header,
            text="\U0001F916 Modello AI",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(side="left")

        model_row = ctk.CTkFrame(model_section, fg_color="transparent")
        model_row.pack(fill="x", padx=10, pady=(0, 10))

        self.model_combo = ctk.CTkComboBox(
            model_row,
            values=["Connetti API per caricare..."],
            width=320,
            height=38,
            font=ctk.CTkFont(size=FONTS['body']),
            state="readonly"
        )
        self.model_combo.pack(side="left", padx=(0, 8))
        add_tooltip(
            self.model_combo,
            "Seleziona il modello Gemini da usare. I modelli 'pro' sono piu' potenti"
        )

        self.refresh_btn = ctk.CTkButton(
            model_row,
            text="\U0001F504",
            width=42,
            height=38,
            font=ctk.CTkFont(size=FONTS['button']),
            command=self._refresh_models
        )
        self.refresh_btn.pack(side="left")
        add_tooltip(self.refresh_btn, "Ricarica lista modelli (Ctrl+R)")

    def _create_bundle_section(self, parent: ctk.CTkFrame) -> None:
        """Create bundle generation section."""
        bundle_section = ctk.CTkFrame(
            parent,
            fg_color=COLORS['bg_light'],
            corner_radius=8
        )
        bundle_section.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(
            bundle_section,
            text="\u2B50 Generazione Completa",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(anchor="w", padx=12, pady=(12, 4))

        num_docs = len(self.ALL_DOC_TYPES)
        ctk.CTkLabel(
            bundle_section,
            text=f"Genera tutti gli {num_docs} documenti in sequenza",
            font=ctk.CTkFont(size=FONTS['body_small']),
            text_color=COLORS['text_muted']
        ).pack(anchor="w", padx=12, pady=(0, 8))

        self.bundle_btn = ctk.CTkButton(
            bundle_section,
            text=f"\U0001F680 GENERA TUTTI ({num_docs} doc)",
            height=48,
            font=ctk.CTkFont(size=FONTS['button'], weight="bold"),
            fg_color=COLORS['success'],
            hover_color=COLORS['success_hover'],
            command=self._start_bundle_generation
        )
        self.bundle_btn.pack(fill="x", padx=12, pady=(0, 8))
        add_tooltip(
            self.bundle_btn,
            f"Genera tutti gli {num_docs} tipi di documento in sequenza - Scorciatoia: Ctrl+G"
        )

        # Preview prompt button
        self.preview_prompt_btn = ctk.CTkButton(
            bundle_section,
            text="\U0001F50D Anteprima Prompt",
            height=32,
            font=ctk.CTkFont(size=FONTS['body_small']),
            fg_color=COLORS['slate'],
            hover_color="#475569",
            command=self._show_prompt_preview
        )
        self.preview_prompt_btn.pack(fill="x", padx=12, pady=(0, 12))
        add_tooltip(
            self.preview_prompt_btn,
            "Visualizza il prompt completo che verra' inviato all'API"
        )

    def _create_single_generators(self, parent: ctk.CTkFrame) -> None:
        """Create document selection with scrollable multi-select list."""
        gen_section = ctk.CTkFrame(parent)
        gen_section.pack(fill="both", expand=True, padx=10, pady=5)

        # Header with selection buttons
        gen_header = ctk.CTkFrame(gen_section, fg_color="transparent")
        gen_header.pack(fill="x", padx=5, pady=(10, 8))

        ctk.CTkLabel(
            gen_header,
            text="\U0001F4C4 Seleziona Documenti",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(side="left")

        # Selection buttons
        sel_btns = ctk.CTkFrame(gen_header, fg_color="transparent")
        sel_btns.pack(side="right")

        ctk.CTkButton(
            sel_btns,
            text="\u2713 Tutti",
            width=60,
            height=26,
            font=ctk.CTkFont(size=FONTS['small']),
            command=self._select_all_generators
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            sel_btns,
            text="\u2717 Nessuno",
            width=70,
            height=26,
            font=ctk.CTkFont(size=FONTS['small']),
            fg_color=COLORS['slate'],
            command=self._deselect_all_generators
        ).pack(side="left", padx=2)

        # Scrollable frame for generators
        gen_scroll = ctk.CTkScrollableFrame(
            gen_section,
            fg_color="transparent",
            scrollbar_button_color=COLORS['primary'],
            scrollbar_button_hover_color=COLORS['primary_hover']
        )
        gen_scroll.pack(fill="both", expand=True, padx=2, pady=2)

        self.gen_checkboxes: dict[GenerationType, tuple[ctk.CTkCheckBox, tk.BooleanVar]] = {}

        for gt in self.ALL_DOC_TYPES:
            var = tk.BooleanVar(value=False)

            # Card for each generator
            card = ctk.CTkFrame(gen_scroll, fg_color=COLORS['bg_light'], corner_radius=6)
            card.pack(fill="x", pady=3, padx=2)

            card_inner = ctk.CTkFrame(card, fg_color="transparent")
            card_inner.pack(fill="x", padx=4, pady=6)

            # Colored indicator bar
            indicator = ctk.CTkFrame(card_inner, width=5, height=28, fg_color=gt.color, corner_radius=2)
            indicator.pack(side="left", padx=(2, 8))

            cb = ctk.CTkCheckBox(
                card_inner,
                text=f"{gt.icon} {gt.label}",
                variable=var,
                font=ctk.CTkFont(size=FONTS['body']),
                checkbox_width=20,
                checkbox_height=20,
                onvalue=True,
                offvalue=False
            )
            cb.pack(side="left", fill="x", expand=True)

            self.gen_checkboxes[gt] = (cb, var)

            # Add tooltip to both card and checkbox
            add_tooltip(card, gt.description)
            add_tooltip(cb, gt.description)

        # Generate Selected button
        self.gen_selected_btn = ctk.CTkButton(
            gen_section,
            text="\u25B6 Genera Selezionati",
            height=42,
            font=ctk.CTkFont(size=FONTS['body'], weight="bold"),
            fg_color=COLORS['primary'],
            hover_color=COLORS['primary_hover'],
            command=self._start_selected_generation
        )
        self.gen_selected_btn.pack(fill="x", padx=4, pady=(10, 8))
        add_tooltip(self.gen_selected_btn, "Genera solo i documenti selezionati")

    def _select_all_generators(self) -> None:
        """Select all generator checkboxes."""
        for _, (cb, var) in self.gen_checkboxes.items():
            var.set(True)

    def _deselect_all_generators(self) -> None:
        """Deselect all generator checkboxes."""
        for _, (cb, var) in self.gen_checkboxes.items():
            var.set(False)

    def _get_selected_generators(self) -> list[GenerationType]:
        """Get list of selected generators."""
        return [gt for gt, (cb, var) in self.gen_checkboxes.items() if var.get()]

    def _validate_generation(self) -> bool:
        """Validate that generation can proceed."""
        if not self.setup_tab.is_api_connected():
            self._on_status_update(
                "\u26A0\uFE0F Connetti prima l'API nella tab Setup",
                "warning"
            )
            return False

        scan_result = self.setup_tab.get_scan_result()
        if not scan_result:
            self._on_status_update(
                "\u26A0\uFE0F Scansiona prima un progetto nella tab Setup",
                "warning"
            )
            return False

        return True

    def _start_selected_generation(self) -> None:
        """Start generation for selected document types."""
        selected = self._get_selected_generators()
        if not selected:
            self._on_status_update("\u26A0\uFE0F Seleziona almeno un documento da generare", "warning")
            return

        if self._generating:
            self._on_status_update("\u23F3 Generazione gia' in corso...", "warning")
            return

        prepared = self._validate_and_prepare()
        if not prepared:
            return

        selected_model, code_content, smart_preset, scan_result = prepared

        self._set_generating_state(True)
        self._cancel_generation = False
        self._last_errors = []  # Clear previous errors
        self.error_btn.pack_forget()  # Hide error button
        self._on_status_update(
            f"\U0001F680 Generazione di {len(selected)} documenti...",
            "info"
        )

        def selected_task() -> None:
            total_docs = len(selected)
            completed = 0
            failed = 0

            for i, doc_type in enumerate(selected):
                if self._cancel_generation:
                    self.event_queue.put(
                        self._on_bundle_complete,
                        completed,
                        failed,
                        total_docs,
                        True
                    )
                    return

                # Check for existing doc
                existing_doc = self._get_existing_doc_for_type(doc_type, scan_result)
                action = "Aggiornando" if existing_doc else "Generando"

                base_pct = (i / total_docs) * 100
                self.event_queue.put(
                    self._update_gen_status,
                    f"\U0001F4C4 [{i + 1}/{total_docs}] {action} {doc_type.label}...",
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
                    ),
                    existing_doc=existing_doc
                )

                if result.success:
                    completed += 1
                    self.event_queue.put(self._on_generation_complete, result)
                else:
                    failed += 1
                    # Show brief message in status bar
                    brief_msg = result.error_message[:80] + "..." if len(result.error_message) > 80 else result.error_message
                    self.event_queue.put(
                        self._on_status_update,
                        f"\u26A0\uFE0F {doc_type.label} fallito: {brief_msg}",
                        "warning"
                    )
                    # Save error for later viewing
                    self.event_queue.put(
                        self._add_error,
                        doc_type.label,
                        result.error_message
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

        self._executor.submit(selected_task)

    def _create_status_section(self, parent: ctk.CTkFrame) -> None:
        """Create status display section."""
        status_section = ctk.CTkFrame(parent)
        status_section.pack(fill="x", padx=15, pady=(10, 15))

        self.gen_progress = ctk.CTkProgressBar(status_section, width=300, height=12)
        self.gen_progress.pack(pady=(15, 8))
        self.gen_progress.set(0)

        self.gen_status = ctk.CTkLabel(
            status_section,
            text="\u2728 Pronto per generare",
            font=ctk.CTkFont(size=FONTS['body']),
            text_color=COLORS['text_muted']
        )
        self.gen_status.pack(pady=(0, 8))

        self.cancel_btn = ctk.CTkButton(
            status_section,
            text="\u23F9 Interrompi (Esc)",
            width=130,
            height=34,
            font=ctk.CTkFont(size=FONTS['body_small']),
            fg_color=COLORS['danger'],
            hover_color=COLORS['danger_hover'],
            command=self._cancel_current_generation
        )

        # Error details button (initially hidden)
        self.error_btn = ctk.CTkButton(
            status_section,
            text="\u26A0\uFE0F Vedi Errori",
            width=130,
            height=34,
            font=ctk.CTkFont(size=FONTS['body_small']),
            fg_color=COLORS['warning'],
            hover_color="#d97706",
            command=self._show_errors_dialog
        )

    def _show_errors_dialog(self) -> None:
        """Show dialog with all error details."""
        if not self._last_errors:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Dettagli Errori")
        dialog.geometry("700x400")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 700) // 2
        y = (dialog.winfo_screenheight() - 400) // 2
        dialog.geometry(f"700x400+{x}+{y}")

        # Title
        ctk.CTkLabel(
            dialog,
            text=f"Errori durante la generazione ({len(self._last_errors)})",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS['danger']
        ).pack(pady=(15, 10))

        # Build error text
        error_text = ""
        for doc_type, error_msg in self._last_errors:
            error_text += f"{'='*60}\n"
            error_text += f"DOCUMENTO: {doc_type}\n"
            error_text += f"{'='*60}\n"
            error_text += f"{error_msg}\n\n"

        # Scrollable textbox
        textbox = ctk.CTkTextbox(
            dialog,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word"
        )
        textbox.pack(fill="both", expand=True, padx=20, pady=10)
        textbox.insert("1.0", error_text)
        textbox.configure(state="disabled")

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(5, 15))

        def copy_errors():
            dialog.clipboard_clear()
            dialog.clipboard_append(error_text)
            copy_btn.configure(text="Copiato!")
            dialog.after(1500, lambda: copy_btn.configure(text="Copia Tutto"))

        copy_btn = ctk.CTkButton(
            btn_frame,
            text="Copia Tutto",
            command=copy_errors,
            width=120
        )
        copy_btn.pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Chiudi",
            command=dialog.destroy,
            width=100,
            fg_color=COLORS['slate']
        ).pack(side="left", padx=5)

    def _add_error(self, doc_type: str, error_message: str) -> None:
        """Add an error to the list and show the error button."""
        self._last_errors.append((doc_type, error_message))
        if not self.error_btn.winfo_ismapped():
            self.error_btn.pack(pady=(5, 10))

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

    def _show_prompt_preview(self) -> None:
        """Show a preview of the prompt that will be sent to the API."""
        # Validate setup
        scan_result = self.setup_tab.get_scan_result()
        if not scan_result:
            self._on_status_update(
                "\u26A0\uFE0F Scansiona prima un progetto nella tab Setup",
                "warning"
            )
            return

        # Get selected documents or use first one for preview
        selected = self._get_selected_generators()
        if not selected:
            selected = [GenerationType.ARCHITECTURE]

        # Get smart preset
        smart_preset = self.smart_preset_panel.get_preset()

        # Build code content
        code_parts: list[str] = []
        for f in scan_result.selected_files[:10]:  # Limit for preview
            code_parts.append(f"### File: {f.relative_path}")
            file_content = scan_result.content_map.get(f.relative_path, "")
            code_parts.append(f"```\n{file_content[:2000]}{'...' if len(file_content) > 2000 else ''}\n```")
        code_content = "\n".join(code_parts)
        if len(scan_result.selected_files) > 10:
            code_content += f"\n... e altri {len(scan_result.selected_files) - 10} file ..."

        # Build prompt for first selected type
        doc_type = selected[0]
        prompt = PromptEngine.build_prompt(
            doc_type=doc_type,
            code_content=code_content,
            smart_preset=smart_preset
        )

        # Show dialog
        self._show_prompt_dialog(
            f"Anteprima Prompt: {doc_type.label}",
            prompt,
            len(prompt)
        )

    def _show_prompt_dialog(self, title: str, content: str, char_count: int) -> None:
        """Show a dialog with prompt preview."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("900x700")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 900) // 2
        y = (dialog.winfo_screenheight() - 700) // 2
        dialog.geometry(f"900x700+{x}+{y}")

        # Header
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text=f"{char_count:,} caratteri",
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_muted']
        ).pack(side="right")

        # Textbox
        textbox = ctk.CTkTextbox(
            dialog,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word"
        )
        textbox.pack(fill="both", expand=True, padx=20, pady=10)
        textbox.insert("1.0", content)
        textbox.configure(state="disabled")

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 15))

        def copy_prompt():
            dialog.clipboard_clear()
            dialog.clipboard_append(content)
            copy_btn.configure(text="Copiato!")
            dialog.after(1500, lambda: copy_btn.configure(text="Copia Prompt"))

        copy_btn = ctk.CTkButton(
            btn_frame,
            text="Copia Prompt",
            command=copy_prompt,
            width=120
        )
        copy_btn.pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Chiudi",
            fg_color=COLORS['slate'],
            command=dialog.destroy,
            width=100
        ).pack(side="left", padx=5)

    def _validate_and_prepare(
        self
    ) -> Optional[tuple[str, str, SmartPreset, ScanResult]]:
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

        return selected_model, code_content, smart_preset, scan_result

    def _get_existing_doc_for_type(
        self,
        doc_type: GenerationType,
        scan_result: ScanResult
    ) -> Optional[ExistingDoc]:
        """
        Get existing documentation for a generation type.

        Args:
            doc_type: The generation type.
            scan_result: The scan result with existing docs.

        Returns:
            ExistingDoc if found, None otherwise.
        """
        if not scan_result.existing_docs:
            return None

        # Try exact filename match first
        if doc_type.filename in scan_result.existing_docs:
            return scan_result.existing_docs[doc_type.filename]

        # Try case-insensitive match
        filename_lower = doc_type.filename.lower()
        for name, doc in scan_result.existing_docs.items():
            if name.lower() == filename_lower:
                return doc

        return None

    def _set_generating_state(self, generating: bool) -> None:
        """Set UI state during generation."""
        self._generating = generating
        state = "disabled" if generating else "normal"

        self.bundle_btn.configure(state=state)
        self.gen_selected_btn.configure(state=state)
        for _, (cb, var) in self.gen_checkboxes.items():
            cb.configure(state=state)

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

        selected_model, code_content, smart_preset, scan_result = prepared

        # Check for existing doc
        existing_doc = self._get_existing_doc_for_type(gen_type, scan_result)
        action = "Aggiornamento" if existing_doc else "Generazione"

        self._set_generating_state(True)
        self._cancel_generation = False
        self._last_errors = []  # Clear previous errors
        self.error_btn.pack_forget()  # Hide error button
        self._on_status_update(
            f"\U0001F680 {action} {gen_type.label} in corso...",
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
                ),
                existing_doc=existing_doc
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
            brief_msg = result.error_message[:80] + "..." if len(result.error_message) > 80 else result.error_message
            self._on_status_update(
                f"\u274C Errore: {brief_msg}",
                "error"
            )
            # Save error and show button
            self._last_errors = [(result.doc_type.label, result.error_message)]
            self.error_btn.pack(pady=(5, 10))

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

        selected_model, code_content, smart_preset, scan_result = prepared
        total_docs = len(self.ALL_DOC_TYPES)

        self._set_generating_state(True)
        self._cancel_generation = False
        self._last_errors = []  # Clear previous errors
        self.error_btn.pack_forget()  # Hide error button
        self._on_status_update(
            f"\U0001F680 Generazione completa avviata ({total_docs} documenti)...",
            "info"
        )

        def bundle_task() -> None:
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

                # Check for existing doc
                existing_doc = self._get_existing_doc_for_type(doc_type, scan_result)
                action = "Aggiornando" if existing_doc else "Generando"

                base_pct = (i / total_docs) * 100
                self.event_queue.put(
                    self._update_gen_status,
                    f"\U0001F4C4 [{i + 1}/{total_docs}] {action} {doc_type.label}...",
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
                    ),
                    existing_doc=existing_doc
                )

                if result.success:
                    completed += 1
                    self.event_queue.put(self._on_generation_complete, result)
                else:
                    failed += 1
                    # Show brief message in status bar
                    brief_msg = result.error_message[:80] + "..." if len(result.error_message) > 80 else result.error_message
                    self.event_queue.put(
                        self._on_status_update,
                        f"\u26A0\uFE0F {doc_type.label} fallito: {brief_msg}",
                        "warning"
                    )
                    # Save error for later viewing
                    self.event_queue.put(
                        self._add_error,
                        doc_type.label,
                        result.error_message
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

    def _view_mermaid_diagrams(self) -> None:
        """Extract Mermaid diagrams from documents and view them in browser."""
        import re
        import tempfile
        import webbrowser

        # Collect all mermaid blocks from all documents
        mermaid_blocks: list[tuple[str, str]] = []

        for filename, content in self._results.items():
            # Find all mermaid code blocks
            pattern = r'```mermaid\s*([\s\S]*?)```'
            matches = re.findall(pattern, content)
            for match in matches:
                mermaid_blocks.append((filename, match.strip()))

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
        diagrams_html = ""
        for i, (filename, diagram) in enumerate(diagrams, 1):
            diagrams_html += f'''
            <div class="diagram-card">
                <h3>Diagramma {i} - {filename}</h3>
                <div class="mermaid">
{diagram}
                </div>
                <details>
                    <summary>Mostra codice sorgente</summary>
                    <pre><code>{diagram}</code></pre>
                </details>
            </div>
            '''

        return f'''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diagrammi Mermaid - AI Context Studio</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
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
            securityLevel: 'loose'
        }});
    </script>
</body>
</html>'''
