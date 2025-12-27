import tkinter as tk
from tkinter import filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
import customtkinter as ctk

from ...config import ConfigManager
from ...core.scanner import FastFileScanner
from ...core.models import ScanResult, FileInfo
from ...core.estimator import TokenEstimator
from ...services.gemini_client import GeminiAPIClient
from ..utils import UIEventQueue
from ..components.file_tree import OptimizedFileTree

class SetupTab(ctk.CTkFrame):
    """Tab per configurazione progetto e scansione."""

    def __init__(self, master, config: ConfigManager, event_queue: UIEventQueue, **kwargs):
        super().__init__(master, **kwargs)

        self.config = config
        self.event_queue = event_queue
        self.scanner = FastFileScanner()

        self._scan_result: Optional[ScanResult] = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._scanning = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        # ═══ API KEY ═══
        api_frame = ctk.CTkFrame(self)
        api_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            api_frame,
            text="🔑 Google Gemini API Key",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        key_row = ctk.CTkFrame(api_frame, fg_color="transparent")
        key_row.pack(fill="x", padx=10, pady=(0, 10))

        self.api_key_entry = ctk.CTkEntry(
            key_row,
            placeholder_text="Inserisci la tua API Key...",
            show="•",
            width=400
        )
        self.api_key_entry.pack(side="left", padx=(0, 10))

        # Carica API key salvata
        saved_key = self.config.get_api_key()
        if saved_key:
            self.api_key_entry.insert(0, saved_key)

        self.show_key_btn = ctk.CTkButton(
            key_row, text="👁", width=40,
            command=self._toggle_key_visibility
        )
        self.show_key_btn.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            key_row, text="💾 Salva", width=80,
            command=self._save_api_key
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            key_row, text="🔌 Test Connessione", width=140,
            command=self._test_connection
        ).pack(side="left")

        self.connection_status = ctk.CTkLabel(
            api_frame, text="", font=ctk.CTkFont(size=12)
        )
        self.connection_status.pack(anchor="w", padx=10, pady=(0, 10))

        # ═══ PROGETTO ═══
        project_frame = ctk.CTkFrame(self)
        project_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            project_frame,
            text="📂 Progetto",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        path_row = ctk.CTkFrame(project_frame, fg_color="transparent")
        path_row.pack(fill="x", padx=10, pady=(0, 10))

        self.path_entry = ctk.CTkEntry(
            path_row,
            placeholder_text="Seleziona la cartella root del progetto...",
            width=450
        )
        self.path_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            path_row, text="📁 Sfoglia...", width=100,
            command=self._browse_folder
        ).pack(side="left", padx=(0, 10))

        self.scan_btn = ctk.CTkButton(
            path_row, text="🔍 Scansiona", width=100,
            command=self._start_scan,
            fg_color="#28a745", hover_color="#218838"
        )
        self.scan_btn.pack(side="left")

        # ═══ PROGRESS ═══
        self.progress_label = ctk.CTkLabel(
            project_frame, text="", font=ctk.CTkFont(size=11)
        )
        self.progress_label.pack(anchor="w", padx=10, pady=(0, 10))

        # ═══ TOKEN ESTIMATOR ═══
        stats_frame = ctk.CTkFrame(self)
        stats_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            stats_frame,
            text="📊 Token Estimator",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        stats_row = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=10, pady=10)

        self.stat_labels = {}
        stats = [
            ("files", "📄 File:"),
            ("size", "💾 Dimensione:"),
            ("tokens", "🎯 Token:"),
            ("context", "📏 Context Window:")
        ]

        for key, label in stats:
            frame = ctk.CTkFrame(stats_row, fg_color="transparent")
            frame.pack(side="left", padx=15)

            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=12)).pack(side="left")
            self.stat_labels[key] = ctk.CTkLabel(
                frame, text="--", font=ctk.CTkFont(size=12, weight="bold")
            )
            self.stat_labels[key].pack(side="left", padx=(5, 0))

        # ═══ FILE TREE ═══
        tree_frame = ctk.CTkFrame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(
            tree_frame,
            text="🌳 File Tree (doppio click per toggle)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self.file_tree = OptimizedFileTree(tree_frame)
        self.file_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.file_tree.set_on_change_callback(self._update_stats)

    def _toggle_key_visibility(self) -> None:
        current = self.api_key_entry.cget("show")
        self.api_key_entry.configure(show="" if current else "•")
        self.show_key_btn.configure(text="🔒" if current else "👁")

    def _save_api_key(self) -> None:
        key = self.api_key_entry.get().strip()
        if key:
            self.config.set_api_key(key)
            self.connection_status.configure(text="✅ API Key salvata", text_color="green")
        else:
            self.connection_status.configure(text="⚠️ Inserisci una API Key", text_color="orange")

    def _test_connection(self) -> None:
        key = self.api_key_entry.get().strip()
        if not key:
            self.connection_status.configure(text="⚠️ Inserisci prima la API Key", text_color="orange")
            return

        self.connection_status.configure(text="🔄 Test in corso...", text_color="gray")

        def test_task():
            client = GeminiAPIClient()
            client.configure(key)
            success, message = client.test_connection()
            self.event_queue.put(self._update_connection_status, success, message)

        self._executor.submit(test_task)

    def _update_connection_status(self, success: bool, message: str) -> None:
        color = "green" if success else "red"
        icon = "✅" if success else "❌"
        self.connection_status.configure(text=f"{icon} {message}", text_color=color)

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="Seleziona la root del progetto")
        if folder:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)

    def _start_scan(self) -> None:
        if self._scanning:
            return

        path = self.path_entry.get().strip()
        if not path or not Path(path).exists():
            messagebox.showerror("Errore", "Seleziona una cartella valida")
            return

        self._scanning = True
        self.scan_btn.configure(state="disabled", text="⏳ Scansione...")
        self.progress_label.configure(text="Avvio scansione...")

        def scan_task():
            self.scanner.set_progress_callback(
                lambda msg: self.event_queue.put(self._update_progress, msg)
            )
            result = self.scanner.scan(Path(path))
            self.event_queue.put(self._on_scan_complete, result)

        self._executor.submit(scan_task)

    def _update_progress(self, message: str) -> None:
        self.progress_label.configure(text=message)

    def _on_scan_complete(self, result: ScanResult) -> None:
        self._scan_result = result
        self._scanning = False
        self.scan_btn.configure(state="normal", text="🔍 Scansiona")
        self.progress_label.configure(text=f"✅ Scansione completata! {len(result.files)} file trovati")

        # Carica file nel tree
        self.file_tree.load_files(result.files)

        # Aggiorna statistiche
        self._update_stats()

    def _update_stats(self) -> None:
        if not self._scan_result:
            return

        included = self.file_tree.get_included_files()
        total_size = sum(f.size for f in included)
        tokens = total_size // TOKEN_FACTOR

        self.stat_labels["files"].configure(text=str(len(included)))
        self.stat_labels["size"].configure(text=self._format_size(total_size))
        self.stat_labels["tokens"].configure(text=f"{tokens:,}")

        usage = TokenEstimator.calculate_usage_percentage(tokens, "gemini-1.5-pro")
        color = "green" if usage < 50 else "orange" if usage < 80 else "red"
        self.stat_labels["context"].configure(text=f"{usage:.1f}%", text_color=color)

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def get_scan_result(self) -> Optional[ScanResult]:
        return self._scan_result

    def get_included_files(self) -> list[FileInfo]:
        return self.file_tree.get_included_files()

    def get_api_key(self) -> str:
        return self.api_key_entry.get().strip()

    def read_file_contents(self) -> None:
        """Legge contenuto file inclusi (chiamato prima della generazione)."""
        if self._scan_result:
            # Aggiorna lista file inclusi
            included = self.file_tree.get_included_files()
            self._scan_result.files = [f for f in self._scan_result.files]
            for f in self._scan_result.files:
                f.included = f in included

            self.scanner.read_files(self._scan_result)
