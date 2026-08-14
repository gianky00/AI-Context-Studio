# -*- coding: utf-8 -*-
"""Rotating file logging helper. main.setup_logging should call this later."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import restrict_file_permissions
from .secret_redaction import SecretRedactionFilter

_LOG_FILENAME = "ai_context_studio.log"
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3

_file_logging_configured = False
_logger = logging.getLogger(__name__)


def _restricting_rotator(source: str, dest: str) -> None:
    """Rename like the default rotator, then tighten ACL on the backup."""
    os.rename(source, dest)
    restrict_file_permissions(Path(dest))


def _has_redaction_filter(filterer: logging.Filterer) -> bool:
    return any(isinstance(item, SecretRedactionFilter) for item in filterer.filters)


def ensure_secret_redaction(root: logging.Logger | None = None) -> None:
    """Attach SecretRedactionFilter to the root logger and every handler.

    A root Filter covers records logged on root. Handler Filters cover child
    loggers (file + stdout StreamHandlers from main.setup_logging).
    Idempotent.
    """
    if root is None:
        root = logging.getLogger()
    if not _has_redaction_filter(root):
        root.addFilter(SecretRedactionFilter())
    for handler in root.handlers:
        if not _has_redaction_filter(handler):
            handler.addFilter(SecretRedactionFilter())


def setup_file_logging(log_dir: Path, debug: bool = False) -> Path:
    """Attach a rotating file handler without removing existing StreamHandlers.

    Creates ``log_dir`` if needed. If ``log_dir`` cannot be created (for
    example it already exists as a file), logs a warning, skips the file
    handler, and still installs secret redaction so stdout logging works.
    Does not remove existing StreamHandler instances (main.py already logs
    to stdout). Always installs secret redaction on root and handlers
    (including pre-existing StreamHandlers).

    Args:
        log_dir: Directory for the log file.
        debug: If True, set level to DEBUG; otherwise INFO.

    Returns:
        Path to the log file.
    """
    global _file_logging_configured

    log_dir = Path(log_dir)
    log_path = log_dir / _LOG_FILENAME
    root = logging.getLogger()

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        _logger.warning(
            "Could not create log directory; file logging disabled"
        )
        ensure_secret_redaction(root)
        return log_path

    if _file_logging_configured:
        ensure_secret_redaction(root)
        return log_path

    for handler in root.handlers:
        if isinstance(handler, RotatingFileHandler):
            handler.rotator = _restricting_rotator
            _file_logging_configured = True
            ensure_secret_redaction(root)
            return log_path

    level = logging.DEBUG if debug else logging.INFO
    try:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        _logger.warning("Could not open log file; file logging disabled")
        ensure_secret_redaction(root)
        return log_path

    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.rotator = _restricting_rotator
    root.addHandler(handler)
    restrict_file_permissions(log_path)

    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    _file_logging_configured = True
    ensure_secret_redaction(root)
    return log_path
