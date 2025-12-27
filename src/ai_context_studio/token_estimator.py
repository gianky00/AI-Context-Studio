# -*- coding: utf-8 -*-
"""
Token estimation utilities for AI Context Studio.

This module provides utilities for estimating token counts
and managing AI model context windows.
"""

from __future__ import annotations

import logging

from .constants import TOKEN_FACTOR

logger = logging.getLogger(__name__)


class TokenEstimator:
    """
    Utility class for token estimation and context window management.

    Provides static and class methods for:
    - Estimating token counts from text
    - Looking up model context windows
    - Calculating usage percentages
    """

    # Known context window sizes for Gemini models
    MODEL_CONTEXT_WINDOWS: dict[str, int] = {
        'gemini-1.5-flash': 1_048_576,
        'gemini-1.5-pro': 2_097_152,
        'gemini-2.0-flash': 1_048_576,
        'gemini-2.5': 1_048_576,
        'gemini-1.0-pro': 32_768,
    }

    # Default context window for unknown models
    DEFAULT_CONTEXT_WINDOW: int = 1_048_576

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate the number of tokens in text.

        Uses a simple character-based estimation. For more accurate
        results, a tokenizer specific to the model should be used.

        Args:
            text: Text to estimate tokens for.

        Returns:
            Estimated token count.
        """
        return len(text) // TOKEN_FACTOR

    @classmethod
    def get_context_window(cls, model_name: str) -> int:
        """
        Get the context window size for a model.

        Args:
            model_name: Full or partial model name (e.g., "models/gemini-1.5-pro").

        Returns:
            Context window size in tokens.
        """
        clean_name = model_name.replace('models/', '').lower()

        for key, window in cls.MODEL_CONTEXT_WINDOWS.items():
            if key in clean_name:
                logger.debug(
                    "Context window for %s: %d tokens",
                    model_name,
                    window
                )
                return window

        logger.debug(
            "Unknown model %s, using default context window",
            model_name
        )
        return cls.DEFAULT_CONTEXT_WINDOW

    @classmethod
    def calculate_usage_percentage(cls, tokens: int, model_name: str) -> float:
        """
        Calculate what percentage of the context window is used.

        Args:
            tokens: Number of tokens to check.
            model_name: Model to check against.

        Returns:
            Usage percentage (0-100+).
        """
        window = cls.get_context_window(model_name)
        percentage = (tokens / window) * 100

        logger.debug(
            "Token usage: %d / %d = %.1f%%",
            tokens,
            window,
            percentage
        )

        return percentage

    @classmethod
    def format_token_count(cls, tokens: int) -> str:
        """
        Format a token count for display.

        Args:
            tokens: Token count to format.

        Returns:
            Formatted string (e.g., "1,234" or "1.2M").
        """
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        elif tokens >= 1_000:
            return f"{tokens:,}"
        else:
            return str(tokens)
