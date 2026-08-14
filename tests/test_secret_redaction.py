# -*- coding: utf-8 -*-
"""Unit tests for redact_secrets and SecretRedactionFilter."""

from __future__ import annotations

import logging
import sys
from typing import get_type_hints

import pytest

from ai_context_studio.secret_redaction import (
    REDACTED,
    SecretRedactionFilter,
    redact_secrets,
)

_FAKE_GEMINI_KEY = "AIzaSyDummyTestKeyNotReal000"
_FAKE_TRACEBACK_GEMINI_KEY = "AIzaSyDummyKeyValueHere"
_CLASSIC_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.signaturepart"
)
_LONG_MIXED_TOKEN = "AbCdEfGhIjKlMnOpQrStUvWxYz012345"
# Classic GitHub PAT: ghp_ + 36 URL-safe chars (lowercase so _LONG_TOKEN cannot match).
_GITHUB_CLASSIC_PAT = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
# Fine-grained PAT: github_pat_ + alphanumeric run, underscore, more alphanumerics.
_GITHUB_FINE_GRAINED_PAT = (
    "github_pat_11aaaa0bbb0ccc0ddd0eee_"
    "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
)
# AWS access key ID: AKIA + exactly 16 uppercase alphanumeric (all-caps, no lowercase).
_AWS_ACCESS_KEY_ID = "AKIATESTKEY000000001"
# Slack bot/user tokens: lowercase-heavy with hyphens so _LONG_TOKEN cannot match.
_SLACK_BOT_TOKEN = "xoxb-dummy-token-for-testing-purposes-only-12345"
_SLACK_USER_TOKEN = "xoxp-dummy-token-for-testing-purposes-only-12345"
# OpenAI user/project keys: sk- / sk-proj- + 48 URL-safe chars (lowercase so
# _LONG_TOKEN cannot hide a missing OpenAI regex).
_OPENAI_USER_KEY = "sk-abcdefghijklmnopqrstuvwxyz0123456789abcdefghijkl"
_OPENAI_PROJECT_KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789abcdefghijkl"
# All-caps PEM bodies so _LONG_TOKEN (mixed-case) cannot hide a missing PEM regex.
_PKCS8_BODY = "MIIEVQIBADANBGKQHKI+G9W0BAQEFAASCBKC/WGGSJAGEAAOIBAQCUMMYNOTAREAL"
_RSA_BODY = "MIIEOWIBAAKDUMMYRSAPRIVATEKEYBODY+NOTAREALKEY/ABCDEF0123456789=="
_OPENSSH_BODY = "B3BLBNNZAC1RZXKTDJEAAAABG5VBMUDUMMYOPENSSH+PRIVATE/KEYNOTREAL=="
_EC_BODY = "MHCAGQEEIDUMMYECPRIVATEKEY+BODYNOTAREAL/ABCDEFGHIJKLMN012345=="
_CERT_BODY = "MIIDXTCCAKWGAWIBAGIJADUMMYCERTBODY+NOTAPRIVATEKEY/ABCDEF0123=="
_PUBLIC_KEY_BODY = "MIIBIJANBGKQHKI+G9W0BAQEFAAOC/AQ8AMIIBCGKCAQEADUMMYPUBLICKEY=="


class TestRedactSecrets:
    """Direct coverage of redact_secrets string replacements."""

    def test_aiza_key_is_redacted(self) -> None:
        result = redact_secrets(f"connecting with {_FAKE_GEMINI_KEY}")
        assert _FAKE_GEMINI_KEY not in result
        assert REDACTED in result

    def test_api_key_assignment_is_redacted(self) -> None:
        result = redact_secrets("config api_key=sk-not-a-real-secret extra")
        assert "sk-not-a-real-secret" not in result
        assert f"api_key={REDACTED}" in result

    def test_mixed_case_api_key_assignment(self) -> None:
        result = redact_secrets("dump API_KEY=MixedCaseSecret99")
        assert "MixedCaseSecret99" not in result
        assert f"API_KEY={REDACTED}" in result

    def test_authorization_bearer_jwt_is_redacted(self) -> None:
        header = f"Authorization: Bearer {_CLASSIC_JWT}"
        result = redact_secrets(header)
        assert _CLASSIC_JWT not in result
        assert "signaturepart" not in result
        assert ".e30." not in result
        assert "Authorization" in result
        assert "Bearer" in result
        assert REDACTED in result

    def test_bearer_is_case_insensitive(self) -> None:
        result = redact_secrets(f"auth bearer {_CLASSIC_JWT}")
        assert _CLASSIC_JWT not in result
        assert "signaturepart" not in result
        assert "bearer" in result.lower()
        assert REDACTED in result

    def test_jwt_without_bearer_prefix_is_redacted(self) -> None:
        result = redact_secrets(f"token dump {_CLASSIC_JWT} extra")
        assert _CLASSIC_JWT not in result
        assert "signaturepart" not in result
        assert ".e30." not in result
        assert REDACTED in result

    def test_mixed_case_long_token_is_redacted(self) -> None:
        result = redact_secrets(f"session {_LONG_MIXED_TOKEN}")
        assert _LONG_MIXED_TOKEN not in result
        assert REDACTED in result

    def test_github_classic_pat_is_redacted(self) -> None:
        result = redact_secrets(f"token {_GITHUB_CLASSIC_PAT} in env")
        assert _GITHUB_CLASSIC_PAT not in result
        assert "abcdefghijklmnopqrstuvwxyz0123456789" not in result
        assert REDACTED in result

    def test_github_fine_grained_pat_is_redacted(self) -> None:
        result = redact_secrets(f"dump {_GITHUB_FINE_GRAINED_PAT} extra")
        assert _GITHUB_FINE_GRAINED_PAT not in result
        assert "github_pat_11aaaa0bbb0ccc0ddd0eee_" not in result
        assert REDACTED in result

    def test_github_classic_prefix_alone_is_not_redacted(self) -> None:
        text = "docs mention the ghp_ prefix and a short ghp_abc example"
        assert redact_secrets(text) == text

    def test_aws_access_key_id_is_redacted(self) -> None:
        result = redact_secrets(f"AWS_ACCESS_KEY_ID={_AWS_ACCESS_KEY_ID} extra")
        assert _AWS_ACCESS_KEY_ID not in result
        assert REDACTED in result

    def test_short_akia_prefix_is_not_redacted(self) -> None:
        text = "docs mention the AKIA prefix and a short AKIABC example"
        assert redact_secrets(text) == text

    def test_slack_bot_token_is_redacted(self) -> None:
        result = redact_secrets(f"bot token {_SLACK_BOT_TOKEN} in env")
        assert _SLACK_BOT_TOKEN not in result
        assert "testing-purposes" not in result
        assert REDACTED in result

    def test_slack_user_token_is_redacted(self) -> None:
        result = redact_secrets(f"user token {_SLACK_USER_TOKEN} extra")
        assert _SLACK_USER_TOKEN not in result
        assert REDACTED in result

    def test_short_slack_bot_prefix_is_not_redacted(self) -> None:
        text = "docs mention the xoxb- prefix and a short xoxb-1 example"
        assert redact_secrets(text) == text

    def test_openai_user_key_is_redacted(self) -> None:
        result = redact_secrets(f"openai key {_OPENAI_USER_KEY} in env")
        assert _OPENAI_USER_KEY not in result
        assert "abcdefghijklmnopqrstuvwxyz0123456789abcdefghijkl" not in result
        assert "openai key" in result
        assert "in env" in result
        assert REDACTED in result

    def test_openai_project_key_is_redacted(self) -> None:
        result = redact_secrets(f"project key {_OPENAI_PROJECT_KEY} extra")
        assert _OPENAI_PROJECT_KEY not in result
        assert "sk-proj-" not in result
        assert "abcdefghijklmnopqrstuvwxyz0123456789abcdefghijkl" not in result
        assert "project key" in result
        assert "extra" in result
        assert REDACTED in result

    def test_skip_and_short_sk_are_not_redacted(self) -> None:
        text = "docs mention skip-this and a short sk-abc example"
        assert redact_secrets(text) == text

    def test_openai_redaction_keeps_other_secret_classes(self) -> None:
        cert = (
            "-----BEGIN CERTIFICATE-----\n"
            f"{_CERT_BODY}\n"
            "-----END CERTIFICATE-----"
        )
        pkcs8 = (
            "-----BEGIN PRIVATE KEY-----\n"
            f"{_PKCS8_BODY}\n"
            "-----END PRIVATE KEY-----"
        )
        text = (
            f"{_FAKE_GEMINI_KEY} {_GITHUB_CLASSIC_PAT} {_SLACK_BOT_TOKEN} "
            f"{_OPENAI_USER_KEY}\n{cert}\n{pkcs8}"
        )
        result = redact_secrets(text)
        assert _OPENAI_USER_KEY not in result
        assert _FAKE_GEMINI_KEY not in result
        assert _GITHUB_CLASSIC_PAT not in result
        assert _SLACK_BOT_TOKEN not in result
        assert _PKCS8_BODY not in result
        assert "BEGIN CERTIFICATE" in result
        assert _CERT_BODY in result
        assert REDACTED in result

    def test_normal_sentence_is_not_redacted(self) -> None:
        sentence = (
            "Please paste the api_key from your dashboard into settings. "
            "Gemini keys historically used an AIza prefix in documentation."
        )
        assert redact_secrets(sentence) == sentence

    def test_pkcs8_private_key_body_is_redacted(self) -> None:
        pem = (
            "-----BEGIN PRIVATE KEY-----\n"
            f"{_PKCS8_BODY}\n"
            "-----END PRIVATE KEY-----"
        )
        result = redact_secrets(f"exception dump:\n{pem}\nnext frame")
        assert _PKCS8_BODY not in result
        assert REDACTED in result
        assert "exception dump:" in result
        assert "next frame" in result

    def test_rsa_private_key_body_is_redacted(self) -> None:
        pem = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            f"{_RSA_BODY}\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = redact_secrets(pem)
        assert _RSA_BODY not in result
        assert REDACTED in result

    def test_openssh_private_key_body_is_redacted(self) -> None:
        pem = (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            f"{_OPENSSH_BODY}\n"
            "-----END OPENSSH PRIVATE KEY-----"
        )
        result = redact_secrets(pem)
        assert _OPENSSH_BODY not in result
        assert REDACTED in result

    def test_ec_private_key_body_is_redacted(self) -> None:
        pem = (
            "-----BEGIN EC PRIVATE KEY-----\n"
            f"{_EC_BODY}\n"
            "-----END EC PRIVATE KEY-----"
        )
        result = redact_secrets(pem)
        assert _EC_BODY not in result
        assert REDACTED in result

    def test_certificate_is_not_redacted(self) -> None:
        pem = (
            "-----BEGIN CERTIFICATE-----\n"
            f"{_CERT_BODY}\n"
            "-----END CERTIFICATE-----"
        )
        assert redact_secrets(pem) == pem

    def test_public_key_is_not_redacted(self) -> None:
        pem = (
            "-----BEGIN PUBLIC KEY-----\n"
            f"{_PUBLIC_KEY_BODY}\n"
            "-----END PUBLIC KEY-----"
        )
        assert redact_secrets(pem) == pem

    def test_empty_string_unchanged(self) -> None:
        assert redact_secrets("") == ""

    def test_signature_is_str_only(self) -> None:
        hints = get_type_hints(redact_secrets)
        assert hints["text"] is str
        assert hints["return"] is str


def _record_with_exc_info(message: str, log_msg: str = "handler failed") -> logging.LogRecord:
    """Build a LogRecord whose traceback message contains *message* and exc_text is None."""
    try:
        raise ValueError(message)
    except ValueError:
        record = logging.LogRecord(
            name="ai_context_studio.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=log_msg,
            args=(),
            exc_info=sys.exc_info(),
        )
    assert record.exc_text is None
    return record


class TestSecretRedactionFilter:
    """Formatter.format after the filter must not leak secrets from tracebacks."""

    def test_exc_info_aiza_secret_is_redacted_before_formatter(self) -> None:
        record = _record_with_exc_info(f"boom {_FAKE_TRACEBACK_GEMINI_KEY}")
        assert SecretRedactionFilter().filter(record) is True
        formatted = logging.Formatter().format(record)
        assert _FAKE_TRACEBACK_GEMINI_KEY not in formatted
        assert REDACTED in formatted

    def test_exc_info_openai_key_is_redacted_before_formatter(self) -> None:
        record = _record_with_exc_info(f"boom {_OPENAI_USER_KEY}")
        assert SecretRedactionFilter().filter(record) is True
        formatted = logging.Formatter().format(record)
        assert _OPENAI_USER_KEY not in formatted
        assert REDACTED in formatted

    def test_msg_is_redacted_when_no_exc_info(self) -> None:
        record = logging.LogRecord(
            name="ai_context_studio.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=f"connecting with {_FAKE_GEMINI_KEY}",
            args=(),
            exc_info=None,
        )
        assert SecretRedactionFilter().filter(record) is True
        assert record.args is None
        assert _FAKE_GEMINI_KEY not in record.msg
        assert REDACTED in record.msg
        formatted = logging.Formatter().format(record)
        assert _FAKE_GEMINI_KEY not in formatted
        assert REDACTED in formatted

    def test_already_populated_exc_text_is_redacted(self) -> None:
        record = logging.LogRecord(
            name="ai_context_studio.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="handler failed",
            args=(),
            exc_info=None,
        )
        record.exc_text = f"Traceback (most recent call last):\nValueError: boom {_FAKE_GEMINI_KEY}"
        assert SecretRedactionFilter().filter(record) is True
        assert _FAKE_GEMINI_KEY not in record.exc_text
        assert REDACTED in record.exc_text
        formatted = logging.Formatter().format(record)
        assert _FAKE_GEMINI_KEY not in formatted
        assert REDACTED in formatted

    def test_stack_info_is_redacted(self) -> None:
        record = logging.LogRecord(
            name="ai_context_studio.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="handler failed",
            args=("kept-arg",),
            exc_info=None,
        )
        record.stack_info = f"Stack (most recent call last):\nsecret {_FAKE_GEMINI_KEY}"
        assert SecretRedactionFilter().filter(record) is True
        assert record.args is None
        assert _FAKE_GEMINI_KEY not in record.stack_info
        assert REDACTED in record.stack_info

    def test_filter_returns_true_when_exc_info_format_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        record = _record_with_exc_info(f"boom {_FAKE_TRACEBACK_GEMINI_KEY}")

        def _raise_format_error(*_args: object, **_kwargs: object) -> str:
            raise RuntimeError("formatException failed")

        monkeypatch.setattr(logging.Formatter, "formatException", _raise_format_error)
        assert SecretRedactionFilter().filter(record) is True
