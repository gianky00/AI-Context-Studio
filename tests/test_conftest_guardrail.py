# -*- coding: utf-8 -*-
"""Autouse paid-API guardrail must block live google.genai calls.

Invokes the patched ``Client.__init__``, ``Models.generate_content``, and
``Models.list`` as unbound callables so a missing patch fails with TypeError
instead of opening a billed HTTP session. Does not pass an API key. Skips
when ``google.genai`` is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("google.genai")


class TestPaidApiGuardrail:
    """Session autouse fixture must raise before any Gemini HTTP call."""

    def test_client_init_raises_paid_api_blocked(self) -> None:
        from google.genai.client import Client

        with pytest.raises(RuntimeError, match="paid API blocked"):
            Client.__init__()

    def test_models_generate_content_raises_paid_api_blocked(self) -> None:
        from google.genai.models import Models

        with pytest.raises(RuntimeError, match="paid API blocked"):
            Models.generate_content()

    def test_models_list_raises_paid_api_blocked(self) -> None:
        from google.genai.models import Models

        with pytest.raises(RuntimeError, match="paid API blocked"):
            Models.list()
