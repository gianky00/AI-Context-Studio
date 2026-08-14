# -*- coding: utf-8 -*-
"""
Tests for token estimation module.
"""

from __future__ import annotations


from ai_context_studio.token_estimator import (
    ContentType,
    CostCalculator,
    Currency,
    ModelRegistry,
    TokenEstimator,
)


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


class TestContextBudget:
    """Tests for context-window overflow detection."""

    def test_under_limit(self) -> None:
        exceeds, usage, window = TokenEstimator.exceeds_context_budget(
            1000, "gemini-1.5-flash"
        )
        assert exceeds is False
        assert usage < 80
        assert window == 1_048_576

    def test_at_limit(self) -> None:
        window = TokenEstimator.get_context_window("gemini-1.5-flash")
        tokens = int(window * 0.81)
        exceeds, usage, _ = TokenEstimator.exceeds_context_budget(
            tokens, "gemini-1.5-flash"
        )
        assert exceeds is True
        assert usage >= 80.0

    def test_custom_limit_percent(self) -> None:
        """Custom limit_percent should replace the default 80% threshold."""
        window = TokenEstimator.get_context_window("gemini-1.5-flash")
        tokens = int(window * 0.50)
        exceeds_default, _, _ = TokenEstimator.exceeds_context_budget(
            tokens, "gemini-1.5-flash"
        )
        exceeds_strict, usage, window_out = TokenEstimator.exceeds_context_budget(
            tokens, "gemini-1.5-flash", limit_percent=40.0
        )
        exceeds_lenient, _, _ = TokenEstimator.exceeds_context_budget(
            tokens, "gemini-1.5-flash", limit_percent=90.0
        )
        assert exceeds_default is False
        assert exceeds_strict is True
        assert exceeds_lenient is False
        assert usage >= 40.0
        assert window_out == window


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


class TestModelRegistry:
    """Tests for ModelRegistry lookup and listing (local only, no API)."""

    def test_get_model_unknown_returns_default(self) -> None:
        """Unknown names should fall back to DEFAULT_MODEL."""
        model = ModelRegistry.get_model("unknown-model-xyz")
        assert model.model_id == ModelRegistry.DEFAULT_MODEL
        assert model.model_id == "gemini-2.5-flash"

    def test_get_model_gemini_25_flash(self) -> None:
        """Stable Gemini 2.5 Flash should resolve with documented prices."""
        model = ModelRegistry.get_model("gemini-2.5-flash")
        assert model.model_id == "gemini-2.5-flash"
        assert model.input_price_per_million == 0.30
        assert model.output_price_per_million == 2.50
        assert model.context_window == 1_048_576
        assert model.is_active is True

    def test_get_model_gemini_25_pro(self) -> None:
        """Stable Gemini 2.5 Pro should resolve with documented prices."""
        model = ModelRegistry.get_model("gemini-2.5-pro")
        assert model.model_id == "gemini-2.5-pro"
        assert model.input_price_per_million == 1.25
        assert model.output_price_per_million == 10.00
        assert model.context_window == 1_048_576
        assert model.is_active is True

    def test_get_model_25_prefix_and_case(self) -> None:
        """2.5 lookups should strip models/ and ignore case."""
        flash = ModelRegistry.get_model("models/GEMINI-2.5-FLASH")
        pro = ModelRegistry.get_model("models/Gemini-2.5-Pro")
        assert flash.model_id == "gemini-2.5-flash"
        assert pro.model_id == "gemini-2.5-pro"

    def test_list_models_excludes_inactive(self) -> None:
        """Retired models stay resolvable but must not appear in list_models()."""
        listed_ids = {m.model_id for m in ModelRegistry.list_models()}
        assert "gemini-1.0-pro" not in listed_ids
        assert "gemini-2.0-flash" not in listed_ids
        assert "gemini-2.0-flash-exp" not in listed_ids
        assert "gemini-2.5-flash-preview-05-20" not in listed_ids
        assert "gemini-2.5-flash" in listed_ids
        assert "gemini-2.5-pro" in listed_ids
        assert ModelRegistry.get_model("gemini-1.0-pro").is_active is False


class TestCostCalculator:
    """Offline CostCalculator tests using local ModelRegistry only."""

    def test_calculate_from_tokens_gemini_25_flash_positive_costs(self) -> None:
        """gemini-2.5-flash should yield positive input, output, and total cost."""
        calc = CostCalculator(default_currency=Currency.USD)
        estimate = calc.calculate_from_tokens(1_000_000, "gemini-2.5-flash")
        assert estimate.model_id == "gemini-2.5-flash"
        assert estimate.input_cost > 0
        assert estimate.output_cost > 0
        assert estimate.total_cost > 0
        assert estimate.total_cost == estimate.input_cost + estimate.output_cost

    def test_calculate_from_tokens_include_output_false_zeros_output(self) -> None:
        """include_output=False should zero output tokens and output cost."""
        calc = CostCalculator(default_currency=Currency.USD)
        estimate = calc.calculate_from_tokens(
            1_000_000, "gemini-2.5-flash", include_output=False
        )
        assert estimate.output_tokens == 0
        assert estimate.output_cost == 0.0
        assert estimate.input_cost > 0
        assert estimate.total_cost == estimate.input_cost

    def test_compare_models_sorts_by_total_cost(self) -> None:
        """compare_models should return estimates ordered by total_cost ascending."""
        calc = CostCalculator(default_currency=Currency.USD)
        models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
        estimates = calc.compare_models(100_000, models=models)
        costs = [e.total_cost for e in estimates]
        assert costs == sorted(costs)
        assert estimates[0].model_id == "gemini-2.5-flash-lite"
        assert estimates[-1].model_id == "gemini-2.5-pro"


class TestDetectContentType:
    """Auto-detection of Python code vs JSON vs empty (local, no API)."""

    def test_empty_is_mixed(self) -> None:
        """Empty text has no signal and should classify as MIXED."""
        assert TokenEstimator.detect_content_type("") == ContentType.MIXED

    def test_python_code(self, sample_code_content: str) -> None:
        """Python with import/class/def should classify as CODE."""
        assert TokenEstimator.detect_content_type(sample_code_content) == ContentType.CODE

    def test_json_object(self) -> None:
        """A JSON object should classify as JSON."""
        payload = '{"name": "test", "count": 1, "ok": true}'
        assert TokenEstimator.detect_content_type(payload) == ContentType.JSON

    def test_json_array(self) -> None:
        """A JSON array should classify as JSON."""
        payload = '[{"a": 1}, {"b": 2}]'
        assert TokenEstimator.detect_content_type(payload) == ContentType.JSON


class TestEstimateOutputTokens:
    """Output-token multiplier applied by estimate_output_tokens."""

    def test_default_multiplier(self) -> None:
        """Default multiplier is 1.5."""
        assert TokenEstimator.estimate_output_tokens(100) == 150

    def test_custom_multiplier(self) -> None:
        """A custom multiplier should scale output tokens."""
        assert TokenEstimator.estimate_output_tokens(100, multiplier=2.0) == 200

    def test_truncates_toward_zero(self) -> None:
        """Fractional products are truncated with int()."""
        assert TokenEstimator.estimate_output_tokens(3, multiplier=1.5) == 4
        assert TokenEstimator.estimate_output_tokens(0) == 0
