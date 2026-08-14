# -*- coding: utf-8 -*-
"""
Offline unit tests for the application entry point.

Does not launch the CustomTkinter GUI. File logging is mocked so tests
never write under the real ~/.ai_context_studio directory.
"""

from __future__ import annotations

import logging
import sys
from typing import Generator
from unittest.mock import MagicMock

import pytest

from ai_context_studio import main as main_mod


@pytest.fixture
def reset_root_logging() -> Generator[logging.Logger, None, None]:
    """Restore root logger handlers/level after each test.

    ``logging.basicConfig`` is a no-op when handlers already exist (pytest
    attaches a capture handler). Tests must clear handlers immediately
    before calling ``setup_logging``.
    """
    root = logging.getLogger()
    old_level = root.level
    old_handlers = list(root.handlers)
    yield root
    for handler in list(root.handlers):
        if handler not in old_handlers:
            root.removeHandler(handler)
            handler.close()
    root.handlers.clear()
    for handler in old_handlers:
        root.addHandler(handler)
    root.setLevel(old_level)


@pytest.fixture
def mock_file_logging(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace setup_file_logging so tests do not touch the real config dir."""
    mock = MagicMock(name="setup_file_logging")
    monkeypatch.setattr(main_mod, "setup_file_logging", mock)
    return mock


class TestSetupLogging:
    """Tests for setup_logging."""

    def test_debug_false_sets_root_level_info(
        self,
        reset_root_logging: logging.Logger,
        mock_file_logging: MagicMock,
    ) -> None:
        root = reset_root_logging
        root.handlers.clear()
        root.setLevel(logging.WARNING)

        main_mod.setup_logging(debug=False)

        assert root.level == logging.INFO
        mock_file_logging.assert_called_once_with(
            main_mod.CONFIG_DIR / "logs", debug=False
        )

    def test_debug_true_sets_root_level_debug(
        self,
        reset_root_logging: logging.Logger,
        mock_file_logging: MagicMock,
    ) -> None:
        root = reset_root_logging
        root.handlers.clear()
        root.setLevel(logging.WARNING)

        main_mod.setup_logging(debug=True)

        assert root.level == logging.DEBUG
        mock_file_logging.assert_called_once_with(
            main_mod.CONFIG_DIR / "logs", debug=True
        )


class TestCheckDependencies:
    """Tests for check_dependencies with mocked imports."""

    def test_both_present_returns_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "customtkinter", MagicMock())
        monkeypatch.setitem(sys.modules, "google", MagicMock())
        monkeypatch.setitem(sys.modules, "google.genai", MagicMock())

        assert main_mod.check_dependencies() is True

    def test_missing_customtkinter_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "customtkinter", None)
        monkeypatch.setitem(sys.modules, "google", MagicMock())
        monkeypatch.setitem(sys.modules, "google.genai", MagicMock())

        assert main_mod.check_dependencies() is False

    def test_missing_google_genai_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "customtkinter", MagicMock())
        monkeypatch.setitem(sys.modules, "google.genai", None)

        assert main_mod.check_dependencies() is False


class TestPrintBanner:
    """Tests for print_banner."""

    def test_contains_app_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        main_mod.print_banner()
        captured = capsys.readouterr()
        assert main_mod.APP_NAME in captured.out

    def test_contains_app_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        main_mod.print_banner()
        captured = capsys.readouterr()
        assert main_mod.APP_VERSION in captured.out
        assert f"v{main_mod.APP_VERSION}" in captured.out

    def test_contains_app_author(self, capsys: pytest.CaptureFixture[str]) -> None:
        main_mod.print_banner()
        captured = capsys.readouterr()
        assert main_mod.APP_AUTHOR in captured.out
        assert f"by {main_mod.APP_AUTHOR}" in captured.out


class TestMain:
    """Tests for main() that never open a GUI window."""

    def test_returns_1_when_dependencies_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(main_mod, "setup_logging", lambda debug=False: None)
        monkeypatch.setattr(main_mod, "print_banner", lambda: None)
        monkeypatch.setattr(main_mod, "check_dependencies", lambda: False)

        assert main_mod.main() == 1

    @pytest.mark.parametrize("flag", ["--debug", "-d"])
    def test_debug_flag_enables_file_logging_without_mainloop(
        self,
        flag: str,
        monkeypatch: pytest.MonkeyPatch,
        mock_file_logging: MagicMock,
        reset_root_logging: logging.Logger,
    ) -> None:
        root = reset_root_logging
        root.handlers.clear()
        monkeypatch.setattr(sys, "argv", ["prog", flag])
        monkeypatch.setattr(main_mod, "print_banner", lambda: None)
        monkeypatch.setattr(main_mod, "check_dependencies", lambda: False)
        mock_app_cls = MagicMock(name="AIContextStudioApp")
        monkeypatch.setitem(
            sys.modules,
            "ai_context_studio.app",
            MagicMock(AIContextStudioApp=mock_app_cls),
        )

        assert main_mod.main() == 1
        mock_file_logging.assert_called_once_with(
            main_mod.CONFIG_DIR / "logs", debug=True
        )
        mock_app_cls.assert_not_called()
        mock_app_cls.return_value.mainloop.assert_not_called()

    def test_without_debug_flag_file_logging_info_without_mainloop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_file_logging: MagicMock,
        reset_root_logging: logging.Logger,
    ) -> None:
        root = reset_root_logging
        root.handlers.clear()
        monkeypatch.setattr(sys, "argv", ["prog"])
        monkeypatch.setattr(main_mod, "print_banner", lambda: None)
        monkeypatch.setattr(main_mod, "check_dependencies", lambda: False)
        mock_app_cls = MagicMock(name="AIContextStudioApp")
        monkeypatch.setitem(
            sys.modules,
            "ai_context_studio.app",
            MagicMock(AIContextStudioApp=mock_app_cls),
        )

        assert main_mod.main() == 1
        mock_file_logging.assert_called_once_with(
            main_mod.CONFIG_DIR / "logs", debug=False
        )
        mock_app_cls.assert_not_called()
        mock_app_cls.return_value.mainloop.assert_not_called()

    def test_returns_0_when_mocked_app_closes_normally(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_file_logging: MagicMock,
        reset_root_logging: logging.Logger,
    ) -> None:
        root = reset_root_logging
        root.handlers.clear()
        monkeypatch.setattr(sys, "argv", ["prog"])
        monkeypatch.setattr(main_mod, "print_banner", lambda: None)
        monkeypatch.setattr(main_mod, "check_dependencies", lambda: True)
        mock_app = MagicMock(name="app_instance")
        mock_app_cls = MagicMock(name="AIContextStudioApp", return_value=mock_app)
        monkeypatch.setitem(
            sys.modules,
            "ai_context_studio.app",
            MagicMock(AIContextStudioApp=mock_app_cls),
        )

        assert main_mod.main() == 0
        mock_file_logging.assert_called_once_with(
            main_mod.CONFIG_DIR / "logs", debug=False
        )
        mock_app_cls.assert_called_once_with()
        mock_app.mainloop.assert_called_once_with()

    def test_returns_1_when_app_ctor_raises_generic_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(main_mod, "setup_logging", lambda debug=False: None)
        monkeypatch.setattr(main_mod, "print_banner", lambda: None)
        monkeypatch.setattr(main_mod, "check_dependencies", lambda: True)
        logger = logging.getLogger(main_mod.__name__)
        mock_exception = MagicMock(name="logger.exception")
        monkeypatch.setattr(logger, "exception", mock_exception)
        mock_app_cls = MagicMock(
            name="AIContextStudioApp", side_effect=RuntimeError("boom")
        )
        monkeypatch.setitem(
            sys.modules,
            "ai_context_studio.app",
            MagicMock(AIContextStudioApp=mock_app_cls),
        )

        assert main_mod.main() == 1
        mock_exception.assert_called_once()
        assert "Fatal error" in mock_exception.call_args[0][0]

    def test_returns_0_when_app_ctor_raises_keyboard_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(main_mod, "setup_logging", lambda debug=False: None)
        monkeypatch.setattr(main_mod, "print_banner", lambda: None)
        monkeypatch.setattr(main_mod, "check_dependencies", lambda: True)
        logger = logging.getLogger(main_mod.__name__)
        mock_exception = MagicMock(name="logger.exception")
        monkeypatch.setattr(logger, "exception", mock_exception)
        mock_app_cls = MagicMock(
            name="AIContextStudioApp", side_effect=KeyboardInterrupt
        )
        monkeypatch.setitem(
            sys.modules,
            "ai_context_studio.app",
            MagicMock(AIContextStudioApp=mock_app_cls),
        )

        assert main_mod.main() == 0
        mock_exception.assert_not_called()

    def test_returns_0_when_mainloop_raises_keyboard_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(main_mod, "setup_logging", lambda debug=False: None)
        monkeypatch.setattr(main_mod, "print_banner", lambda: None)
        monkeypatch.setattr(main_mod, "check_dependencies", lambda: True)
        logger = logging.getLogger(main_mod.__name__)
        mock_exception = MagicMock(name="logger.exception")
        monkeypatch.setattr(logger, "exception", mock_exception)
        mock_app = MagicMock(name="app_instance")
        mock_app.mainloop.side_effect = KeyboardInterrupt
        mock_app_cls = MagicMock(name="AIContextStudioApp", return_value=mock_app)
        monkeypatch.setitem(
            sys.modules,
            "ai_context_studio.app",
            MagicMock(AIContextStudioApp=mock_app_cls),
        )

        assert main_mod.main() == 0
        mock_exception.assert_not_called()
