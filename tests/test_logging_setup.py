# -*- coding: utf-8 -*-
"""Tests for rotating file logging helper."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Generator

import pytest

from ai_context_studio import logging_setup as logging_setup_mod
from ai_context_studio.logging_setup import ensure_secret_redaction, setup_file_logging
from ai_context_studio.secret_redaction import REDACTED, SecretRedactionFilter


def _rotating_file_handlers() -> list[RotatingFileHandler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, RotatingFileHandler)
    ]


def _redaction_filter_count(filterer: logging.Filterer) -> int:
    return sum(1 for item in filterer.filters if isinstance(item, SecretRedactionFilter))


def _drop_redaction_filters(filterer: logging.Filterer) -> None:
    for item in list(filterer.filters):
        if isinstance(item, SecretRedactionFilter):
            filterer.removeFilter(item)


@pytest.fixture
def reset_file_logging() -> Generator[None, None, None]:
    """Reset module flag and remove handlers added during a test."""
    logging_setup_mod._file_logging_configured = False
    root = logging.getLogger()
    existing = list(root.handlers)
    previous_level = root.level
    yield
    logging_setup_mod._file_logging_configured = False
    root.setLevel(previous_level)
    _drop_redaction_filters(root)
    for handler in list(root.handlers):
        _drop_redaction_filters(handler)
        if handler not in existing:
            root.removeHandler(handler)
            handler.close()


class TestSetupFileLogging:
    """Tests for setup_file_logging."""

    def test_creates_log_file(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = setup_file_logging(temp_dir)

        assert log_path == temp_dir / "ai_context_studio.log"
        assert log_path.is_file()

    def test_returns_log_path_under_given_temp_dir(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = setup_file_logging(temp_dir)
        resolved = log_path.resolve()
        home_config = (Path.home() / ".ai_context_studio").resolve()

        assert log_path.name == "ai_context_studio.log"
        assert resolved.parent == temp_dir.resolve()
        assert home_config not in resolved.parents
        assert resolved != home_config / "ai_context_studio.log"

    def test_creates_log_dir_if_needed(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        nested = temp_dir / "nested" / "logs"
        assert not nested.exists()

        log_path = setup_file_logging(nested)

        assert nested.is_dir()
        assert log_path.is_file()

    def test_writes_log_record(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = setup_file_logging(temp_dir)
        marker = "unique-file-logging-record-42"

        logger = logging.getLogger("ai_context_studio.logging_setup.test")
        logger.info(marker)
        for handler in logging.getLogger().handlers:
            handler.flush()

        content = log_path.read_text(encoding="utf-8")
        assert marker in content
        assert "INFO" in content

    def test_idempotent_does_not_duplicate_handlers(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        first = setup_file_logging(temp_dir)
        count_after_first = len(_rotating_file_handlers())

        second = setup_file_logging(temp_dir)
        count_after_second = len(_rotating_file_handlers())

        assert first == second
        assert count_after_first == 1
        assert count_after_second == count_after_first

    def test_preserves_existing_stream_handler(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        root = logging.getLogger()
        stream_handler = logging.StreamHandler()
        root.addHandler(stream_handler)
        try:
            setup_file_logging(temp_dir)
            assert stream_handler in root.handlers
        finally:
            root.removeHandler(stream_handler)
            stream_handler.close()

    def test_handler_uses_utf8_encoding(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = setup_file_logging(temp_dir)
        handlers = _rotating_file_handlers()

        assert len(handlers) == 1
        assert handlers[0].encoding == "utf-8"

        marker = "utf8-record-café-日本語"
        logging.getLogger("ai_context_studio.logging_setup.test").info(marker)
        for handler in logging.getLogger().handlers:
            handler.flush()
        assert marker in log_path.read_text(encoding="utf-8")

    def test_rotating_handler_uses_max_bytes_and_backup_count(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = setup_file_logging(temp_dir)
        handlers = _rotating_file_handlers()

        assert log_path.parent == temp_dir
        assert len(handlers) == 1
        assert handlers[0].maxBytes == 1_000_000
        assert handlers[0].backupCount == 3

    def test_debug_flag_sets_handler_level(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = setup_file_logging(temp_dir, debug=True)
        handlers = _rotating_file_handlers()

        assert len(handlers) == 1
        assert handlers[0].level == logging.DEBUG
        assert handlers[0].maxBytes == 1_000_000
        assert handlers[0].backupCount == 3

        marker = "debug-record-should-be-present"
        logging.getLogger("ai_context_studio.logging_setup.test").debug(marker)
        for handler in logging.getLogger().handlers:
            handler.flush()
        assert marker in log_path.read_text(encoding="utf-8")

    def test_default_info_level_drops_debug_records(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = setup_file_logging(temp_dir, debug=False)
        handlers = _rotating_file_handlers()

        assert len(handlers) == 1
        assert handlers[0].level == logging.INFO

        logger = logging.getLogger("ai_context_studio.logging_setup.test")
        logger.debug("debug-record-should-be-absent")
        logger.info("info-record-should-be-present")
        for handler in logging.getLogger().handlers:
            handler.flush()

        content = log_path.read_text(encoding="utf-8")
        assert "debug-record-should-be-absent" not in content
        assert "info-record-should-be-present" in content

    def test_second_call_is_idempotent_and_reattaches_redaction(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        setup_file_logging(temp_dir, debug=False)
        root = logging.getLogger()
        _drop_redaction_filters(root)
        for handler in root.handlers:
            _drop_redaction_filters(handler)

        setup_file_logging(temp_dir, debug=True)

        handlers = _rotating_file_handlers()
        assert len(handlers) == 1
        assert handlers[0].level == logging.INFO
        assert _redaction_filter_count(root) == 1
        for handler in handlers:
            assert _redaction_filter_count(handler) == 1

    def test_restricts_log_file_permissions(
        self,
        temp_dir: Path,
        reset_file_logging: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(Path(path))

        monkeypatch.setattr(
            logging_setup_mod, "restrict_file_permissions", record_restrict
        )

        log_path = setup_file_logging(temp_dir)

        assert recorded == [log_path]
        assert log_path.is_file()

    def test_second_call_does_not_restrict_again(
        self,
        temp_dir: Path,
        reset_file_logging: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Idempotent: first successful handler attach is enough.

        A second call while ``_file_logging_configured`` is already True
        must not invoke restrict_file_permissions again.
        """
        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(Path(path))

        monkeypatch.setattr(
            logging_setup_mod, "restrict_file_permissions", record_restrict
        )

        first = setup_file_logging(temp_dir)
        assert recorded == [first]

        second = setup_file_logging(temp_dir)
        assert second == first
        assert recorded == [first]

    def test_rotate_restricts_backup_file_permissions(
        self,
        temp_dir: Path,
        reset_file_logging: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rotated backups (log.1 / .2 / .3) must get the same ACL as the live log.

        Drive RotatingFileHandler.rotate with temp files — do not fill maxBytes.
        """
        setup_file_logging(temp_dir)
        handlers = _rotating_file_handlers()
        assert len(handlers) == 1
        handler = handlers[0]

        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(Path(path))

        monkeypatch.setattr(
            logging_setup_mod, "restrict_file_permissions", record_restrict
        )

        source = temp_dir / "rotate_source.log"
        dest = temp_dir / "ai_context_studio.log.1"
        source.write_text("rotated-backup-payload", encoding="utf-8")

        if callable(handler.rotator):
            handler.rotator(str(source), str(dest))
        else:
            handler.rotate(str(source), str(dest))

        assert dest in recorded
        assert dest.is_file()
        assert not source.exists()

    def test_existing_rotating_handler_skips_new_handler(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = temp_dir / "preexisting.log"
        existing = RotatingFileHandler(log_path, encoding="utf-8")
        root = logging.getLogger()
        root.addHandler(existing)
        try:
            returned = setup_file_logging(temp_dir)
            assert returned == temp_dir / "ai_context_studio.log"
            assert len(_rotating_file_handlers()) == 1
            assert existing in root.handlers
            assert logging_setup_mod._file_logging_configured is True
            assert _redaction_filter_count(root) == 1
            assert _redaction_filter_count(existing) == 1
        finally:
            root.removeHandler(existing)
            existing.close()

    def test_existing_handler_gets_restricting_rotator(
        self,
        temp_dir: Path,
        reset_file_logging: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A pre-existing RotatingFileHandler must get the ACL rotator.

        If root already has a RotatingFileHandler, setup_file_logging must
        still assign ``_restricting_rotator`` so rotation backups are locked
        down. Do not add a second file handler.
        """
        log_path = temp_dir / "preexisting.log"
        existing = RotatingFileHandler(log_path, encoding="utf-8")
        root = logging.getLogger()
        root.addHandler(existing)
        try:
            assert existing.rotator is not logging_setup_mod._restricting_rotator
            monkeypatch.setattr(
                logging_setup_mod, "_file_logging_configured", False
            )

            setup_file_logging(temp_dir)

            assert existing.rotator is logging_setup_mod._restricting_rotator
            assert len(_rotating_file_handlers()) == 1

            recorded: list[Path] = []

            def record_restrict(path: Path) -> None:
                recorded.append(Path(path))

            monkeypatch.setattr(
                logging_setup_mod, "restrict_file_permissions", record_restrict
            )
            monkeypatch.setattr(
                logging_setup_mod.os, "rename", lambda _src, _dst: None
            )

            dest = temp_dir / "preexisting.log.1"
            existing.rotator(str(log_path), str(dest))
            assert dest in recorded

            setup_file_logging(temp_dir)
            assert len(_rotating_file_handlers()) == 1
        finally:
            root.removeHandler(existing)
            existing.close()

    def test_file_as_log_dir_does_not_raise(
        self, tmp_path: Path, reset_file_logging: None
    ) -> None:
        """If log_dir exists as a file, mkdir fails; startup must not crash.

        Returns the would-be log path even if unused. Does not attach a
        RotatingFileHandler. Leaves ``_file_logging_configured`` False so a
        later call with a real directory can still attach.
        """
        blocked = tmp_path / "not_a_directory"
        blocked.write_text("i-am-a-file", encoding="utf-8")

        returned = setup_file_logging(blocked)

        assert returned == blocked / "ai_context_studio.log"
        assert logging_setup_mod._file_logging_configured is False
        assert _rotating_file_handlers() == []

        later = setup_file_logging(tmp_path)
        assert later == tmp_path / "ai_context_studio.log"
        assert logging_setup_mod._file_logging_configured is True
        assert len(_rotating_file_handlers()) == 1


_FAKE_GEMINI_KEY = "AIzaSyDummyTestKeyNotReal000"


class TestSecretRedaction:
    """API keys must never appear in log records."""

    def test_info_with_fake_gemini_key_is_redacted(
        self, temp_dir: Path, reset_file_logging: None, caplog: pytest.LogCaptureFixture
    ) -> None:
        log_path = setup_file_logging(temp_dir)
        logger = logging.getLogger("ai_context_studio.logging_setup.test")

        with caplog.at_level(logging.INFO):
            logger.info("connecting with %s", _FAKE_GEMINI_KEY)
            for handler in logging.getLogger().handlers:
                handler.flush()

        file_content = log_path.read_text(encoding="utf-8")
        captured = caplog.text + file_content
        assert _FAKE_GEMINI_KEY not in captured
        assert REDACTED in captured

    def test_api_key_assignment_is_redacted(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        log_path = setup_file_logging(temp_dir)
        logger = logging.getLogger("ai_context_studio.logging_setup.test")
        logger.info("config api_key=%s extra", _FAKE_GEMINI_KEY)
        for handler in logging.getLogger().handlers:
            handler.flush()

        content = log_path.read_text(encoding="utf-8")
        assert _FAKE_GEMINI_KEY not in content
        assert f"api_key={REDACTED}" in content

    def test_stream_handler_from_setup_logging_is_covered(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        import io

        stream = io.StringIO()
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        root = logging.getLogger()
        root.addHandler(stream_handler)
        try:
            setup_file_logging(temp_dir)
            logging.getLogger("ai_context_studio.logging_setup.test").info(
                _FAKE_GEMINI_KEY
            )
            stream_handler.flush()
            output = stream.getvalue()
            assert _FAKE_GEMINI_KEY not in output
            assert REDACTED in output
        finally:
            root.removeHandler(stream_handler)
            stream_handler.close()

    def test_root_and_handlers_receive_filter(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        stream_handler = logging.StreamHandler()
        root = logging.getLogger()
        root.addHandler(stream_handler)
        try:
            setup_file_logging(temp_dir)
            assert any(isinstance(f, SecretRedactionFilter) for f in root.filters)
            assert any(
                isinstance(f, SecretRedactionFilter) for f in stream_handler.filters
            )
            for handler in _rotating_file_handlers():
                assert any(
                    isinstance(f, SecretRedactionFilter) for f in handler.filters
                )
        finally:
            root.removeHandler(stream_handler)
            stream_handler.close()

    def test_does_not_duplicate_filter_when_already_attached(
        self, temp_dir: Path, reset_file_logging: None
    ) -> None:
        root = logging.getLogger()
        stream_handler = logging.StreamHandler()
        root.addFilter(SecretRedactionFilter())
        stream_handler.addFilter(SecretRedactionFilter())
        root.addHandler(stream_handler)
        try:
            setup_file_logging(temp_dir)
            ensure_secret_redaction(root)
            assert _redaction_filter_count(root) == 1
            assert _redaction_filter_count(stream_handler) == 1
            for handler in _rotating_file_handlers():
                assert _redaction_filter_count(handler) == 1
        finally:
            root.removeHandler(stream_handler)
            stream_handler.close()

    def test_ensure_secret_redaction_is_idempotent(
        self, reset_file_logging: None
    ) -> None:
        root = logging.getLogger()
        stream_handler = logging.StreamHandler()
        root.addHandler(stream_handler)
        try:
            ensure_secret_redaction(root)
            ensure_secret_redaction(root)
            assert _redaction_filter_count(root) == 1
            assert _redaction_filter_count(stream_handler) == 1
        finally:
            root.removeHandler(stream_handler)
            stream_handler.close()
