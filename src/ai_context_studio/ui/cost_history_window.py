# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from tkinter import messagebox
from typing import Any, Callable, Optional, Sequence

import customtkinter as ctk

from ..constants import COLORS, FONTS
from ..token_estimator import (
    CostHistoryEntry,
    CostHistoryManager,
    Currency,
)

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str, str], None]
ProgressCallback = Callable[[str, int], None]

EMPTY_HISTORY_LABEL = (
    "Nessuna generazione registrata.\nI costi verranno tracciati automaticamente."
)
HISTORY_TABLE_LIMIT = 50


def empty_history_label(entries: Sequence[CostHistoryEntry]) -> str:
    """Return the empty-state copy, or an empty string when rows exist."""
    return EMPTY_HISTORY_LABEL if not entries else ""


def format_entry_timestamp(timestamp: str) -> str:
    """Format an ISO timestamp for the history table, with a short fallback."""
    try:
        return datetime.fromisoformat(timestamp).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return timestamp[:16]


def format_history_row(
    entry: CostHistoryEntry,
    currency: Currency,
) -> tuple[str, str, str, str, str]:
    """Return the five table cells for a history entry."""
    symbol = currency.symbol
    try:
        estimated_tokens_finite = math.isfinite(entry.estimated_tokens)
    except TypeError:
        estimated_tokens_finite = False
    estimated_tokens_str = (
        f"{entry.estimated_tokens:,}" if estimated_tokens_finite else "-"
    )
    if entry.actual_tokens is not None:
        try:
            actual_tokens_finite = math.isfinite(entry.actual_tokens)
        except TypeError:
            actual_tokens_finite = False
        actual_tokens_str = (
            f"{entry.actual_tokens:,}" if actual_tokens_finite else "-"
        )
    else:
        actual_tokens_str = "-"
    if entry.actual_cost is not None:
        try:
            actual_finite = math.isfinite(entry.actual_cost)
        except TypeError:
            actual_finite = False
        cost_str = f"{symbol}{entry.actual_cost:.4f}" if actual_finite else "-"
    else:
        try:
            estimated_finite = math.isfinite(entry.estimated_cost)
        except TypeError:
            estimated_finite = False
        cost_str = (
            f"~{symbol}{entry.estimated_cost:.4f}" if estimated_finite else "-"
        )
    model = entry.model_id.replace("gemini-", "").replace("\n", " ")
    model = "".join(ch for ch in model if not (ord(ch) < 32 or ord(ch) == 127))
    return (
        format_entry_timestamp(entry.timestamp),
        model,
        estimated_tokens_str,
        actual_tokens_str,
        cost_str,
    )


def filter_entries_by_currency(
    entries: Sequence[CostHistoryEntry],
    currency: Currency,
) -> list[CostHistoryEntry]:
    """Keep entries whose stored currency matches ``currency``."""
    code = currency.value
    return [entry for entry in entries if entry.currency == code]


def _as_utc(moment: datetime) -> datetime:
    """Treat naive datetimes as UTC so mixed-tz ordering never raises."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def filter_entries_by_date_range(
    entries: Sequence[CostHistoryEntry],
    days: Optional[int] = None,
    *,
    now: Optional[datetime] = None,
) -> list[CostHistoryEntry]:
    """Keep entries on or after ``now - days``. ``days=None`` keeps all rows."""
    if days is None:
        return list(entries)
    moment = now if now is not None else datetime.now()
    cutoff = _as_utc(moment - timedelta(days=days))
    kept: list[CostHistoryEntry] = []
    for entry in entries:
        try:
            stamp = _as_utc(datetime.fromisoformat(entry.timestamp))
        except (TypeError, ValueError):
            continue
        if stamp >= cutoff:
            kept.append(entry)
    return kept


def select_table_entries(
    entries: Sequence[CostHistoryEntry],
    currency: Currency,
    *,
    days: Optional[int] = None,
    limit: int = HISTORY_TABLE_LIMIT,
    now: Optional[datetime] = None,
) -> list[CostHistoryEntry]:
    """Currency-filter, optional date window, then newest-first up to ``limit``."""
    filtered = filter_entries_by_currency(entries, currency)
    filtered = filter_entries_by_date_range(filtered, days, now=now)
    return list(reversed(filtered[-limit:]))


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
            ("\U0001F4B0 Ultimi 7gg", f"{symbol}{total_7d:.3f}", "Spesa recente"),
            ("\U0001F4B5 Ultimi 30gg", f"{symbol}{total_30d:.3f}", "Spesa mensile"),
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

        table_entries = select_table_entries(entries, self.currency)
        empty_text = empty_history_label(table_entries)
        if empty_text:
            ctk.CTkLabel(
                scroll_frame,
                text=empty_text,
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
            for entry in table_entries:
                row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                row.pack(fill="x", pady=2)

                values = format_history_row(entry, self.currency)

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
        if messagebox.askyesno(
            "Conferma",
            "Vuoi eliminare tutto lo storico dei costi?\nQuesta azione non puo' essere annullata."
        ):
            self.history_manager.clear()
            self.destroy()
