import customtkinter as ctk

from ..config import ConfigManager
from ..config.settings import APP_NAME, APP_VERSION, APP_AUTHOR
from ..services.gemini_client import GeminiAPIClient
from ..core.models import GenerationResult
from .utils import UIEventQueue
from .tabs.setup_tab import SetupTab
from .tabs.generator_tab import GeneratorTab
from .tabs.preview_tab import PreviewTab

class AIContextStudioApp(ctk.CTk):
    """Applicazione principale AI Context Studio."""

    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1050x800")
        self.minsize(900, 700)

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.config_manager = ConfigManager()
        self.api_client = GeminiAPIClient()
        self.event_queue = UIEventQueue(self)

        self._setup_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self) -> None:
        # Header
        header = ctk.CTkFrame(self, height=55, fg_color="#1a1a2e")
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text=f"🧠 {APP_NAME}",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="white"
        ).pack(side="left", padx=20, pady=12)

        ctk.CTkLabel(
            header, text=f"v{APP_VERSION} | {APP_AUTHOR}",
            font=ctk.CTkFont(size=11), text_color="#888"
        ).pack(side="right", padx=20, pady=12)

        # Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1
        self.tabview.add("⚙️ Configurazione")
        self.config_tab = SetupTab(
            self.tabview.tab("⚙️ Configurazione"),
            config=self.config_manager,
            event_queue=self.event_queue
        )
        self.config_tab.pack(fill="both", expand=True)

        # Tab 2
        self.tabview.add("🤖 AI Generator")
        self.generator_tab = GeneratorTab(
            self.tabview.tab("🤖 AI Generator"),
            config=self.config_manager,
            api_client=self.api_client,
            event_queue=self.event_queue,
            get_scan_result=self.config_tab.get_scan_result,
            get_included_files=self.config_tab.get_included_files,
            get_api_key=self.config_tab.get_api_key,
            read_file_contents=self.config_tab.read_file_contents,
            on_generation_complete=self._on_generation_complete
        )
        self.generator_tab.pack(fill="both", expand=True)

        # Tab 3
        self.tabview.add("📝 Preview & Editor")
        self.preview_tab = PreviewTab(
            self.tabview.tab("📝 Preview & Editor"),
            config=self.config_manager,
            get_scan_result=self.config_tab.get_scan_result
        )
        self.preview_tab.pack(fill="both", expand=True)

        # Footer
        footer = ctk.CTkFrame(self, height=28, fg_color="#f0f0f0")
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.status_bar = ctk.CTkLabel(
            footer, text="Pronto.", font=ctk.CTkFont(size=10), text_color="#666"
        )
        self.status_bar.pack(side="left", padx=15, pady=4)

    def _on_generation_complete(self, result: GenerationResult) -> None:
        self.preview_tab.add_result(result)
        if result.success:
            self.status_bar.configure(text=f"✅ Generato: {result.filename}")
            self.tabview.set("📝 Preview & Editor")

    def _on_close(self) -> None:
        self.event_queue.stop()
        self.destroy()
