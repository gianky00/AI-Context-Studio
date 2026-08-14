# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..api_client import GeminiAPIClient
from ..config import ConfigManager
from ..constants import COLORS, FONTS
from ..models import (
    ExistingDoc,
    GenerationResult,
    GenerationType,
    ScanResult,
    SmartPreset,
)
from ..prompt_engine import PromptEngine
from ..token_estimator import (
    TokenEstimator,
)
from .event_queue import UIEventQueue
from .panels import SmartPresetPanel
from .tooltip import add_tooltip
from .setup_tab import SetupTab

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str, str], None]
ProgressCallback = Callable[[str, int], None]


def build_bundle_code_payload(
    code_content: str,
    model_name: str,
    prior_outputs: Optional[list[tuple[str, str]]] = None,
) -> str:
    """
    Return the source payload for one bundle document.

    The first item (no prior successes) keeps the full codebase. Later items
    still send the source; it is truncated with ``...[TRONCATO]...`` only if
    estimated tokens would exceed 80% of the model context window.
    """
    return PromptEngine.build_bundle_code_payload(
        code_content, model_name, prior_outputs
    )


def priors_or_none(
    priors: list[tuple[str, str]],
) -> Optional[list[tuple[str, str]]]:
    """Return accumulated priors, or None for the first sequential item."""
    return priors or None


def record_prior_output(
    priors: list[tuple[str, str]],
    filename: str,
    content: str,
) -> None:
    """Append a successful (filename, content) pair for later sequential items."""
    priors.append((filename, content))


def _sanitize_file_header_path(path: str) -> str:
    """Flatten newlines and drop C0/DEL controls from a FILE header path."""
    flattened = " ".join(path.splitlines())
    return "".join(
        ch for ch in flattened if not (ord(ch) < 32 or ord(ch) == 127)
    )


def build_included_code_content(
    content_map: dict[str, str],
    included_paths: set[str],
) -> str:
    """Concatenate included files from ``content_map`` into a generation payload.

    Iterates ``content_map`` (scan/read order) and omits keys not in
    ``included_paths``. An empty inclusion set yields ``""`` even when
    ``content_map`` is stale/non-empty from a prior read. Non-str content
    (including ``None``) is skipped; empty-string bodies still emit a FILE
    header. Map keys are sanitized only in the FILE header line.
    """
    parts: list[str] = []
    for path, content in content_map.items():
        if path not in included_paths:
            continue
        if not isinstance(content, str):
            continue
        header_path = _sanitize_file_header_path(path)
        parts.append(
            f"\n\n{'=' * 60}\nFILE: {header_path}\n{'=' * 60}\n{content}"
        )
    return "".join(parts)


def is_empty_code_payload(text: str) -> bool:
    """Return True when there is no code payload to send; abort generation.

    Emptiness is the raw string (``not text``), not ``text.strip()``.
    Whitespace-only file bodies still produce FILE headers; an all-excluded
    selection yields the empty string exactly.
    """
    return not text


def is_model_selection_ready(value: object) -> bool:
    """Return True when the combo value is a usable model name.

    Non-strings, whitespace-only values, and any string containing C0
    controls (ord < 32) or DEL (ord == 127) are rejected. The historical
    ``Connetti`` placeholder (``"Connetti API per caricare..."``) is also
    rejected so generation aborts in the UI before the API is called.
    """
    if not isinstance(value, str):
        return False
    if not value.strip():
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    return "Connetti" not in value


def brief_error(message: str, limit: int = 80) -> str:
    """Return a single-line status snippet; truncate with an ellipsis if needed."""
    cleaned_chars: list[str] = []
    prev_space = False
    changed = False
    for ch in message:
        if ch in "\n\r\t":
            changed = True
            if not prev_space:
                cleaned_chars.append(" ")
                prev_space = True
            continue
        if ord(ch) < 32 or ord(ch) == 127:
            changed = True
            continue
        cleaned_chars.append(ch)
        prev_space = ch == " "
    cleaned = "".join(cleaned_chars)
    if changed:
        cleaned = cleaned.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "..."


def find_existing_doc(
    doc_type: GenerationType,
    existing_docs: dict[str, ExistingDoc],
) -> Optional[ExistingDoc]:
    """Look up an existing doc by exact filename, then case-insensitive match."""
    if not existing_docs:
        return None

    if doc_type.filename in existing_docs:
        return existing_docs[doc_type.filename]

    filename_lower = doc_type.filename.lower()
    for name, doc in existing_docs.items():
        if name.lower() == filename_lower:
            return doc

    return None


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
        self._last_input_tokens: int = 0
        self._last_model_name: str = ""

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
        self._reset_cancel_state()
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
            prior_outputs: list[tuple[str, str]] = []

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

                payload = build_bundle_code_payload(
                    code_content, selected_model, prior_outputs
                )
                item_priors = priors_or_none(prior_outputs)

                result = self.api_client.generate_documentation(
                    model_name=selected_model,
                    code_content=payload,
                    doc_type=doc_type,
                    smart_preset=smart_preset,
                    progress_callback=lambda msg, pct: self.event_queue.put(
                        self._update_gen_status,
                        f"\U0001F4C4 [{i + 1}/{total_docs}] {msg}",
                        int(base_pct + (pct / total_docs))
                    ),
                    existing_doc=existing_doc,
                    prior_outputs=item_priors,
                )

                if result.success:
                    completed += 1
                    record_prior_output(
                        prior_outputs, doc_type.filename, result.content
                    )
                    self.event_queue.put(self._on_generation_complete, result)
                    self.event_queue.put(
                        self.setup_tab.record_generation_cost,
                        selected_model,
                        TokenEstimator.estimate_tokens(payload),
                        result.tokens_used,
                    )
                else:
                    failed += 1
                    # Show brief message in status bar
                    brief_msg = brief_error(result.error_message)
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
        self,
        *,
        enforce_context_budget: bool = True,
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
        if not is_model_selection_ready(selected_model):
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

        # Build code content from currently included files only.
        # content_map may be stale/non-empty after a prior read even if the
        # user excluded every file (included_paths empty → empty payload).
        included = self.setup_tab.get_included_files()
        included_paths = {f.relative_path for f in included}
        code_content = build_included_code_content(
            scan_result.content_map, included_paths
        )

        if is_empty_code_payload(code_content):
            self._on_status_update("\u26A0\uFE0F Nessun file selezionato", "warning")
            return None

        input_tokens = TokenEstimator.estimate_tokens(code_content)
        exceeds, usage, window = TokenEstimator.exceeds_context_budget(
            input_tokens, selected_model
        )
        if exceeds and enforce_context_budget:
            self._on_status_update(
                f"\u26A0\uFE0F Contesto troppo grande: {usage:.0f}% della finestra "
                f"({TokenEstimator.format_token_count(window)} token). "
                "Riduci i file selezionati.",
                "error",
            )
            return None
        if exceeds:
            logger.warning(
                "Code exceeds context budget (%.0f%% of %s); "
                "bundle items will be truncated to fit",
                usage,
                TokenEstimator.format_token_count(window),
            )

        self._last_input_tokens = input_tokens
        self._last_model_name = selected_model

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
        return find_existing_doc(doc_type, scan_result.existing_docs)

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

    def _reset_cancel_state(self) -> None:
        """Allow a new generation to start after a previous cancel."""
        self._cancel_generation = False
        self.api_client.clear_cancel()

    def _cancel_current_generation(self) -> None:
        """Request cancellation of current generation."""
        self._cancel_generation = True
        self.api_client.cancel()
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
        self._reset_cancel_state()
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
            self.setup_tab.record_generation_cost(
                self._last_model_name,
                self._last_input_tokens,
                result.tokens_used,
            )
        else:
            self.gen_status.configure(text="\u274C Errore")
            brief_msg = brief_error(result.error_message)
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

        prepared = self._validate_and_prepare(enforce_context_budget=False)
        if not prepared:
            return

        selected_model, code_content, smart_preset, scan_result = prepared
        total_docs = len(self.ALL_DOC_TYPES)

        self._set_generating_state(True)
        self._reset_cancel_state()
        self._last_errors = []  # Clear previous errors
        self.error_btn.pack_forget()  # Hide error button
        self._on_status_update(
            f"\U0001F680 Generazione completa avviata ({total_docs} documenti)...",
            "info"
        )

        def bundle_task() -> None:
            completed = 0
            failed = 0
            prior_outputs: list[tuple[str, str]] = []

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

                payload = build_bundle_code_payload(
                    code_content, selected_model, prior_outputs
                )
                item_priors = priors_or_none(prior_outputs)

                result = self.api_client.generate_documentation(
                    model_name=selected_model,
                    code_content=payload,
                    doc_type=doc_type,
                    smart_preset=smart_preset,
                    progress_callback=lambda msg, pct: self.event_queue.put(
                        self._update_gen_status,
                        f"\U0001F4C4 [{i + 1}/{total_docs}] {msg}",
                        int(base_pct + (pct / total_docs))
                    ),
                    existing_doc=existing_doc,
                    prior_outputs=item_priors,
                )

                if result.success:
                    completed += 1
                    record_prior_output(
                        prior_outputs, doc_type.filename, result.content
                    )
                    self.event_queue.put(self._on_generation_complete, result)
                    self.event_queue.put(
                        self.setup_tab.record_generation_cost,
                        selected_model,
                        TokenEstimator.estimate_tokens(payload),
                        result.tokens_used,
                    )
                else:
                    failed += 1
                    # Show brief message in status bar
                    brief_msg = brief_error(result.error_message)
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

    def shutdown(self) -> None:
        """Stop background workers."""
        self._cancel_generation = True
        self.api_client.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
