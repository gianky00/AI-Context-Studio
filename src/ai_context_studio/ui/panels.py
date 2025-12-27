# -*- coding: utf-8 -*-
"""
Panel components for AI Context Studio.

Contains reusable panel widgets for configuration and help.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Any

import customtkinter as ctk

from ..constants import COLORS, FONTS
from ..models import FocusArea, ProjectType, SmartPreset
from .tooltip import add_tooltip

logger = logging.getLogger(__name__)


class SmartPresetPanel(ctk.CTkFrame):
    """
    Panel for configuring smart presets.

    Allows users to configure:
    - Project type
    - Focus areas
    - Target audience
    - Additional notes

    These settings influence how documentation is generated.
    """

    def __init__(self, master: Any, **kwargs: Any) -> None:
        """
        Initialize the smart preset panel.

        Args:
            master: Parent widget.
            **kwargs: Additional frame arguments.
        """
        super().__init__(master, **kwargs)

        self._preset = SmartPreset()
        self._focus_vars: dict[FocusArea, tk.BooleanVar] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        # Header
        self._create_header()

        # Main scrollable content
        main = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=10, pady=5)

        # Sections
        self._create_project_type_section(main)
        self._create_focus_areas_section(main)
        self._create_audience_section(main)
        self._create_notes_section(main)
        self._create_preview_section(main)

        self._update_preview()

    def _create_header(self) -> None:
        """Create the header section."""
        header = ctk.CTkFrame(self, fg_color=COLORS['bg_light'], corner_radius=8)
        header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="\U0001F3AF Configurazione Automatica",
            font=ctk.CTkFont(size=FONTS['header'], weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 2))

        ctk.CTkLabel(
            header,
            text="Non devi scrivere nessun prompt! Seleziona le opzioni e l'AI fara' il resto.",
            font=ctk.CTkFont(size=FONTS['body']),
            text_color=COLORS['text_muted'],
            wraplength=450
        ).pack(anchor="w", padx=15, pady=(0, 12))

    def _create_project_type_section(self, parent: ctk.CTkFrame) -> None:
        """Create project type selection section."""
        type_frame = ctk.CTkFrame(parent)
        type_frame.pack(fill="x", pady=8)

        # Header
        type_header = ctk.CTkFrame(type_frame, fg_color="transparent")
        type_header.pack(fill="x", padx=12, pady=(12, 5))

        ctk.CTkLabel(
            type_header,
            text="\U0001F4C1 Tipo di Progetto",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            type_header,
            text="Aiuta l'AI a capire il contesto",
            font=ctk.CTkFont(size=FONTS['body_small']),
            text_color=COLORS['text_muted']
        ).pack(side="right")

        # Radio buttons
        type_grid = ctk.CTkFrame(type_frame, fg_color="transparent")
        type_grid.pack(fill="x", padx=12, pady=(0, 12))

        self.project_type_var = tk.StringVar(value=ProjectType.GENERIC.name)

        for i, pt in enumerate(ProjectType):
            rb = ctk.CTkRadioButton(
                type_grid,
                text=f"{pt.icon} {pt.label}",
                variable=self.project_type_var,
                value=pt.name,
                font=ctk.CTkFont(size=FONTS['body']),
                command=self._on_preset_change
            )
            rb.grid(row=i // 4, column=i % 4, padx=8, pady=5, sticky="w")
            add_tooltip(rb, pt.description)

    def _create_focus_areas_section(self, parent: ctk.CTkFrame) -> None:
        """Create focus areas selection section."""
        focus_frame = ctk.CTkFrame(parent)
        focus_frame.pack(fill="x", pady=8)

        # Header
        focus_header = ctk.CTkFrame(focus_frame, fg_color="transparent")
        focus_header.pack(fill="x", padx=12, pady=(12, 5))

        ctk.CTkLabel(
            focus_header,
            text="\U0001F3AF Aree di Focus (opzionale)",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            focus_header,
            text="Seleziona per enfatizzare aspetti specifici",
            font=ctk.CTkFont(size=FONTS['body_small']),
            text_color=COLORS['text_muted']
        ).pack(side="right")

        # Checkboxes
        focus_grid = ctk.CTkFrame(focus_frame, fg_color="transparent")
        focus_grid.pack(fill="x", padx=12, pady=(0, 12))

        for i, fa in enumerate(FocusArea):
            var = tk.BooleanVar(value=False)
            self._focus_vars[fa] = var

            cb = ctk.CTkCheckBox(
                focus_grid,
                text=f"{fa.value[0]} {fa.value[1]}",
                variable=var,
                font=ctk.CTkFont(size=FONTS['body']),
                command=self._on_preset_change
            )
            cb.grid(row=i // 3, column=i % 3, padx=8, pady=5, sticky="w")
            add_tooltip(cb, fa.value[2])

    def _create_audience_section(self, parent: ctk.CTkFrame) -> None:
        """Create target audience selection section."""
        audience_frame = ctk.CTkFrame(parent)
        audience_frame.pack(fill="x", pady=8)

        aud_header = ctk.CTkFrame(audience_frame, fg_color="transparent")
        aud_header.pack(fill="x", padx=12, pady=(12, 5))

        ctk.CTkLabel(
            aud_header,
            text="\U0001F465 Chi usera' questa documentazione?",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(side="left")

        audiences = [
            "AI Agents (Claude, Copilot, Cursor, Jules)",
            "Sviluppatori Junior (team interno)",
            "Sviluppatori Senior / Architect",
            "Team DevOps / SRE",
            "Product Manager / Stakeholder"
        ]

        self.audience_combo = ctk.CTkComboBox(
            audience_frame,
            values=audiences,
            width=420,
            height=36,
            font=ctk.CTkFont(size=FONTS['body']),
            command=lambda _: self._on_preset_change()
        )
        self.audience_combo.set(audiences[0])
        self.audience_combo.pack(anchor="w", padx=12, pady=(0, 12))
        add_tooltip(
            self.audience_combo,
            "Seleziona il pubblico target per adattare il linguaggio e il livello di dettaglio"
        )

    def _create_notes_section(self, parent: ctk.CTkFrame) -> None:
        """Create additional notes section with expanded suggestions."""
        notes_frame = ctk.CTkFrame(parent)
        notes_frame.pack(fill="x", pady=8)

        notes_header = ctk.CTkFrame(notes_frame, fg_color="transparent")
        notes_header.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(
            notes_header,
            text="\U0001F4DD Istruzioni Personalizzate (opzionale)",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(side="left")

        # Suggestion examples - more readable
        suggestions_frame = ctk.CTkFrame(notes_frame, fg_color=COLORS['bg_light'], corner_radius=8)
        suggestions_frame.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            suggestions_frame,
            text="\U0001F4A1 Esempi di istruzioni utili:",
            font=ctk.CTkFont(size=FONTS['body'], weight="bold"),
            text_color=COLORS['primary']
        ).pack(anchor="w", padx=12, pady=(10, 6))

        examples = [
            "Il progetto usa SQLAlchemy come ORM, documenta le query e i modelli",
            "Enfatizza le API REST e i pattern di autenticazione JWT",
            "Ignora i file di test, concentrati sulla logica core",
            "Aggiungi esempi di codice per ogni endpoint API",
            "Documenta le variabili d'ambiente necessarie per il deploy",
        ]

        for ex in examples:
            ctk.CTkLabel(
                suggestions_frame,
                text=f"  \u2022  {ex}",
                font=ctk.CTkFont(size=FONTS['body_small']),
                text_color=COLORS['text_muted'],
                anchor="w"
            ).pack(anchor="w", padx=12, pady=2)

        ctk.CTkLabel(suggestions_frame, text="").pack(pady=4)  # Spacer

        self.notes_text = ctk.CTkTextbox(
            notes_frame,
            height=90,
            font=ctk.CTkFont(size=FONTS['body'])
        )
        self.notes_text.pack(fill="x", padx=12, pady=(0, 12))

        self._notes_placeholder = (
            "Scrivi qui istruzioni specifiche per l'AI...\n"
            "Es: Documenta in dettaglio il sistema di caching Redis usato nel progetto."
        )
        self.notes_text.insert("1.0", self._notes_placeholder)
        self.notes_text.configure(text_color=COLORS['text_muted'])
        self.notes_text.bind("<FocusIn>", self._clear_placeholder)
        self.notes_text.bind("<FocusOut>", self._restore_placeholder)

    def _create_preview_section(self, parent: ctk.CTkFrame) -> None:
        """Create configuration preview section."""
        preview_frame = ctk.CTkFrame(parent)
        preview_frame.pack(fill="x", pady=8)

        ctk.CTkLabel(
            preview_frame,
            text="\U0001F441\uFE0F Anteprima Configurazione",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(anchor="w", padx=12, pady=(12, 5))

        self.preview_text = ctk.CTkTextbox(
            preview_frame,
            height=90,
            font=ctk.CTkFont(family="Consolas", size=FONTS['small']),
            state="disabled",
            fg_color=COLORS['bg_light']
        )
        self.preview_text.pack(fill="x", padx=12, pady=(0, 12))

    def _clear_placeholder(self, event: Any = None) -> None:
        """Clear placeholder text on focus."""
        content = self.notes_text.get("1.0", "end-1c")
        if content.startswith("Scrivi qui") or content.startswith("Es:"):
            self.notes_text.delete("1.0", "end")
            self.notes_text.configure(text_color="black")

    def _restore_placeholder(self, event: Any = None) -> None:
        """Restore placeholder if notes are empty."""
        content = self.notes_text.get("1.0", "end-1c").strip()
        if not content:
            self.notes_text.insert("1.0", self._notes_placeholder)
            self.notes_text.configure(text_color=COLORS['text_muted'])

    def _on_preset_change(self) -> None:
        """Handle preset configuration changes."""
        self._update_preview()

    def _update_preview(self) -> None:
        """Update the preview text."""
        preset = self.get_preset()
        preview = preset.to_prompt_context()

        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", preview)
        self.preview_text.configure(state="disabled")

    def get_preset(self) -> SmartPreset:
        """
        Get the current preset configuration.

        Returns:
            SmartPreset with current settings.
        """
        try:
            project_type = ProjectType[self.project_type_var.get()]
        except KeyError:
            project_type = ProjectType.GENERIC

        focus_areas = [fa for fa, var in self._focus_vars.items() if var.get()]

        notes = self.notes_text.get("1.0", "end-1c").strip()
        if notes.startswith("Scrivi qui") or notes.startswith("Es:"):
            notes = ""

        return SmartPreset(
            project_type=project_type,
            focus_areas=focus_areas,
            target_audience=self.audience_combo.get(),
            additional_notes=notes
        )


class GuidePanel(ctk.CTkFrame):
    """
    Help guide panel for new users.

    Displays step-by-step instructions for using the application.
    """

    def __init__(self, master: Any, **kwargs: Any) -> None:
        """
        Initialize the guide panel.

        Args:
            master: Parent widget.
            **kwargs: Additional frame arguments.
        """
        super().__init__(master, **kwargs)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the guide UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS['primary'], corner_radius=8)
        header.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(
            header,
            text="\U0001F4DA Come Usare AI Context Studio",
            font=ctk.CTkFont(size=FONTS['title'], weight="bold"),
            text_color="white"
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            header,
            text="Segui questi 3 semplici passi per generare documentazione professionale",
            font=ctk.CTkFont(size=FONTS['body']),
            text_color="#e2e8f0"
        ).pack(pady=(0, 15))

        # Steps
        steps_frame = ctk.CTkFrame(self, fg_color="transparent")
        steps_frame.pack(fill="both", expand=True, padx=15)

        steps = [
            (
                "1\uFE0F\u20E3",
                "Configura API",
                "Vai alla tab 'Setup' e inserisci la tua Google Gemini API Key.\n"
                "Non ce l'hai? Ottienila gratis su: https://makersuite.google.com/app/apikey",
                COLORS['primary']
            ),
            (
                "2\uFE0F\u20E3",
                "Seleziona Progetto",
                "Clicca 'Sfoglia' e seleziona la cartella root del tuo progetto.\n"
                "L'app analizzera' automaticamente tutti i file di codice supportati.\n"
                "Puoi selezionare/deselezionare i file con il tasto destro del mouse.",
                COLORS['teal']
            ),
            (
                "3\uFE0F\u20E3",
                "Genera Documentazione",
                "Vai alla tab 'Generatore' e seleziona i documenti da creare.\n"
                "Puoi generare singoli documenti o tutti gli 11 tipi disponibili.\n"
                "L'app riconosce automaticamente documentazione esistente!",
                COLORS['success']
            ),
        ]

        for icon, title, desc, color in steps:
            self._create_step_card(steps_frame, icon, title, desc, color)

        # Tips
        self._create_tips_section()

    def _create_step_card(
        self,
        parent: ctk.CTkFrame,
        icon: str,
        title: str,
        desc: str,
        color: str
    ) -> None:
        """Create a step instruction card."""
        step_card = ctk.CTkFrame(parent, fg_color="white", corner_radius=8)
        step_card.pack(fill="x", pady=8)

        step_header = ctk.CTkFrame(step_card, fg_color="transparent")
        step_header.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            step_header,
            text=icon,
            font=ctk.CTkFont(size=28)
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            step_header,
            text=title,
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold"),
            text_color=color
        ).pack(side="left")

        ctk.CTkLabel(
            step_card,
            text=desc,
            font=ctk.CTkFont(size=FONTS['body']),
            text_color=COLORS['text_muted'],
            justify="left",
            wraplength=500
        ).pack(anchor="w", padx=15, pady=(0, 15))

    def _create_tips_section(self) -> None:
        """Create tips section."""
        tips_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS['bg_light'],
            corner_radius=8
        )
        tips_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(
            tips_frame,
            text="\U0001F4A1 Suggerimenti e Scorciatoie",
            font=ctk.CTkFont(size=FONTS['subheader'], weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 5))

        tips = [
            "Usa le 'Istruzioni Personalizzate' per guidare l'AI su aspetti specifici",
            "Seleziona/Deseleziona file multipli nella tabella con tasto destro",
            "L'app rileva automaticamente i file .md esistenti e li aggiorna",
            "I documenti vengono salvati nella cartella /docs del progetto",
            "Ctrl+O apri cartella, Ctrl+G genera tutti, Ctrl+S salva, F1 guida"
        ]

        for tip in tips:
            ctk.CTkLabel(
                tips_frame,
                text=f"\u2022 {tip}",
                font=ctk.CTkFont(size=FONTS['body_small']),
                text_color=COLORS['text_muted']
            ).pack(anchor="w", padx=15, pady=2)

        ctk.CTkLabel(tips_frame, text="").pack(pady=5)  # Spacer
