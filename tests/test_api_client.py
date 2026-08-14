# -*- coding: utf-8 -*-
"""Tests for GeminiAPIClient and response parsing."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from ai_context_studio.api_client import (
    GeminiAPIClient,
    _is_text_generation_model,
    extract_generated_text,
)
from ai_context_studio.models import GenerationType


class _RaisingTextResponse:
    def __init__(self) -> None:
        self.candidates = [SimpleNamespace(finish_reason=None)]
        self.prompt_feedback = None

    @property
    def text(self) -> str:
        raise ValueError("no parts")


def _response(
    text: Any = "Generated docs",
    candidates: Any = None,
    block_reason: Any = None,
    finish_reason: Any = None,
) -> SimpleNamespace:
    if candidates is None:
        candidates = [SimpleNamespace(finish_reason=finish_reason)]

    ns = SimpleNamespace(
        candidates=candidates,
        prompt_feedback=SimpleNamespace(block_reason=block_reason) if block_reason else None,
        text=text,
    )
    return ns


class TestExtractGeneratedText:
    """Tests for safe Gemini response parsing."""

    def test_success(self) -> None:
        result = extract_generated_text(_response("Hello world"), GenerationType.ARCHITECTURE)
        assert result.success is True
        assert result.content == "Hello world"
        assert result.tokens_used > 0
        assert result.retryable is True

    def test_blocked_prompt(self) -> None:
        result = extract_generated_text(
            _response(block_reason="SAFETY"),
            GenerationType.SECURITY,
        )
        assert result.success is False
        assert result.retryable is False
        assert "filtri di sicurezza" in result.error_message

    def test_empty_candidates(self) -> None:
        result = extract_generated_text(
            _response(candidates=[]),
            GenerationType.RULES,
        )
        assert result.success is False
        assert result.retryable is False
        assert "candidati vuoti" in result.error_message

    def test_safety_finish_reason(self) -> None:
        result = extract_generated_text(
            _response(finish_reason="SAFETY"),
            GenerationType.CONTEXT,
        )
        assert result.success is False
        assert result.retryable is False

    def test_success_with_stop_finish_reason(self) -> None:
        result = extract_generated_text(
            _response("Hello world", finish_reason="STOP"),
            GenerationType.ARCHITECTURE,
        )
        assert result.success is True
        assert result.content == "Hello world"
        assert result.retryable is True

    @pytest.mark.parametrize("text", ["copied copyrighted snippet", "", None])
    def test_recitation_finish_reason_non_retryable(self, text: Any) -> None:
        result = extract_generated_text(
            _response(text=text, finish_reason="RECITATION"),
            GenerationType.ARCHITECTURE,
        )
        assert result.success is False
        assert result.retryable is False
        error = result.error_message.lower()
        assert (
            "recitazione" in error
            or "copyright" in error
            or "policy" in error
        )

    @pytest.mark.parametrize(
        "finish_reason",
        ["BLOCKLIST", "PROHIBITED_CONTENT", "SPII"],
    )
    def test_policy_finish_reasons_non_retryable(self, finish_reason: str) -> None:
        result = extract_generated_text(
            _response(text="blocked content", finish_reason=finish_reason),
            GenerationType.CONTEXT,
        )
        assert result.success is False
        assert result.retryable is False

    def test_empty_text(self) -> None:
        result = extract_generated_text(_response(text="  "), GenerationType.TESTING)
        assert result.success is False
        assert result.retryable is False

    def test_text_raises_value_error(self) -> None:
        result = extract_generated_text(
            _RaisingTextResponse(),
            GenerationType.API_DOCS,
        )
        assert result.success is False
        assert result.retryable is False
        assert "Impossibile leggere" in result.error_message

    def test_max_tokens_empty_is_retryable(self) -> None:
        result = extract_generated_text(
            _response(text="", finish_reason="MAX_TOKENS"),
            GenerationType.ONBOARDING,
        )
        assert result.success is False
        assert result.retryable is True
        assert "troncata" in result.error_message

    def test_length_empty_is_retryable(self) -> None:
        result = extract_generated_text(
            _response(text="", finish_reason="LENGTH"),
            GenerationType.ONBOARDING,
        )
        assert result.success is False
        assert result.retryable is True
        assert "troncata" in result.error_message


class TestModelFiltering:
    """Tests for generative model filtering."""

    def test_excludes_embedding(self) -> None:
        model = SimpleNamespace(name="models/text-embedding-004", supported_actions=["embedContent"])
        assert _is_text_generation_model(model) is False

    def test_excludes_computer_use(self) -> None:
        model = SimpleNamespace(
            name="models/gemini-2.5-computer-use-preview",
            supported_actions=["generateContent"],
        )
        assert _is_text_generation_model(model) is False

    def test_excludes_imagen(self) -> None:
        model = SimpleNamespace(
            name="models/imagen-3.0-generate-001",
            supported_actions=["generateContent"],
        )
        assert _is_text_generation_model(model) is False

    def test_excludes_aqa(self) -> None:
        model = SimpleNamespace(name="models/aqa", supported_actions=["generateContent"])
        assert _is_text_generation_model(model) is False

    def test_includes_gemini_generate_content(self) -> None:
        model = SimpleNamespace(
            name="models/gemini-2.0-flash",
            supported_actions=["generateContent"],
        )
        assert _is_text_generation_model(model) is True

    def test_includes_legacy_supported_generation_methods(self) -> None:
        model = SimpleNamespace(
            name="models/gemini-1.5-pro",
            supported_generation_methods=["generateContent"],
        )
        assert _is_text_generation_model(model) is True

    def test_includes_snake_case_generate_content_action(self) -> None:
        model = SimpleNamespace(
            name="models/gemini-2.0-flash",
            supported_actions=["generate_content"],
        )
        assert _is_text_generation_model(model) is True

    def test_excludes_non_gemini_without_actions(self) -> None:
        model = SimpleNamespace(name="models/chat-bison-001")
        assert _is_text_generation_model(model) is False


class TestGeminiAPIClient:
    """Tests for client configuration and generation with mocks."""

    def test_not_configured_by_default(self) -> None:
        client = GeminiAPIClient()
        assert client.is_configured is False
        success, message, count = client.test_connection()
        assert success is False
        assert count == 0
        assert "non configurata" in message

    def test_generate_without_client_fails(self) -> None:
        client = GeminiAPIClient()
        result = client.generate_documentation(
            "gemini-2.0-flash",
            "print('hi')",
            GenerationType.ARCHITECTURE,
        )
        assert result.success is False
        assert result.retryable is False

    def test_generate_success_with_mock_client(self, monkeypatch: Any) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _response("# Architettura\n\nOK")
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(client, "RETRY_DELAY", 0)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        result = client.generate_documentation(
            "gemini-2.0-flash",
            "def main(): pass",
            GenerationType.ARCHITECTURE,
        )
        assert result.success is True
        assert "Architettura" in result.content
        mock_models.generate_content.assert_called_once()

    @pytest.mark.parametrize(
        "model_name",
        ["", "   ", None, 123, "\x00", "gemini-\x00flash", "model\x7f", "\x1bmodel"],
    )
    def test_empty_model_name_fails_closed_without_generate_content(
        self, model_name: Any, monkeypatch: Any
    ) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _response("# Architettura\n\nOK")
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(client, "RETRY_DELAY", 0)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        result = client.generate_documentation(
            model_name,
            "def main(): pass",
            GenerationType.ARCHITECTURE,
        )
        assert result.success is False
        assert result.retryable is False
        assert "modello" in result.error_message.lower()
        mock_models.generate_content.assert_not_called()

    @pytest.mark.parametrize("code_content", ["", "   ", None, "\x00", "\x1b", "\x7f"])
    def test_empty_code_content_fails_closed_without_generate_content(
        self, code_content: Any, monkeypatch: Any
    ) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _response("# Architettura\n\nOK")
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(client, "RETRY_DELAY", 0)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        result = client.generate_documentation(
            "gemini-2.0-flash",
            code_content,
            GenerationType.ARCHITECTURE,
        )
        assert result.success is False
        assert result.retryable is False
        error = result.error_message.lower()
        assert "contenuto" in error
        assert "codice" in error or "vuoto" in error
        mock_models.generate_content.assert_not_called()

    def test_generate_forwards_prior_outputs_into_prompt(
        self, monkeypatch: Any
    ) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _response("# Regole\n\nOK")
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(client, "RETRY_DELAY", 0)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        result = client.generate_documentation(
            "gemini-2.0-flash",
            "def main(): pass",
            GenerationType.RULES,
            prior_outputs=[("AI_ARCHITECTURE.md", "# Architettura\n\nModuli core.")],
        )
        assert result.success is True
        prompt = mock_models.generate_content.call_args.kwargs["contents"]
        assert "DOCUMENTI GIÀ GENERATI IN QUESTO BUNDLE" in prompt
        assert "AI_ARCHITECTURE.md" in prompt
        assert "Moduli core" in prompt

    def test_blocked_response_does_not_retry(self, monkeypatch: Any) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _response(block_reason="SAFETY")
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(client, "RETRY_DELAY", 2)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        def _sleep_must_not_run(_seconds: float) -> None:
            raise AssertionError("sleep must not run on non-retryable failure")

        def _wait_must_not_run(_timeout: float | None = None) -> bool:
            raise AssertionError("wait must not run on non-retryable failure")

        monkeypatch.setattr("ai_context_studio.api_client.time.sleep", _sleep_must_not_run)
        monkeypatch.setattr(client._cancel_event, "wait", _wait_must_not_run)

        result = client.generate_documentation(
            "gemini-2.0-flash",
            "secret = 'x'",
            GenerationType.SECURITY,
        )
        assert result.success is False
        assert result.retryable is False
        assert mock_models.generate_content.call_count == 1
        assert result.retries == 0

    def test_cancelled_generation_skips_generate_content(
        self, monkeypatch: Any
    ) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _response("# Architettura\n\nOK")
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(client, "RETRY_DELAY", 0)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )
        client.cancel()

        result = client.generate_documentation(
            "gemini-2.0-flash",
            "def main(): pass",
            GenerationType.ARCHITECTURE,
        )
        assert result.success is False
        assert result.retryable is False
        assert result.error_message == "cancelled"
        mock_models.generate_content.assert_not_called()

    def test_cancel_during_retry_wait_skips_next_generate_content(
        self, monkeypatch: Any
    ) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()

        def _retryable_then_cancel(*_args: object, **_kwargs: object) -> SimpleNamespace:
            client.cancel()
            return _response(text="", finish_reason="MAX_TOKENS")

        mock_models.generate_content.side_effect = _retryable_then_cancel
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(client, "RETRY_DELAY", 2)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        def _sleep_must_not_run(_seconds: float) -> None:
            raise AssertionError("sleep must not run; cancel should interrupt wait")

        monkeypatch.setattr("ai_context_studio.api_client.time.sleep", _sleep_must_not_run)

        result = client.generate_documentation(
            "gemini-2.0-flash",
            "def main(): pass",
            GenerationType.ARCHITECTURE,
        )
        assert result.success is False
        assert result.retryable is False
        assert result.error_message == "cancelled"
        assert mock_models.generate_content.call_count == 1

    def test_clear_cancel_allows_later_generate(self, monkeypatch: Any) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _response("# Architettura\n\nOK")
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(client, "RETRY_DELAY", 0)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )
        client.cancel()
        client.clear_cancel()

        result = client.generate_documentation(
            "gemini-2.0-flash",
            "def main(): pass",
            GenerationType.ARCHITECTURE,
        )
        assert result.success is True
        mock_models.generate_content.assert_called_once()

    def test_get_models_uses_cache(self, mock_config_dir: Any, monkeypatch: Any) -> None:
        from ai_context_studio.config import ConfigManager

        config = ConfigManager()
        config.set_cached_models(["models/gemini-2.0-flash"])
        client = GeminiAPIClient()
        models = client.get_available_models()
        assert models == ["models/gemini-2.0-flash"]

    def test_get_available_models_returns_cache_without_force_refresh(
        self, monkeypatch: Any
    ) -> None:
        cached = ["models/gemini-2.0-flash", "models/gemini-1.5-pro"]
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = cached
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )

        client = GeminiAPIClient()
        client._client = MagicMock()
        models = client.get_available_models()

        assert models == cached
        mock_config.get_cached_models.assert_called_once()
        mock_config.set_cached_models.assert_not_called()
        client._client.models.list.assert_not_called()

    def test_get_available_models_filters_dirty_cached_names(
        self, monkeypatch: Any
    ) -> None:
        cached = [
            "models/gemini-2.5-flash",
            "models/imagen-3.0-generate-001",
            "",
            "models/embedding-001",
            123,
            "x\x00",
        ]
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = cached
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )

        client = GeminiAPIClient()
        client._client = MagicMock()
        models = client.get_available_models()

        assert models == ["models/gemini-2.5-flash"]
        mock_config.get_cached_models.assert_called_once()
        mock_config.set_cached_models.assert_not_called()
        client._client.models.list.assert_not_called()

    def test_get_available_models_non_list_cache_is_miss(
        self, monkeypatch: Any
    ) -> None:
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = "gemini-2.5"
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )

        client = GeminiAPIClient()
        client._client = MagicMock()
        models = client.get_available_models()

        assert models == []
        mock_config.get_cached_models.assert_called_once()
        mock_config.set_cached_models.assert_not_called()
        client._client.models.list.assert_not_called()

    def test_get_available_models_excluded_only_cache_is_miss(
        self, monkeypatch: Any
    ) -> None:
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = [
            "models/imagen-3.0-generate-001",
        ]
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )

        client = GeminiAPIClient()
        client._client = MagicMock()
        models = client.get_available_models()

        assert models == []
        assert "imagen" not in "".join(models).lower()
        mock_config.get_cached_models.assert_called_once()
        mock_config.set_cached_models.assert_not_called()
        client._client.models.list.assert_not_called()

    def test_get_available_models_empty_when_not_configured(
        self, monkeypatch: Any
    ) -> None:
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = None
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )

        client = GeminiAPIClient()
        assert client.is_configured is False
        models = client.get_available_models(force_refresh=True)

        assert models == []
        mock_config.set_cached_models.assert_not_called()

    def test_get_available_models_force_refresh_empty_list(
        self, monkeypatch: Any
    ) -> None:
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = ["models/stale-cache"]
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.list.return_value = []
        client._client = MagicMock()
        client._client.models = mock_models

        models = client.get_available_models(force_refresh=True)

        assert models == []
        mock_models.list.assert_called_once()
        mock_config.get_cached_models.assert_not_called()
        mock_config.set_cached_models.assert_called_once_with([])

    def test_get_models_filters_excluded_patterns(
        self, mock_config_dir: Any, monkeypatch: Any
    ) -> None:
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.list.return_value = [
            SimpleNamespace(
                name="models/gemini-1.5-flash",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/gemini-2.0-flash",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/imagen-3.0-generate-001",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/gemini-2.5-computer-use-preview",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/text-embedding-004",
                supported_actions=["embedContent"],
            ),
            SimpleNamespace(name="models/aqa", supported_actions=["generateContent"]),
        ]
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        names = client.get_available_models(force_refresh=True)
        assert names == ["models/gemini-2.0-flash", "models/gemini-1.5-flash"]
        mock_models.list.assert_called_once()

    def test_get_available_models_fetch_skips_nul_name(
        self, monkeypatch: Any
    ) -> None:
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = None
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.list.return_value = [
            SimpleNamespace(
                name="models/gemini-2.5-flash",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/gemini-2.5-\x00flash",
                supported_actions=["generateContent"],
            ),
        ]
        client._client = MagicMock()
        client._client.models = mock_models

        names = client.get_available_models(force_refresh=True)

        assert names == ["models/gemini-2.5-flash"]
        mock_models.list.assert_called_once()
        mock_models.generate_content.assert_not_called()

    def test_get_available_models_fetch_skips_del_name(
        self, monkeypatch: Any
    ) -> None:
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = None
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.list.return_value = [
            SimpleNamespace(
                name="gemini\x7f-2.5-flash",
                supported_actions=["generateContent"],
            ),
        ]
        client._client = MagicMock()
        client._client.models = mock_models

        names = client.get_available_models(force_refresh=True)

        assert names == []
        mock_models.list.assert_called_once()
        mock_models.generate_content.assert_not_called()

    def test_get_available_models_fetch_skips_whitespace_only_name(
        self, monkeypatch: Any
    ) -> None:
        mock_config = MagicMock()
        mock_config.get_cached_models.return_value = None
        monkeypatch.setattr(
            "ai_context_studio.api_client.ConfigManager",
            MagicMock(return_value=mock_config),
        )
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.list.return_value = [
            SimpleNamespace(
                name="models/gemini-2.5-flash",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="   ",
                supported_actions=["generateContent"],
            ),
        ]
        client._client = MagicMock()
        client._client.models = mock_models

        names = client.get_available_models(force_refresh=True)

        assert names == ["models/gemini-2.5-flash"]
        mock_models.list.assert_called_once()
        mock_models.generate_content.assert_not_called()

    def test_configure_when_genai_unavailable(self, monkeypatch: Any) -> None:
        from ai_context_studio import api_client as api_client_mod

        constructed: list[object] = []

        class _RecordingClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                constructed.append((args, kwargs))

        monkeypatch.setattr(api_client_mod, "GENAI_AVAILABLE", False)
        if api_client_mod.genai is not None:
            monkeypatch.setattr(api_client_mod.genai, "Client", _RecordingClient)

        client = GeminiAPIClient()
        assert client.configure("unused-key") is False
        assert client.is_configured is False
        assert client._client is None
        assert constructed == []

    @pytest.mark.parametrize("api_key", ["", "   ", None, 123, "AIza\x00dead"])
    def test_configure_rejects_invalid_key_without_constructing_client(
        self, api_key: Any, monkeypatch: Any
    ) -> None:
        from ai_context_studio import api_client as api_client_mod

        mock_client_cls = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client = mock_client_cls
        monkeypatch.setattr(api_client_mod, "GENAI_AVAILABLE", True)
        monkeypatch.setattr(api_client_mod, "genai", mock_genai)

        client = GeminiAPIClient()
        result = client.configure(api_key)

        assert result is False
        assert client.is_configured is False
        assert client._client is None
        mock_client_cls.assert_not_called()

    def test_configure_success_with_mocked_client(self, monkeypatch: Any) -> None:
        from ai_context_studio import api_client as api_client_mod

        mock_client_instance = MagicMock()
        mock_client_cls = MagicMock(return_value=mock_client_instance)
        mock_genai = MagicMock()
        mock_genai.Client = mock_client_cls
        monkeypatch.setattr(api_client_mod, "GENAI_AVAILABLE", True)
        monkeypatch.setattr(api_client_mod, "genai", mock_genai)

        client = GeminiAPIClient()
        result = client.configure("valid-test-key")

        assert result is True
        assert client.is_configured is True
        assert client._client is mock_client_instance
        mock_client_cls.assert_called_once_with(api_key="valid-test-key")

    def test_configure_redacts_key_from_client_init_exception(
        self, monkeypatch: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        from ai_context_studio import api_client as api_client_mod

        leaky_key = "AIzaSyDummyTestKeyNotReal000"
        mock_genai = MagicMock()
        mock_genai.Client = MagicMock(
            side_effect=Exception(f"bad key {leaky_key}")
        )
        monkeypatch.setattr(api_client_mod, "GENAI_AVAILABLE", True)
        monkeypatch.setattr(api_client_mod, "genai", mock_genai)

        client = GeminiAPIClient()
        with caplog.at_level(logging.ERROR, logger="ai_context_studio.api_client"):
            result = client.configure(leaky_key)

        assert result is False
        assert client.is_configured is False
        assert leaky_key not in caplog.text
        assert "[REDACTED]" in caplog.text

    def test_connection_success_with_one_gemini_model(self, monkeypatch: Any) -> None:
        gemini_model = MagicMock()
        gemini_model.name = "models/gemini-2.0-flash"
        gemini_model.supported_actions = ["generateContent"]

        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.list.return_value = [gemini_model]
        client._client = MagicMock()
        client._client.models = mock_models
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        success, message, count = client.test_connection()

        assert success is True
        assert count == 1
        assert "riuscita" in message
        mock_models.list.assert_called_once()

    def test_connection_redacts_key_from_exception_message(
        self, monkeypatch: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        leaky_key = "AIzaSyDummyTestKeyNotReal000"
        client = GeminiAPIClient()
        client._configured = True
        mock_models = MagicMock()
        mock_models.list.side_effect = Exception(f"invalid api_key={leaky_key}")
        client._client = SimpleNamespace(models=mock_models)
        monkeypatch.setattr(
            "ai_context_studio.api_client.GENAI_AVAILABLE",
            True,
        )

        with caplog.at_level(logging.ERROR, logger="ai_context_studio.api_client"):
            success, message, count = client.test_connection()

        assert success is False
        assert count == 0
        assert leaky_key not in message
        assert "[REDACTED]" in message
        assert leaky_key not in caplog.text
        assert "[REDACTED]" in caplog.text


class TestPaidApiGuardrail:
    """Session autouse fixture must block live google.genai Client construction."""

    def test_client_init_raises_without_rewriting_mocks(self) -> None:
        from google import genai

        with pytest.raises(RuntimeError, match="paid API blocked in tests"):
            genai.Client(api_key="must-not-call-network")

    def test_configure_cannot_construct_real_client(self) -> None:
        from ai_context_studio import api_client as api_client_mod

        if not api_client_mod.GENAI_AVAILABLE:
            pytest.skip("google-genai not installed")

        client = GeminiAPIClient()
        assert client.configure("must-not-call-network") is False
        assert client.is_configured is False
        assert client._client is None
