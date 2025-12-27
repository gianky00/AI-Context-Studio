# -*- coding: utf-8 -*-
"""
Google Gemini API client for AI Context Studio.

This module provides the GeminiAPIClient class for interacting
with the Google Generative AI API with retry logic and caching.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from .config import ConfigManager
from .models import ExistingDoc, GenerationResult, GenerationType, SmartPreset
from .prompt_engine import PromptEngine
from .token_estimator import TokenEstimator

logger = logging.getLogger(__name__)

# Try to import the Google Generative AI library
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-generativeai not installed")
    genai = None

# Type alias for progress callbacks
ProgressCallback = Callable[[str, int], None]


class GeminiAPIClient:
    """
    Client for interacting with Google Gemini API.

    Provides methods for:
    - API configuration and connection testing
    - Model listing with caching
    - Document generation with retry logic

    Attributes:
        MAX_RETRIES: Maximum number of retry attempts
        RETRY_DELAY: Base delay between retries (seconds)
    """

    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2

    def __init__(self) -> None:
        """Initialize the API client."""
        self._api_key: str = ""
        self._configured: bool = False
        self._available_models: list[str] = []

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
        if not GENAI_AVAILABLE:
            logger.error("Cannot configure: google-generativeai not installed")
            return False

        try:
            genai.configure(api_key=api_key)
            self._api_key = api_key
            self._configured = True
            logger.info("API configured successfully")
            return True
        except Exception as e:
            logger.error("Failed to configure API: %s", e)
            return False

    def test_connection(self) -> tuple[bool, str, int]:
        """
        Test the API connection.

        Returns:
            Tuple of (success, message, model_count).
        """
        if not self._configured:
            return False, "API non configurata", 0

        if not GENAI_AVAILABLE:
            return False, "google-generativeai non installato", 0

        try:
            models = list(genai.list_models())
            count = len([
                m for m in models
                if 'generateContent' in m.supported_generation_methods
            ])
            logger.info("Connection test successful: %d models", count)
            return True, "Connessione riuscita", count
        except Exception as e:
            logger.error("Connection test failed: %s", e)
            return False, str(e), 0

    def get_available_models(self, force_refresh: bool = False) -> list[str]:
        """
        Get list of available generative models.

        Args:
            force_refresh: If True, bypass cache and fetch fresh list.

        Returns:
            List of model names.
        """
        config = ConfigManager()

        # Try cache first unless force refresh
        if not force_refresh:
            cached = config.get_cached_models()
            if cached:
                self._available_models = cached
                logger.debug("Returning %d cached models", len(cached))
                return cached

        if not self._configured or not GENAI_AVAILABLE:
            logger.warning("Cannot fetch models: not configured")
            return []

        try:
            self._available_models = []

            for model in genai.list_models():
                if 'generateContent' in model.supported_generation_methods:
                    self._available_models.append(model.name)

            # Sort by priority (newer models first)
            priority = ['gemini-2.5', 'gemini-2.0', 'gemini-1.5-pro', 'gemini-1.5-flash']

            def sort_key(name: str) -> tuple[int, str]:
                for i, prefix in enumerate(priority):
                    if prefix in name:
                        return (i, name)
                return (len(priority), name)

            self._available_models.sort(key=sort_key)

            # Cache the results
            config.set_cached_models(self._available_models)

            logger.info("Fetched %d models", len(self._available_models))
            return self._available_models

        except Exception as e:
            logger.error("Failed to fetch models: %s", e)
            return []

    def generate_documentation(
        self,
        model_name: str,
        code_content: str,
        doc_type: GenerationType,
        smart_preset: Optional[SmartPreset] = None,
        progress_callback: Optional[ProgressCallback] = None,
        existing_doc: Optional[ExistingDoc] = None
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

        Returns:
            GenerationResult with the generated content or error.
        """
        start_time = time.time()
        last_error = ""

        action = "Updating" if existing_doc else "Starting generation"
        logger.info(
            "%s: %s with model %s",
            action,
            doc_type.label,
            model_name
        )

        for attempt in range(self.MAX_RETRIES):
            try:
                result = self._attempt_generation(
                    model_name=model_name,
                    code_content=code_content,
                    doc_type=doc_type,
                    smart_preset=smart_preset,
                    progress_callback=progress_callback,
                    attempt=attempt,
                    existing_doc=existing_doc
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

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Generation attempt %d failed: %s",
                    attempt + 1,
                    e
                )

            # Wait before retry
            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_DELAY * (attempt + 1)
                logger.debug("Retrying in %d seconds", delay)
                time.sleep(delay)

        # All attempts failed
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
        existing_doc: Optional[ExistingDoc] = None
    ) -> GenerationResult:
        """
        Attempt a single generation.

        Args:
            model_name: Model to use.
            code_content: Source code content.
            doc_type: Type of document.
            smart_preset: Preset configuration.
            progress_callback: Progress callback.
            attempt: Current attempt number.
            existing_doc: Optional existing documentation to update.

        Returns:
            GenerationResult from this attempt.
        """
        if not GENAI_AVAILABLE:
            return GenerationResult(
                success=False,
                doc_type=doc_type,
                error_message="google-generativeai non installato"
            )

        # Update progress
        action_verb = "Aggiornamento" if existing_doc else "Generazione"
        if progress_callback:
            if attempt > 0:
                msg = f"\U0001F504 Tentativo {attempt + 1}/{self.MAX_RETRIES}..."
                progress_callback(msg, 30)
            else:
                msg = f"\U0001F680 {action_verb} {doc_type.label}..."
                progress_callback(msg, 20)

        # Build prompt with existing doc context
        prompt = PromptEngine.build_prompt(
            doc_type, code_content, smart_preset, existing_doc
        )

        if progress_callback:
            progress_callback("\u23F3 Elaborazione AI in corso...", 50)

        # Generate content
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 8192
            }
        )

        if progress_callback:
            progress_callback(f"\u2705 {doc_type.label} completato!", 100)

        return GenerationResult(
            success=True,
            doc_type=doc_type,
            content=response.text,
            tokens_used=TokenEstimator.estimate_tokens(response.text)
        )
