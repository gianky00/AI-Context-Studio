# -*- coding: utf-8 -*-
"""
Google Gemini API client for AI Context Studio.

This module provides the GeminiAPIClient class for interacting
with the Google Gen AI SDK with retry logic and caching.
"""

from __future__ import annotations

import logging
import threading
import time
from types import SimpleNamespace
from typing import Any, Callable, Optional

from .config import ConfigManager
from .models import ExistingDoc, GenerationResult, GenerationType, SmartPreset
from .prompt_engine import PromptEngine
from .token_estimator import TokenEstimator

try:
    from .secret_redaction import redact_secrets as _redact
except ImportError:
    import re as _re

    def _redact(text: str) -> str:
        """Last-resort AIza / api_key= redaction if secret_redaction is missing."""
        redacted = _re.sub(
            r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;\"']+)",
            r"\1[REDACTED]",
            text,
        )
        return _re.sub(r"AIza[0-9A-Za-z_\-]{10,}", "[REDACTED]", redacted)

logger = logging.getLogger(__name__)

_GENAI_CHECKED = False
GENAI_AVAILABLE = False
genai = None
genai_types = None

def _ensure_genai() -> bool:
    global _GENAI_CHECKED, GENAI_AVAILABLE, genai, genai_types
    if _GENAI_CHECKED:
        return GENAI_AVAILABLE
    
    _GENAI_CHECKED = True
    try:
        from google import genai as _genai
        from google.genai import types as _genai_types
        genai = _genai
        genai_types = _genai_types
        GENAI_AVAILABLE = True
    except ImportError:
        GENAI_AVAILABLE = False
        logger.warning("google-genai not installed")
        genai = None
        genai_types = None
        
    return GENAI_AVAILABLE

ProgressCallback = Callable[[str, int], None]

EXCLUDED_MODEL_PATTERNS = ("computer-use", "imagen", "embedding", "aqa")
MODEL_PRIORITY = (
    "gemini-2.5",
    "gemini-2.0",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
)


def extract_generated_text(response: Any, doc_type: GenerationType) -> GenerationResult:
    """
    Parse a generate_content response into a GenerationResult.

    Handles blocked prompts, empty candidates, safety/policy finish
    reasons (including recitation), and missing/empty text without raising.
    """
    prompt_feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(prompt_feedback, "block_reason", None) if prompt_feedback else None
    if block_reason:
        return GenerationResult(
            success=False,
            doc_type=doc_type,
            error_message=f"Risposta bloccata dai filtri di sicurezza ({block_reason}).",
            retryable=False,
        )

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return GenerationResult(
            success=False,
            doc_type=doc_type,
            error_message="Nessun contenuto generato (candidati vuoti).",
            retryable=False,
        )

    finish_reason = getattr(candidates[0], "finish_reason", None)
    finish_str = str(finish_reason).upper() if finish_reason is not None else ""

    if "SAFETY" in finish_str:
        return GenerationResult(
            success=False,
            doc_type=doc_type,
            error_message="Generazione interrotta dai filtri di sicurezza.",
            retryable=False,
        )

    if any(
        reason in finish_str
        for reason in ("RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII")
    ):
        return GenerationResult(
            success=False,
            doc_type=doc_type,
            error_message="Generazione bloccata per recitazione o policy/copyright.",
            retryable=False,
        )

    try:
        text = response.text
    except (ValueError, AttributeError, TypeError) as e:
        return GenerationResult(
            success=False,
            doc_type=doc_type,
            error_message=f"Impossibile leggere il testo della risposta: {_redact(str(e))}",
            retryable=False,
        )

    if text is None or not str(text).strip():
        if "MAX_TOKENS" in finish_str or "LENGTH" in finish_str:
            return GenerationResult(
                success=False,
                doc_type=doc_type,
                error_message="Risposta troncata: limite di token raggiunto.",
                retryable=True,
            )
        return GenerationResult(
            success=False,
            doc_type=doc_type,
            error_message="La risposta del modello è vuota.",
            retryable=False,
        )

    return GenerationResult(
        success=True,
        doc_type=doc_type,
        content=str(text),
        tokens_used=TokenEstimator.estimate_tokens(str(text)),
    )


def _model_sort_key(name: str) -> tuple[int, str]:
    lowered = name.lower()
    for i, prefix in enumerate(MODEL_PRIORITY):
        if prefix in lowered:
            return (i, name)
    return (len(MODEL_PRIORITY), name)


def _safe_listed_model_name(name: str) -> Optional[str]:
    """Return a stripped model name, or None if empty or it contains C0/DEL."""
    stripped = name.strip()
    if not stripped or any(ord(c) < 32 or ord(c) == 127 for c in stripped):
        return None
    return stripped


def _is_text_generation_model(model: Any) -> bool:
    name = str(getattr(model, "name", "") or "").lower()
    if any(pattern in name for pattern in EXCLUDED_MODEL_PATTERNS):
        return False

    actions = getattr(model, "supported_actions", None) or getattr(
        model, "supported_generation_methods", None
    )
    if actions:
        normalized = {str(a) for a in actions}
        if "generateContent" not in normalized and "generate_content" not in normalized:
            return False
    elif "gemini" not in name:
        return False

    return True


class GeminiAPIClient:
    """
    Client for interacting with Google Gemini API.

    Provides methods for:
    - API configuration and connection testing
    - Model listing with caching
    - Document generation with retry logic
    """

    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2

    def __init__(self) -> None:
        """Initialize the API client."""
        self._api_key: str = ""
        self._configured: bool = False
        self._available_models: list[str] = []
        self._client: Any = None
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Request cooperative cancellation of an in-flight generation."""
        self._cancel_event.set()
        logger.debug("Generation cancellation requested")

    def clear_cancel(self) -> None:
        """Clear a previous cancellation so a new generation can start."""
        self._cancel_event.clear()

    def _cancelled_result(self, doc_type: GenerationType) -> Optional[GenerationResult]:
        """Return a non-retryable failure if cancellation was requested."""
        if not self._cancel_event.is_set():
            return None
        logger.info("Generation cancelled before API call: %s", doc_type.label)
        return GenerationResult(
            success=False,
            doc_type=doc_type,
            error_message="cancelled",
            retryable=False,
        )

    @property
    def is_configured(self) -> bool:
        """Check if the API client is configured."""
        return self._configured

    def configure(self, api_key: str) -> bool:
        """
        Configure the API client with an API key.

        Args:
            api_key: Google Gemini API key.

        Returns:
            True if configuration succeeded, False otherwise.
        """
        if not _ensure_genai():
            logger.error("Cannot configure: google-genai not installed")
            return False

        if (
            not isinstance(api_key, str)
            or not api_key.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in api_key)
        ):
            self._client = None
            self._configured = False
            return False

        try:
            self._client = genai.Client(api_key=api_key)
            self._api_key = api_key
            self._configured = True
            logger.info("API configured successfully")
            return True
        except Exception as e:
            logger.error("Failed to configure API: %s", _redact(str(e)))
            self._client = None
            self._configured = False
            return False

    def test_connection(self) -> tuple[bool, str, int]:
        """
        Test the API connection.

        Returns:
            Tuple of (success, message, model_count).
        """
        if not self._configured or self._client is None:
            return False, "API non configurata", 0

        if not _ensure_genai():
            return False, "google-genai non installato", 0

        try:
            models = list(self._client.models.list())
            count = len([m for m in models if _is_text_generation_model(m)])
            logger.info("Connection test successful: %d models", count)
            return True, "Connessione riuscita", count
        except Exception as e:
            safe_error = _redact(str(e))
            logger.error("Connection test failed: %s", safe_error)
            return False, safe_error, 0

    def get_available_models(self, force_refresh: bool = False) -> list[str]:
        """
        Get list of available generative models.

        Args:
            force_refresh: If True, bypass cache and fetch fresh list.

        Returns:
            List of model names.
        """
        config = ConfigManager()

        if not force_refresh:
            cached = config.get_cached_models()
            if isinstance(cached, list):
                cached_names: list[str] = []
                for item in cached:
                    if not isinstance(item, str):
                        continue
                    name = _safe_listed_model_name(item)
                    if name is None:
                        continue
                    if _is_text_generation_model(SimpleNamespace(name=name)):
                        cached_names.append(name)
                if cached_names:
                    self._available_models = cached_names
                    logger.debug("Returning %d cached models", len(cached_names))
                    return cached_names

        if not self._configured or not _ensure_genai() or self._client is None:
            logger.warning("Cannot fetch models: not configured")
            return []

        try:
            names: list[str] = []
            for model in self._client.models.list():
                if not _is_text_generation_model(model):
                    continue
                name = _safe_listed_model_name(str(getattr(model, "name", "") or ""))
                if name is None:
                    continue
                names.append(name)

            names.sort(key=_model_sort_key)
            self._available_models = names
            config.set_cached_models(names)
            logger.info("Fetched %d models", len(names))
            return names
        except Exception as e:
            logger.error("Failed to fetch models: %s", _redact(str(e)))
            return []

    def generate_documentation(
        self,
        model_name: str,
        code_content: str,
        doc_type: GenerationType,
        smart_preset: Optional[SmartPreset] = None,
        progress_callback: Optional[ProgressCallback] = None,
        existing_doc: Optional[ExistingDoc] = None,
        prior_outputs: Optional[list[tuple[str, str]]] = None,
    ) -> GenerationResult:
        """
        Generate documentation using the AI model.

        Args:
            model_name: Name of the model to use.
            code_content: Source code to analyze.
            doc_type: Type of documentation to generate.
            smart_preset: Optional preset configuration.
            progress_callback: Optional callback for progress updates.
            existing_doc: Optional existing documentation to update.
            prior_outputs: Optional (filename, content) pairs already generated
                in the current bundle, forwarded to PromptEngine.build_prompt.

        Returns:
            GenerationResult with the generated content or error.
        """
        start_time = time.time()
        last_error = ""

        if (
            not isinstance(model_name, str)
            or not model_name.strip()
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in model_name)
        ):
            return GenerationResult(
                success=False,
                doc_type=doc_type,
                error_message="Nome del modello non valido o vuoto.",
                retryable=False,
                generation_time=time.time() - start_time,
            )

        if (
            not isinstance(code_content, str)
            or not code_content.strip()
            or not "".join(
                ch
                for ch in code_content
                if ch in "\t\n\r" or not (ord(ch) < 32 or ord(ch) == 127)
            ).strip()
        ):
            return GenerationResult(
                success=False,
                doc_type=doc_type,
                error_message="Contenuto del codice non valido o vuoto.",
                retryable=False,
                generation_time=time.time() - start_time,
            )

        action = "Updating" if existing_doc else "Starting generation"
        logger.info("%s: %s with model %s", action, doc_type.label, model_name)

        for attempt in range(self.MAX_RETRIES):
            cancelled = self._cancelled_result(doc_type)
            if cancelled is not None:
                cancelled.generation_time = time.time() - start_time
                cancelled.retries = attempt
                return cancelled

            try:
                result = self._attempt_generation(
                    model_name=model_name,
                    code_content=code_content,
                    doc_type=doc_type,
                    smart_preset=smart_preset,
                    progress_callback=progress_callback,
                    attempt=attempt,
                    existing_doc=existing_doc,
                    prior_outputs=prior_outputs,
                )

                if result.success:
                    elapsed = time.time() - start_time
                    result.generation_time = elapsed
                    result.retries = attempt
                    logger.info(
                        "Generation complete: %s in %.1fs",
                        doc_type.label,
                        elapsed
                    )
                    return result

                last_error = result.error_message
                if not result.retryable:
                    result.generation_time = time.time() - start_time
                    result.retries = attempt
                    return result

            except Exception as e:
                last_error = _redact(str(e))
                logger.warning(
                    "Generation attempt %d failed: %s",
                    attempt + 1,
                    last_error,
                )

            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_DELAY * (attempt + 1)
                logger.debug("Retrying in %d seconds", delay)
                if delay > 0:
                    if self._cancel_event.wait(timeout=delay):
                        cancelled = self._cancelled_result(doc_type)
                        if cancelled is not None:
                            cancelled.generation_time = time.time() - start_time
                            cancelled.retries = attempt
                            return cancelled

        logger.error("Generation failed after %d attempts", self.MAX_RETRIES)
        return GenerationResult(
            success=False,
            doc_type=doc_type,
            error_message=last_error,
            generation_time=time.time() - start_time,
            retries=self.MAX_RETRIES
        )

    def _attempt_generation(
        self,
        model_name: str,
        code_content: str,
        doc_type: GenerationType,
        smart_preset: Optional[SmartPreset],
        progress_callback: Optional[ProgressCallback],
        attempt: int,
        existing_doc: Optional[ExistingDoc] = None,
        prior_outputs: Optional[list[tuple[str, str]]] = None,
    ) -> GenerationResult:
        """Attempt a single generation."""
        if not _ensure_genai() or self._client is None:
            return GenerationResult(
                success=False,
                doc_type=doc_type,
                error_message="google-genai non installato o API non configurata",
                retryable=False,
            )

        action_verb = "Aggiornamento" if existing_doc else "Generazione"
        if progress_callback:
            if attempt > 0:
                progress_callback(
                    f"\U0001F504 Tentativo {attempt + 1}/{self.MAX_RETRIES}...",
                    30,
                )
            else:
                progress_callback(
                    f"\U0001F680 {action_verb} {doc_type.label}...",
                    20,
                )

        prompt = PromptEngine.build_prompt(
            doc_type,
            code_content,
            smart_preset,
            existing_doc,
            prior_outputs=prior_outputs,
        )

        if progress_callback:
            progress_callback("\u23F3 Elaborazione AI in corso...", 50)

        cancelled = self._cancelled_result(doc_type)
        if cancelled is not None:
            return cancelled

        generate_kwargs: dict[str, Any] = {
            "model": model_name,
            "contents": prompt,
        }
        if genai_types is not None:
            generate_kwargs["config"] = genai_types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=8192,
            )

        response = self._client.models.generate_content(**generate_kwargs)
        result = extract_generated_text(response, doc_type)

        if result.success and progress_callback:
            progress_callback(f"\u2705 {doc_type.label} completato!", 100)

        return result
