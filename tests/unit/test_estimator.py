import pytest
from ai_context_studio.core.estimator import TokenEstimator
from ai_context_studio.config.settings import TOKEN_FACTOR

class TestTokenEstimator:
    def test_estimate_tokens(self):
        text = "Hello World"
        # TOKEN_FACTOR is 4
        expected = len(text) // TOKEN_FACTOR
        assert TokenEstimator.estimate_tokens(text) == expected

    def test_get_context_window(self):
        assert TokenEstimator.get_context_window('gemini-1.5-pro') == 2_097_152
        assert TokenEstimator.get_context_window('gemini-1.0-pro') == 32_768
        # Test unknown model returns default
        assert TokenEstimator.get_context_window('unknown-model') == 1_048_576

    def test_calculate_usage_percentage(self):
        # 10% of 1_048_576 is 104,857.6
        tokens = 104_858
        percentage = TokenEstimator.calculate_usage_percentage(tokens, 'gemini-1.5-flash')
        assert abs(percentage - 10.0) < 0.001
