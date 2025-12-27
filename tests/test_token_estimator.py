# -*- coding: utf-8 -*-
"""
Tests for token estimation module.
"""

from __future__ import annotations

import pytest

from ai_context_studio.token_estimator import TokenEstimator


class TestTokenEstimation:
    """Tests for token estimation functionality."""

    def test_estimate_tokens_empty(self) -> None:
        """Empty string should have zero tokens."""
        assert TokenEstimator.estimate_tokens("") == 0

    def test_estimate_tokens_short(self) -> None:
        """Short strings should have few tokens."""
        # With TOKEN_FACTOR of 4, 8 chars = 2 tokens
        assert TokenEstimator.estimate_tokens("12345678") == 2

    def test_estimate_tokens_long(self) -> None:
        """Longer strings should have proportionally more tokens."""
        text = "a" * 1000
        tokens = TokenEstimator.estimate_tokens(text)
        # With TOKEN_FACTOR of 4, 1000 chars = 250 tokens
        assert tokens == 250

    def test_estimate_tokens_real_code(self, sample_code_content: str) -> None:
        """Should estimate tokens for real code."""
        tokens = TokenEstimator.estimate_tokens(sample_code_content)
        assert tokens > 0
        assert tokens < len(sample_code_content)  # Less than char count


class TestContextWindow:
    """Tests for context window functionality."""

    def test_get_context_window_gemini_15_pro(self) -> None:
        """Should return correct window for Gemini 1.5 Pro."""
        window = TokenEstimator.get_context_window("gemini-1.5-pro")
        assert window == 2_097_152

    def test_get_context_window_gemini_15_flash(self) -> None:
        """Should return correct window for Gemini 1.5 Flash."""
        window = TokenEstimator.get_context_window("gemini-1.5-flash")
        assert window == 1_048_576

    def test_get_context_window_with_prefix(self) -> None:
        """Should handle models/ prefix."""
        window = TokenEstimator.get_context_window("models/gemini-1.5-pro")
        assert window == 2_097_152

    def test_get_context_window_unknown(self) -> None:
        """Should return default for unknown models."""
        window = TokenEstimator.get_context_window("unknown-model-xyz")
        assert window == TokenEstimator.DEFAULT_CONTEXT_WINDOW

    def test_get_context_window_case_insensitive(self) -> None:
        """Should be case insensitive."""
        window1 = TokenEstimator.get_context_window("GEMINI-1.5-PRO")
        window2 = TokenEstimator.get_context_window("gemini-1.5-pro")
        assert window1 == window2


class TestUsagePercentage:
    """Tests for usage percentage calculation."""

    def test_calculate_usage_zero_tokens(self) -> None:
        """Zero tokens should be 0% usage."""
        usage = TokenEstimator.calculate_usage_percentage(0, "gemini-1.5-pro")
        assert usage == 0.0

    def test_calculate_usage_half_window(self) -> None:
        """Half the context window should be ~50%."""
        # Gemini 1.5 Pro has 2M tokens
        window = 2_097_152
        usage = TokenEstimator.calculate_usage_percentage(
            window // 2,
            "gemini-1.5-pro"
        )
        assert 49.9 < usage < 50.1

    def test_calculate_usage_full_window(self) -> None:
        """Full context window should be 100%."""
        window = TokenEstimator.get_context_window("gemini-1.5-flash")
        usage = TokenEstimator.calculate_usage_percentage(window, "gemini-1.5-flash")
        assert usage == 100.0

    def test_calculate_usage_over_window(self) -> None:
        """Over context window should be >100%."""
        window = TokenEstimator.get_context_window("gemini-1.5-flash")
        usage = TokenEstimator.calculate_usage_percentage(
            window * 2,
            "gemini-1.5-flash"
        )
        assert usage == 200.0


class TestFormatTokenCount:
    """Tests for token count formatting."""

    def test_format_small_number(self) -> None:
        """Small numbers should remain as-is."""
        assert TokenEstimator.format_token_count(42) == "42"
        assert TokenEstimator.format_token_count(999) == "999"

    def test_format_thousands(self) -> None:
        """Thousands should be comma-separated."""
        assert TokenEstimator.format_token_count(1000) == "1,000"
        assert TokenEstimator.format_token_count(10000) == "10,000"
        assert TokenEstimator.format_token_count(999999) == "999,999"

    def test_format_millions(self) -> None:
        """Millions should use M suffix."""
        assert TokenEstimator.format_token_count(1000000) == "1.0M"
        assert TokenEstimator.format_token_count(2500000) == "2.5M"
