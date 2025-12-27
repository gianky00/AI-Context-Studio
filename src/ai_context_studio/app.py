# -*- coding: utf-8 -*-
"""
Main application window for AI Context Studio.

This module contains the main application class that orchestrates
all UI components and business logic.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import customtkinter as ctk

from .api_client import GeminiAPIClient
from .config import ConfigManager
from .constants import APP_AUTHOR, APP_NAME, APP_VERSION, COLORS
from .models import GenerationResult
from .ui.event_queue import UIEventQueue
from .ui.panels import GuidePanel
from .ui.tabs import GeneratorTab, PreviewTab, SetupTab
from .ui.tooltip import add_tooltip

logger = logging.getLogger(__name__)


class AIContextStudioApp(ctk.CTk):
    """
    Main application window.

    Orchestrates all components:
    - Configuration management
    - API client
    - Event queue for thread-safe UI updates
    - Tab-based interface
    """

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()

        logger.info("Starting %s v%s", APP_NAME, APP_VERSION)

        # Window setup
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1400x900")
        self.minsize(1200, 800)

        # Force window to front
        self.lift()
        self.attributes('-topmost', True)
        self.after(100, lambda: self.attributes('-topmost', False))
        self.focus_force()

        # Theme
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # Initialize core components
        self.config_manager = ConfigManager()
        self.api_client = GeminiAPIClient()
        self.event_queue = UIEventQueue(self)

        # Build UI
        self._setup_ui()

        # First run guide
        if self.config_manager.is_first_run():
            self.after(500, self._show_first_run_guide)

        # Cleanup on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        self._create_header()
        self._create_main_content()
        self._create_footer()

    def _create_header(self) -> None:
        """Create the application header."""
        header = ctk.CTkFrame(self, height=60, fg_color=COLORS['bg_dark'])
        header.pack(fill="x")
        header.pack_propagate(False)

        # Logo area
        logo_frame = ctk.CTkFrame(header, fg_color="transparent")
        logo_frame.pack(side="left", padx=25, pady=10)

        ctk.CTkLabel(
            logo_frame,
            text="\U0001F9E0",  # Brain emoji
            font=ctk.CTkFont(size=28)
        ).pack(side="left", padx=(0, 10))

        title_frame = ctk.CTkFrame(logo_frame, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text=APP_NAME,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white"
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="Knowledge Base Generator per AI Agents",
            font=ctk.CTkFont(size=10),
            text_color="#94a3b8"
        ).pack(anchor="w")

        # Help button
        help_btn = ctk.CTkButton(
            header,
            text="\u2753 Guida",
            width=80,
            height=30,
            fg_color="transparent",
            hover_color="#1e293b",
            text_color="#94a3b8",
            command=self._show_guide
        )
        help_btn.pack(side="right", padx=10)
        add_tooltip(help_btn, "Mostra la guida su come usare l'applicazione")

        # Version info
        ctk.CTkLabel(
            header,
            text=f"v{APP_VERSION} | {APP_AUTHOR}",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        ).pack(side="right", padx=15, pady=10)

    def _create_main_content(self) -> None:
        """Create the main content area with tabs."""
        main_container = ctk.CTkFrame(self, fg_color="#f1f5f9")
        main_container.pack(fill="both", expand=True)

        # Tab view
        self.tabview = ctk.CTkTabview(main_container, fg_color="white")
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)

        # Tab 0 - Guide
        self.tabview.add("\U0001F4DA Guida")
        self.guide_panel = GuidePanel(self.tabview.tab("\U0001F4DA Guida"))
        self.guide_panel.pack(fill="both", expand=True)

        # Tab 1 - Setup
        self.tabview.add("\u2699\uFE0F Setup")
        self.setup_tab = SetupTab(
            self.tabview.tab("\u2699\uFE0F Setup"),
            config=self.config_manager,
            event_queue=self.event_queue,
            api_client=self.api_client,
            on_status_update=self._update_status
        )
        self.setup_tab.pack(fill="both", expand=True)

        # Tab 2 - Generator
        self.tabview.add("\U0001F680 Generatore")
        self.generator_tab = GeneratorTab(
            self.tabview.tab("\U0001F680 Generatore"),
            config=self.config_manager,
            api_client=self.api_client,
            event_queue=self.event_queue,
            setup_tab=self.setup_tab,
            on_generation_complete=self._on_generation_complete,
            on_status_update=self._update_status
        )
        self.generator_tab.pack(fill="both", expand=True)

        # Tab 3 - Preview
        self.tabview.add("\U0001F4C4 Documenti")
        self.preview_tab = PreviewTab(
            self.tabview.tab("\U0001F4C4 Documenti"),
            config=self.config_manager,
            setup_tab=self.setup_tab,
            on_status_update=self._update_status
        )
        self.preview_tab.pack(fill="both", expand=True)

        # Default tab for returning users
        if not self.config_manager.is_first_run():
            self.tabview.set("\u2699\uFE0F Setup")

    def _create_footer(self) -> None:
        """Create the status bar footer."""
        footer = ctk.CTkFrame(self, height=32, fg_color="#e2e8f0")
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        # Status indicator
        self.status_icon = ctk.CTkLabel(
            footer,
            text="\u25CF",
            font=ctk.CTkFont(size=10),
            text_color=COLORS['success']
        )
        self.status_icon.pack(side="left", padx=(15, 5), pady=6)

        # Status message
        self.status_bar = ctk.CTkLabel(
            footer,
            text="\u2728 Benvenuto! Segui la guida per iniziare.",
            font=ctk.CTkFont(size=11),
            text_color="#475569"
        )
        self.status_bar.pack(side="left", pady=6)

        # Time display
        self.status_time = ctk.CTkLabel(
            footer,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#94a3b8"
        )
        self.status_time.pack(side="right", padx=15, pady=6)

    def _show_guide(self) -> None:
        """Switch to the guide tab."""
        self.tabview.set("\U0001F4DA Guida")

    def _show_first_run_guide(self) -> None:
        """Show guide on first run and mark onboarding complete."""
        self.tabview.set("\U0001F4DA Guida")
        self.config_manager.set_onboarding_completed()
        self._update_status("\U0001F44B Benvenuto! Leggi la guida per iniziare.", "info")
        logger.info("First run guide displayed")

    def _update_status(self, message: str, status_type: str = "info") -> None:
        """
        Update the status bar.

        Args:
            message: Status message to display.
            status_type: One of "success", "error", "warning", "info".
        """
        colors = {
            "success": COLORS['success'],
            "error": COLORS['danger'],
            "warning": COLORS['warning'],
            "info": COLORS['primary']
        }

        self.status_bar.configure(text=message)
        self.status_icon.configure(text_color=colors.get(status_type, COLORS['primary']))
        self.status_time.configure(text=time.strftime("%H:%M:%S"))

        logger.debug("Status: %s (%s)", message, status_type)

    def _on_generation_complete(self, result: GenerationResult) -> None:
        """
        Handle generation completion.

        Args:
            result: The generation result.
        """
        self.preview_tab.add_result(result)

        if result.success:
            logger.info(
                "Generated %s in %.1fs",
                result.doc_type.filename,
                result.generation_time
            )
        else:
            logger.warning(
                "Generation failed for %s: %s",
                result.doc_type.filename,
                result.error_message
            )

    def _on_close(self) -> None:
        """Handle window close event."""
        logger.info("Application closing")
        self.event_queue.stop()
        self.destroy()
