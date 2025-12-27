import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox
import customtkinter as ctk

from ...config import ConfigManager
from ...core.models import GenerationType, GenerationResult
from ...services.gemini_client import GeminiAPIClient
from ..utils import UIEventQueue
from ..components.panels import SmartPresetPanel, GuidePanel

class GeneratorTab(ctk.CTkFrame):
    """Tab per generazione documentazione AI."""

    def __init__(
        self, master, config: ConfigManager, api_client: GeminiAPIClient,
        event_queue: UIEventQueue, get_scan_result, get_included_files,
        get_api_key, read_file_contents, on_generation_complete, **kwargs
    ):
        super().__init__(master, **kwargs)

        self.config = config
        self.api_client = api_client
        self.event_queue = event_queue
        self._get_scan_result = get_scan_result
        self._get_included_files = get_included_files
        self._get_api_key = get_api_key
        self._read_file_contents = read_file_contents
        self._on_generation_complete = on_generation_complete

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._available_models: list[str] = []
        self._generating = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        # ═══ MODELLO ═══
        model_frame = ctk.CTkFrame(self)
        model_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            model_frame, text="🤖 Modello AI",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        model_row = ctk.CTkFrame(model_frame, fg_color="transparent")
        model_row.pack(fill="x", padx=10, pady=(0, 10))

        self.model_combo = ctk.CTkComboBox(
            model_row, values=["Carica modelli..."],
            width=400, state="readonly"
        )
        self.model_combo.pack(side="left", padx=(0, 10))

        self.refresh_btn = ctk.CTkButton(
            model_row, text="🔄 Carica Modelli", width=140,
            command=self._load_models
        )
        self.refresh_btn.pack(side="left")

        self.model_info = ctk.CTkLabel(model_frame, text="", font=ctk.CTkFont(size=11))
        self.model_info.pack(anchor="w", padx=10, pady=(0, 10))

        # ═══ GUIDE PANEL (ISTRUZIONI CUSTOM) ═══
        self.guide_panel = GuidePanel(self)
        self.guide_panel.pack(fill="x", padx=15, pady=10)

        # ═══ SMART PRESET PANEL (AZIONI) ═══
        self.preset_panel = SmartPresetPanel(self, on_generate=self._start_generation)
        self.preset_panel.pack(fill="x", padx=15, pady=10)

        # ═══ STATUS ═══
        status_frame = ctk.CTkFrame(self)
        status_frame.pack(fill="x", padx=15, pady=10)

        self.gen_progress = ctk.CTkProgressBar(status_frame, width=600, mode="indeterminate")
        self.gen_progress.pack(pady=10)
        self.gen_progress.set(0)

        self.gen_status = ctk.CTkLabel(
            status_frame, text="Pronto per generare.",
            font=ctk.CTkFont(size=12)
        )
        self.gen_status.pack(pady=(0, 10))

        # ═══ LOG ═══
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(
            log_frame, text="📜 Log",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self.log_text = ctk.CTkTextbox(
            log_frame, height=120,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _load_models(self) -> None:
        api_key = self._get_api_key()
        if not api_key:
            messagebox.showwarning("Attenzione", "Inserisci prima la API Key")
            return

        self.refresh_btn.configure(state="disabled", text="⏳ Caricamento...")
        self.model_info.configure(text="Recupero modelli...")

        def task():
            self.api_client.configure(api_key)
            models = self.api_client.get_available_models()
            self.event_queue.put(self._on_models_loaded, models)

        self._executor.submit(task)

    def _on_models_loaded(self, models: list[str]) -> None:
        self.refresh_btn.configure(state="normal", text="🔄 Carica Modelli")
        self._available_models = models

        if models:
            self.model_combo.configure(values=models)
            self.model_combo.set(models[0])
            self.model_info.configure(text=f"✅ {len(models)} modelli disponibili", text_color="green")
        else:
            self.model_info.configure(text="❌ Nessun modello trovato", text_color="red")

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _start_generation(self, gen_type: GenerationType) -> None:
        if self._generating:
            return

        scan_result = self._get_scan_result()
        if not scan_result:
            messagebox.showwarning("Attenzione", "Prima scansiona un progetto")
            return

        api_key = self._get_api_key()
        if not api_key:
            messagebox.showwarning("Attenzione", "Inserisci la API Key")
            return

        if not self._available_models:
            messagebox.showwarning("Attenzione", "Carica prima i modelli")
            return

        # Leggi contenuto file
        self._log("Lettura contenuto file...")
        self._read_file_contents()

        if not scan_result.content_map:
            messagebox.showwarning("Attenzione", "Nessun file da analizzare")
            return

        selected_model = self.model_combo.get()

        # Prepara codice
        included = self._get_included_files()
        included_paths = {f.relative_path for f in included}

        code_content = ""
        for path, content in scan_result.content_map.items():
            if path in included_paths:
                code_content += f"\n\n--- FILE: {path} ---\n{content}"

        if not code_content:
            messagebox.showwarning("Attenzione", "Nessun file selezionato")
            return

        # Custom instructions
        custom = self.guide_panel.get_instructions()

        # Disabilita e avvia
        self._generating = True
        self.preset_panel.set_buttons_state("disabled")

        self.gen_progress.start()
        self.gen_status.configure(text=f"🔄 Generazione {gen_type.name}...")
        self._log(f"Avvio: {gen_type.name} con {selected_model}")
        self._log(f"File: {len(included_paths)}, Token input: ~{len(code_content)//4:,}")

        self.api_client.configure(api_key)

        def task():
            result = self.api_client.generate_documentation(
                model_name=selected_model,
                code_content=code_content,
                doc_type=gen_type,
                custom_instructions=custom,
                progress_callback=lambda msg: self.event_queue.put(self._log, msg)
            )
            self.event_queue.put(self._on_generation_done, result)

        self._executor.submit(task)

    def _on_generation_done(self, result: GenerationResult) -> None:
        self._generating = False
        self.preset_panel.set_buttons_state("normal")

        self.gen_progress.stop()
        self.gen_progress.set(0)

        if result.success:
            self.gen_status.configure(
                text=f"✅ Completato in {result.generation_time:.1f}s",
                text_color="green"
            )
            self._log(f"✅ {result.filename} generato ({result.tokens_used:,} token)")
        else:
            self.gen_status.configure(
                text=f"❌ Errore: {result.error_message[:50]}...",
                text_color="red"
            )
            self._log(f"❌ Errore: {result.error_message}")

        self._on_generation_complete(result)
