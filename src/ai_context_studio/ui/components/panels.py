import customtkinter as ctk
from typing import Callable
from ...core.models import GenerationType

class SmartPresetPanel(ctk.CTkFrame):
    """Pannello per la selezione dei preset di generazione (azioni rapide)."""

    def __init__(self, master, on_generate: Callable[[GenerationType], None], **kwargs):
        super().__init__(master, **kwargs)
        self._on_generate = on_generate
        self._buttons = {}
        self._setup_ui()

    def _setup_ui(self):
        ctk.CTkLabel(
            self, text="🚀 Generatori",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        btn_grid = ctk.CTkFrame(self, fg_color="transparent")
        btn_grid.pack(fill="x", padx=10, pady=10)

        configs = [
            ("arch", "🏗️ Architettura", GenerationType.ARCHITECTURE, "#0066cc"),
            ("rules", "📋 Regole Coding", GenerationType.RULES, "#6c5ce7"),
            ("context", "📖 User Stories", GenerationType.CONTEXT, "#00b894"),
            ("bundle", "📦 Genera Tutto", GenerationType.BUNDLE, "#d63031"),
        ]

        for i, (key, text, gen_type, color) in enumerate(configs):
            btn = ctk.CTkButton(
                btn_grid, text=text, width=220, height=45,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=color,
                command=lambda t=gen_type: self._on_generate(t)
            )
            btn.grid(row=i // 2, column=i % 2, padx=8, pady=8)
            self._buttons[key] = btn

    def set_buttons_state(self, state: str):
        """Imposta lo stato (normal/disabled) di tutti i pulsanti."""
        for btn in self._buttons.values():
            btn.configure(state=state)


class GuidePanel(ctk.CTkFrame):
    """Pannello per istruzioni custom e guida."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._instr_expanded = False
        self._setup_ui()

    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            header, text="📝 Istruzioni Custom (opzionale)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        self.expand_btn = ctk.CTkButton(
            header, text="▼ Espandi", width=100, height=25,
            command=self._toggle_instructions
        )
        self.expand_btn.pack(side="right")

        self.instr_container = ctk.CTkFrame(self, fg_color="transparent")

        self.instr_text = ctk.CTkTextbox(self.instr_container, height=80, font=ctk.CTkFont(size=12))
        self.instr_text.pack(fill="x", padx=10, pady=10)
        self.instr_text.insert("1.0", "Es: Focalizzati sulla sicurezza...")

    def _toggle_instructions(self) -> None:
        if self._instr_expanded:
            self.instr_container.pack_forget()
            self.expand_btn.configure(text="▼ Espandi")
        else:
            self.instr_container.pack(fill="x")
            self.expand_btn.configure(text="▲ Comprimi")
        self._instr_expanded = not self._instr_expanded

    def get_instructions(self) -> str:
        """Recupera il testo delle istruzioni, pulendo il placeholder."""
        custom = self.instr_text.get("1.0", "end").strip()
        if custom.startswith("Es:"):
            return ""
        return custom
