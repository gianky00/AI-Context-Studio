# -*- coding: utf-8 -*-
"""Redact API keys and token-like secrets from strings and log records."""

from __future__ import annotations

import logging
import re

REDACTED = "[REDACTED]"

# Gemini / Google API keys (AIza... including short fixtures used in tests).
_GEMINI_API_KEY = re.compile(r"AIza[0-9A-Za-z_\-]{10,}")

# Values after api_key= / api_key: (query strings, kwargs, config dumps).
_API_KEY_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;\"']+)",
)

# Long token-looking strings: mixed-case, 32+ URL-safe chars (avoids hex SHAs).
_LONG_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?=[A-Za-z0-9_\-]{32,})"
    r"(?=[^A-Z]*[A-Z])"
    r"(?=[^a-z]*[a-z])"
    r"(?=[^0-9]*[0-9])"
    r"[A-Za-z0-9_\-]{32,}"
    r"(?![A-Za-z0-9])"
)

# Authorization: Bearer <token> (scheme matched case-insensitively).
_BEARER_TOKEN = re.compile(r"(?i)(\bBearer\s+)\S+")

# JWT-shaped strings: three base64url segments (header typically starts with eyJ).
_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    r"(?![A-Za-z0-9_-])"
)

# Classic GitHub PATs: ghp_ + exactly 36 URL-safe chars (often lowercase).
_GITHUB_CLASSIC_PAT = re.compile(r"ghp_[A-Za-z0-9_\-]{36}")

# Fine-grained GitHub PATs: github_pat_ + alphanumerics, underscore, more alphanumerics.
_GITHUB_FINE_GRAINED_PAT = re.compile(r"github_pat_[A-Za-z0-9]+_[A-Za-z0-9]+")

# AWS access key IDs: AKIA + exactly 16 uppercase alphanumeric (all-caps, no lowercase).
_AWS_ACCESS_KEY_ID = re.compile(r"AKIA[A-Z0-9]{16}")

# Slack bot/user tokens: xoxb- / xoxp- + digits/letters/hyphens (lowercase-heavy).
_SLACK_TOKEN = re.compile(r"xox[bp]-[A-Za-z0-9\-]{20,}")

# OpenAI user/project API keys: sk- / sk-proj- + 20+ URL-safe chars (does not match "skip").
_OPENAI_SECRET_KEY = re.compile(
    r"(?<![A-Za-z0-9])sk-(?:proj-)?[A-Za-z0-9_\-]{20,}(?![A-Za-z0-9])"
)

# PEM private keys (PKCS#8, RSA, EC, OPENSSH). Does not match CERTIFICATE / PUBLIC KEY.
_PEM_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"
    r".*?"
    r"-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)


def redact_secrets(text: str) -> str:
    """Return *text* with API keys and token-like strings replaced."""
    redacted = _PEM_PRIVATE_KEY.sub(REDACTED, text)
    redacted = _API_KEY_ASSIGNMENT.sub(rf"\1{REDACTED}", redacted)
    redacted = _GEMINI_API_KEY.sub(REDACTED, redacted)
    redacted = _BEARER_TOKEN.sub(rf"\1{REDACTED}", redacted)
    redacted = _JWT.sub(REDACTED, redacted)
    redacted = _GITHUB_CLASSIC_PAT.sub(REDACTED, redacted)
    redacted = _GITHUB_FINE_GRAINED_PAT.sub(REDACTED, redacted)
    redacted = _AWS_ACCESS_KEY_ID.sub(REDACTED, redacted)
    redacted = _SLACK_TOKEN.sub(REDACTED, redacted)
    redacted = _OPENAI_SECRET_KEY.sub(REDACTED, redacted)
    redacted = _LONG_TOKEN.sub(REDACTED, redacted)
    return redacted


class SecretRedactionFilter(logging.Filter):
    """Logging filter that strips API keys from LogRecord messages and args."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        record.msg = redact_secrets(rendered)
        record.args = None
        if record.exc_info and not record.exc_text:
            try:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            except Exception:
                pass
        if record.exc_text:
            record.exc_text = redact_secrets(record.exc_text)
        if record.stack_info:
            record.stack_info = redact_secrets(record.stack_info)
        return True
