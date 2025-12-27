import time
from typing import Optional, Callable
import google.generativeai as genai

from ..core.models import GenerationType, GenerationResult
from ..core.estimator import TokenEstimator
from ..core.prompts import PromptEngine

class GeminiAPIClient:
    """Client per interazione con Google Gemini API."""

    def __init__(self):
        self._api_key = ""
        self._configured = False
        self._available_models: list[str] = []

    def configure(self, api_key: str) -> bool:
        try:
            genai.configure(api_key=api_key)
            self._api_key = api_key
            self._configured = True
            return True
        except Exception:
            return False

    def test_connection(self) -> tuple[bool, str]:
        if not self._configured:
            return False, "API non configurata"

        try:
            models = list(genai.list_models())
            return True, f"Connessione OK. {len(models)} modelli disponibili."
        except Exception as e:
            return False, f"Errore: {str(e)}"

    def get_available_models(self) -> list[str]:
        if not self._configured:
            return []

        try:
            self._available_models = []
            for model in genai.list_models():
                if 'generateContent' in model.supported_generation_methods:
                    self._available_models.append(model.name)

            # Ordina per priorità
            priority = ['gemini-2.5', 'gemini-2.0', 'gemini-1.5-pro', 'gemini-1.5-flash']

            def sort_key(name: str) -> tuple:
                for i, prefix in enumerate(priority):
                    if prefix in name:
                        return (i, name)
                return (len(priority), name)

            self._available_models.sort(key=sort_key)
            return self._available_models

        except Exception:
            return []

    def generate_documentation(
        self,
        model_name: str,
        code_content: str,
        doc_type: GenerationType,
        custom_instructions: str = "",
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> GenerationResult:
        """Genera documentazione usando Gemini."""
        start_time = time.time()

        if progress_callback:
            progress_callback(f"Inizializzazione {model_name}...")

        try:
            model = genai.GenerativeModel(model_name)
            prompt = PromptEngine.build_prompt(doc_type, code_content, custom_instructions)

            if progress_callback:
                progress_callback("Generazione in corso (può richiedere 30-60s)...")

            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 8192,
                }
            )

            elapsed = time.time() - start_time

            return GenerationResult(
                success=True,
                doc_type=doc_type,
                content=response.text,
                filename=PromptEngine.get_filename(doc_type),
                generation_time=elapsed,
                tokens_used=TokenEstimator.estimate_tokens(response.text)
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                doc_type=doc_type,
                error_message=str(e),
                generation_time=time.time() - start_time
            )
