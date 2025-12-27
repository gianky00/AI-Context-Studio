from ..config.settings import TOKEN_FACTOR

class TokenEstimator:
    """Stima il numero di token per vari modelli Gemini."""

    MODEL_CONTEXT_WINDOWS = {
        'gemini-1.5-flash': 1_048_576,
        'gemini-1.5-pro': 2_097_152,
        'gemini-2.0-flash': 1_048_576,
        'gemini-2.5': 1_048_576,
        'gemini-1.0-pro': 32_768,
    }

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // TOKEN_FACTOR

    @classmethod
    def get_context_window(cls, model_name: str) -> int:
        clean_name = model_name.replace('models/', '').lower()
        for key, window in cls.MODEL_CONTEXT_WINDOWS.items():
            if key in clean_name:
                return window
        return 1_048_576

    @classmethod
    def calculate_usage_percentage(cls, tokens: int, model_name: str) -> float:
        window = cls.get_context_window(model_name)
        return (tokens / window) * 100
