# -*- coding: utf-8 -*-
"""
Settings tab for AI Context Studio.

Contains prompt editor and other configuration options.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import customtkinter as ctk

from ..config import ConfigManager, normalize_appearance_mode
from ..constants import COLORS
from ..custom_prompts import get_custom_prompts_manager
from ..models import GenerationType

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str, str], None]

# Sidebar order for the prompt manager (all GenerationType members).
SETTINGS_DOC_TYPES: tuple[GenerationType, ...] = (
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
)

IDLE_EDITOR_TITLE = "Seleziona un prompt da modificare"
SYSTEM_PROMPT_TITLE = "Prompt di Sistema"
CUSTOMIZED_BADGE_LABEL = "PERSONALIZZATO"
CUSTOMIZED_INDICATOR = "*"
RESET_ALL_STATUS = "Tutti i prompt ripristinati"
EMPTY_PROMPT_STATUS = "Il prompt non puo' essere vuoto"
UNCHANGED_PROMPT_STATUS = "Nessuna modifica da salvare"


def doc_type_list_label(doc_type: GenerationType) -> str:
    """Return the sidebar list label for a generation type."""
    return doc_type.label


def customized_indicator_text(is_customized: bool) -> str:
    """Return the sidebar marker shown next to a customized prompt."""
    return CUSTOMIZED_INDICATOR if is_customized else ""


def customized_badge_text(is_customized: bool) -> str:
    """Return the editor badge label, or empty when the prompt is stock."""
    return CUSTOMIZED_BADGE_LABEL if is_customized else ""


def should_show_customized_badge(is_customized: bool) -> bool:
    """Return whether the PERSONALIZZATO badge should be packed."""
    return is_customized


def is_editor_dirty(editor_text: str, saved_text: str) -> bool:
    """Return True when the editor content differs from the last saved prompt."""
    return editor_text != saved_text


def prompt_save_error(
    content: str,
    saved_text: Optional[str] = None,
) -> Optional[str]:
    """Return a status-bar error if the editor cannot be saved, else None."""
    without_c0 = "".join(
        ch for ch in content
        if (ord(ch) >= 32 or ch in "\t\n\r") and ord(ch) != 127
    )
    if not without_c0.strip():
        return EMPTY_PROMPT_STATUS
    if saved_text is not None and not is_editor_dirty(content, saved_text):
        return UNCHANGED_PROMPT_STATUS
    return None


def editor_title_text(
    doc_type: Optional[GenerationType] = None,
    *,
    editing_system: bool = False,
) -> str:
    """Return the editor header for the current prompt selection."""
    if editing_system:
        return SYSTEM_PROMPT_TITLE
    if doc_type is not None:
        return f"Prompt: {doc_type.label}"
    return IDLE_EDITOR_TITLE


def default_preview_title(
    doc_type: Optional[GenerationType] = None,
    *,
    editing_system: bool = False,
) -> Optional[str]:
    """Return the default-preview dialog title, or None if nothing is selected."""
    if editing_system:
        return f"Default: {SYSTEM_PROMPT_TITLE}"
    if doc_type is not None:
        return f"Default: {doc_type.label}"
    return None


def char_count_label(content: str) -> str:
    """Return the character-count footer for the prompt editor."""
    return f"{len(content):,} caratteri"


def save_status_message(
    doc_type: Optional[GenerationType] = None,
    *,
    editing_system: bool = False,
) -> str:
    """Return the status-bar message after saving the current prompt."""
    if editing_system:
        return "Prompt di sistema salvato"
    if doc_type is not None:
        return f"Prompt {doc_type.label} salvato"
    return ""


def reset_status_message(
    doc_type: Optional[GenerationType] = None,
    *,
    editing_system: bool = False,
    reset_all: bool = False,
) -> str:
    """Return the status-bar message after resetting prompts."""
    if reset_all:
        return RESET_ALL_STATUS
    if editing_system:
        return "Prompt di sistema ripristinato"
    if doc_type is not None:
        return f"Prompt {doc_type.label} ripristinato"
    return ""


class SettingsTab(ctk.CTkFrame):
    """
    Settings tab with prompt editor.

    Allows users to customize prompt templates.
    """

    DOC_TYPES: tuple[GenerationType, ...] = SETTINGS_DOC_TYPES

    def __init__(
        self,
        master: Any,
        on_status_update: StatusCallback,
        config: Optional[ConfigManager] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the settings tab."""
        super().__init__(master, **kwargs)

        self._on_status_update = on_status_update
        self._config = config if config is not None else ConfigManager()
        self._prompts_manager = get_custom_prompts_manager()
        self._current_doc_type: Optional[GenerationType] = None
        self._editing_system_prompt = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the tab UI."""
        # Compact appearance row, then two-column prompt editor
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_appearance_row()
        self._create_sidebar()
        self._create_editor_panel()

    def _create_appearance_row(self) -> None:
        """Create a compact Light/Dark/System appearance control."""
        row = ctk.CTkFrame(self, fg_color="white", height=44)
        row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=(15, 0))
        row.grid_propagate(False)

        ctk.CTkLabel(
            row,
            text="Aspetto",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1e293b",
        ).pack(side="left", padx=(15, 10), pady=8)

        current = self._config.get_appearance_mode().title()
        self.appearance_selector = ctk.CTkSegmentedButton(
            row,
            values=["Light", "Dark", "System"],
            font=ctk.CTkFont(size=11),
            width=240,
        )
        self.appearance_selector.set(current)
        self.appearance_selector.configure(command=self._on_appearance_change)
        self.appearance_selector.pack(side="left", pady=8)

    def _on_appearance_change(self, value: str) -> None:
        """Persist the selected appearance mode and apply it immediately."""
        mode = normalize_appearance_mode(value)
        self._config.set_appearance_mode(mode)
        ctk.set_appearance_mode(mode)

    def _create_sidebar(self) -> None:
        """Create the prompt selector sidebar."""
        sidebar = ctk.CTkFrame(self, width=280, fg_color="#f8fafc")
        sidebar.grid(row=1, column=0, sticky="nsw", padx=(15, 10), pady=15)
        sidebar.grid_propagate(False)

        # Title
        ctk.CTkLabel(
            sidebar,
            text="Editor Prompt",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#1e293b"
        ).pack(pady=(15, 5), padx=15, anchor="w")

        ctk.CTkLabel(
            sidebar,
            text="Personalizza i template dei prompt",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        ).pack(pady=(0, 15), padx=15, anchor="w")

        # System prompt button
        system_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        system_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.system_btn = ctk.CTkButton(
            system_frame,
            text="Prompt di Sistema",
            font=ctk.CTkFont(size=12),
            fg_color=COLORS['slate'],
            hover_color="#475569",
            anchor="w",
            command=self._edit_system_prompt
        )
        self.system_btn.pack(fill="x")

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color="#e2e8f0").pack(fill="x", padx=15, pady=10)

        # Document type buttons
        ctk.CTkLabel(
            sidebar,
            text="Prompt per Documento:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1e293b"
        ).pack(pady=(5, 10), padx=15, anchor="w")

        # Scrollable frame for buttons
        scroll_frame = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color="#cbd5e1"
        )
        scroll_frame.pack(fill="both", expand=True, padx=5)

        self._doc_buttons: dict[GenerationType, ctk.CTkButton] = {}
        for doc_type in self.DOC_TYPES:
            btn_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            btn_frame.pack(fill="x", pady=2)

            # Indicator for customized prompts
            indicator = ctk.CTkLabel(
                btn_frame,
                text=customized_indicator_text(
                    self._prompts_manager.is_prompt_customized(doc_type)
                ),
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=COLORS['primary'],
                width=15
            )
            indicator.pack(side="left")

            btn = ctk.CTkButton(
                btn_frame,
                text=doc_type_list_label(doc_type),
                font=ctk.CTkFont(size=11),
                fg_color="transparent",
                hover_color="#e2e8f0",
                text_color="#1e293b",
                anchor="w",
                height=32,
                command=lambda dt=doc_type: self._edit_prompt(dt)
            )
            btn.pack(fill="x", expand=True)
            self._doc_buttons[doc_type] = (btn, indicator)

        # Reset all button
        ctk.CTkButton(
            sidebar,
            text="Ripristina Tutti",
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['danger'],
            hover_color=COLORS['danger_hover'],
            height=32,
            command=self._reset_all_prompts
        ).pack(fill="x", padx=15, pady=15)

    def _create_editor_panel(self) -> None:
        """Create the prompt editor panel."""
        editor_panel = ctk.CTkFrame(self, fg_color="white")
        editor_panel.grid(row=1, column=1, sticky="nsew", padx=(0, 15), pady=15)
        editor_panel.grid_columnconfigure(0, weight=1)
        editor_panel.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(editor_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))

        self.editor_title = ctk.CTkLabel(
            header,
            text=editor_title_text(),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1e293b"
        )
        self.editor_title.pack(side="left")

        self.customized_badge = ctk.CTkLabel(
            header,
            text=customized_badge_text(False),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            fg_color=COLORS['primary'],
            corner_radius=4
        )
        # Will be packed/unpacked based on state

        # Editor textbox
        self.editor = ctk.CTkTextbox(
            editor_panel,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
            fg_color="#f8fafc",
            border_width=1,
            border_color="#e2e8f0"
        )
        self.editor.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.editor.configure(state="disabled")

        # Button bar
        btn_bar = ctk.CTkFrame(editor_panel, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))

        self.save_btn = ctk.CTkButton(
            btn_bar,
            text="Salva Modifiche",
            font=ctk.CTkFont(size=12),
            fg_color=COLORS['success'],
            hover_color="#16a34a",
            width=140,
            command=self._save_current_prompt,
            state="disabled"
        )
        self.save_btn.pack(side="left", padx=(0, 10))

        self.reset_btn = ctk.CTkButton(
            btn_bar,
            text="Ripristina Default",
            font=ctk.CTkFont(size=12),
            fg_color=COLORS['warning'],
            hover_color="#d97706",
            width=140,
            command=self._reset_current_prompt,
            state="disabled"
        )
        self.reset_btn.pack(side="left", padx=(0, 10))

        self.preview_btn = ctk.CTkButton(
            btn_bar,
            text="Anteprima Default",
            font=ctk.CTkFont(size=12),
            fg_color=COLORS['slate'],
            hover_color="#475569",
            width=140,
            command=self._show_default_prompt,
            state="disabled"
        )
        self.preview_btn.pack(side="left")

        # Character count
        self.char_count = ctk.CTkLabel(
            btn_bar,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_muted']
        )
        self.char_count.pack(side="right")

    def _edit_system_prompt(self) -> None:
        """Edit the system prompt."""
        self._editing_system_prompt = True
        self._current_doc_type = None

        # Update sidebar selection
        self.system_btn.configure(fg_color=COLORS['primary'])
        for btn, _ in self._doc_buttons.values():
            btn.configure(fg_color="transparent")

        # Update editor
        self.editor_title.configure(text=editor_title_text(editing_system=True))
        prompt = self._prompts_manager.get_system_prompt()

        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", prompt)

        # Enable buttons
        self.save_btn.configure(state="normal")
        self.reset_btn.configure(state="normal")
        self.preview_btn.configure(state="normal")

        self._sync_customized_badge(
            self._prompts_manager.is_system_prompt_customized()
        )

        self._update_char_count()
        self.editor.bind("<KeyRelease>", lambda e: self._update_char_count())

    def _edit_prompt(self, doc_type: GenerationType) -> None:
        """Edit a specific document prompt."""
        self._editing_system_prompt = False
        self._current_doc_type = doc_type

        # Update sidebar selection
        self.system_btn.configure(fg_color=COLORS['slate'])
        for dt, (btn, _) in self._doc_buttons.items():
            if dt == doc_type:
                btn.configure(fg_color=COLORS['primary'], text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color="#1e293b")

        # Update editor
        self.editor_title.configure(text=editor_title_text(doc_type))
        prompt = self._prompts_manager.get_prompt(doc_type)

        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", prompt)

        # Enable buttons
        self.save_btn.configure(state="normal")
        self.reset_btn.configure(state="normal")
        self.preview_btn.configure(state="normal")

        self._sync_customized_badge(
            self._prompts_manager.is_prompt_customized(doc_type)
        )

        self._update_char_count()
        self.editor.bind("<KeyRelease>", lambda e: self._update_char_count())

    def _save_current_prompt(self) -> None:
        """Save the current prompt."""
        content = self.editor.get("1.0", "end-1c")

        if self._editing_system_prompt:
            saved = self._prompts_manager.get_system_prompt()
        elif self._current_doc_type:
            saved = self._prompts_manager.get_prompt(self._current_doc_type)
        else:
            return

        error = prompt_save_error(content, saved)
        if error:
            self._on_status_update(error, "warning")
            return

        if self._editing_system_prompt:
            self._prompts_manager.set_system_prompt(content)
            self._on_status_update(
                save_status_message(editing_system=True), "success"
            )
            self._sync_customized_badge(
                self._prompts_manager.is_system_prompt_customized()
            )
        elif self._current_doc_type:
            self._prompts_manager.set_prompt(self._current_doc_type, content)
            self._on_status_update(
                save_status_message(self._current_doc_type), "success"
            )

            customized = self._prompts_manager.is_prompt_customized(
                self._current_doc_type
            )
            _, indicator = self._doc_buttons[self._current_doc_type]
            indicator.configure(text=customized_indicator_text(customized))
            self._sync_customized_badge(customized)

    def _reset_current_prompt(self) -> None:
        """Reset current prompt to default."""
        if self._editing_system_prompt:
            self._prompts_manager.reset_system_prompt()
            self._edit_system_prompt()  # Reload
            self._on_status_update(
                reset_status_message(editing_system=True), "success"
            )
        elif self._current_doc_type:
            self._prompts_manager.reset_prompt(self._current_doc_type)
            self._edit_prompt(self._current_doc_type)  # Reload

            _, indicator = self._doc_buttons[self._current_doc_type]
            indicator.configure(text=customized_indicator_text(False))

            self._on_status_update(
                reset_status_message(self._current_doc_type), "success"
            )

    def _show_default_prompt(self) -> None:
        """Show the default prompt in a dialog."""
        if self._editing_system_prompt:
            default = self._prompts_manager.get_default_system_prompt()
        elif self._current_doc_type:
            default = self._prompts_manager.get_default_prompt(self._current_doc_type)
        else:
            return

        title = default_preview_title(
            self._current_doc_type,
            editing_system=self._editing_system_prompt,
        )
        if title is None:
            return

        self._show_prompt_dialog(title, default)

    def _show_prompt_dialog(self, title: str, content: str) -> None:
        """Show a dialog with prompt content."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("800x600")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 800) // 2
        y = (dialog.winfo_screenheight() - 600) // 2
        dialog.geometry(f"800x600+{x}+{y}")

        ctk.CTkLabel(
            dialog,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(15, 10))

        textbox = ctk.CTkTextbox(
            dialog,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word"
        )
        textbox.pack(fill="both", expand=True, padx=20, pady=10)
        textbox.insert("1.0", content)
        textbox.configure(state="disabled")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 15))

        def copy_to_editor():
            self.editor.configure(state="normal")
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", content)
            self._update_char_count()
            dialog.destroy()
            self._on_status_update("Default copiato nell'editor", "info")

        ctk.CTkButton(
            btn_frame,
            text="Copia nell'Editor",
            command=copy_to_editor,
            width=140
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Chiudi",
            fg_color=COLORS['slate'],
            command=dialog.destroy,
            width=100
        ).pack(side="left", padx=5)

    def _reset_all_prompts(self) -> None:
        """Reset all prompts to defaults."""
        from tkinter import messagebox

        if messagebox.askyesno(
            "Conferma Reset",
            "Vuoi ripristinare TUTTI i prompt ai valori di default?\n\nQuesta azione non puo' essere annullata."
        ):
            self._prompts_manager.reset_all()

            # Update all indicators
            for _, indicator in self._doc_buttons.values():
                indicator.configure(text=customized_indicator_text(False))

            # Clear editor
            self.editor.configure(state="normal")
            self.editor.delete("1.0", "end")
            self.editor.configure(state="disabled")
            self.editor_title.configure(text=editor_title_text())
            self._sync_customized_badge(False)

            self._editing_system_prompt = False
            self._current_doc_type = None

            self._on_status_update(reset_status_message(reset_all=True), "success")

    def _sync_customized_badge(self, is_customized: bool) -> None:
        """Pack or hide the PERSONALIZZATO badge without changing layout."""
        self.customized_badge.configure(text=customized_badge_text(is_customized))
        if should_show_customized_badge(is_customized):
            self.customized_badge.pack(side="left", padx=10)
        else:
            self.customized_badge.pack_forget()

    def _update_char_count(self) -> None:
        """Update the character count display."""
        content = self.editor.get("1.0", "end-1c")
        self.char_count.configure(text=char_count_label(content))
