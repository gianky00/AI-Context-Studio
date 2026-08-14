# -*- coding: utf-8 -*-
"""Tests for Windows launcher scripts (bat / pyw).

Reads ``Avvia_AI_Context_Studio.bat`` and ``launcher.pyw`` as text.
Does not execute pythonw, does not start the Tk GUI, and does not call
paid Gemini APIs.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from ai_context_studio.constants import APP_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]
BAT_PATH = REPO_ROOT / "Avvia_AI_Context_Studio.bat"
LAUNCHER_PYW = REPO_ROOT / "launcher.pyw"

# Real Gemini / Google API keys look like AIza... (not documentation words).
_GEMINI_API_KEY = re.compile(r"AIza[0-9A-Za-z_\-]{10,}")
# OpenAI-style live keys must not be baked into launchers.
_OPENAI_LIVE_KEY = re.compile(r"sk-[A-Za-z0-9]{20,}")
_HARDCODED_WIN_PATH = re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE)
_SEMVER = re.compile(r"\bv(\d+\.\d+\.\d+)\b")
_INVOKES_PACKAGE = re.compile(
    r"pythonw|python\s+-m\s+ai_context_studio",
    re.IGNORECASE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_no_real_api_key(text: str, label: str) -> None:
    gemini = _GEMINI_API_KEY.search(text)
    assert gemini is None, f"{label} must not contain a Gemini API key"
    openai = _OPENAI_LIVE_KEY.search(text)
    assert openai is None, f"{label} must not contain an API key"


class TestBatLauncher:
    """``Avvia_AI_Context_Studio.bat`` must exist and launch the package."""

    def test_bat_file_exists(self) -> None:
        assert BAT_PATH.is_file()

    def test_bat_contains_pythonw_or_python_dash_m(self) -> None:
        text = _read(BAT_PATH)
        assert _INVOKES_PACKAGE.search(text) is not None

    def test_bat_does_not_contain_real_api_key(self) -> None:
        _assert_no_real_api_key(_read(BAT_PATH), "bat")

    def test_bat_uses_script_dir_not_hardcoded_user_path(self) -> None:
        text = _read(BAT_PATH)
        assert "%~dp0" in text
        assert _HARDCODED_WIN_PATH.search(text) is None

    def test_bat_does_not_call_paid_gemini_sdk(self) -> None:
        text = _read(BAT_PATH).lower()
        assert "google.generativeai" not in text
        assert "google.genai" not in text
        assert "generativelanguage.googleapis.com" not in text

    def test_bat_points_at_launcher_pyw(self) -> None:
        text = _read(BAT_PATH)
        assert "launcher.pyw" in text
        assert "pythonw" in text.lower()

    def test_bat_echoed_version_matches_package(self) -> None:
        match = _SEMVER.search(_read(BAT_PATH))
        if match is not None:
            assert match.group(1) == APP_VERSION


class TestLauncherPyw:
    """``launcher.pyw`` is a thin, import-safe wrapper around the package."""

    def test_launcher_pyw_exists(self) -> None:
        assert LAUNCHER_PYW.is_file()

    def test_launcher_invokes_package_entry(self) -> None:
        text = _read(LAUNCHER_PYW)
        assert "ai_context_studio" in text
        assert "main" in text

    def test_launcher_does_not_contain_real_api_key(self) -> None:
        _assert_no_real_api_key(_read(LAUNCHER_PYW), "launcher.pyw")

    def test_launcher_does_not_call_paid_apis(self) -> None:
        text = _read(LAUNCHER_PYW)
        lowered = text.lower()
        assert "google.genai" not in lowered
        assert "google.generativeai" not in lowered
        assert "gemini" not in lowered
        assert "Client(" not in text
        assert "generate_content" not in text

    def test_launcher_is_guarded_against_import_side_effects(self) -> None:
        text = _read(LAUNCHER_PYW)
        assert '__name__ == "__main__"' in text

    def test_importing_launcher_does_not_start_gui(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "acs_windows_launcher", LAUNCHER_PYW
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert isinstance(module, ModuleType)
        assert callable(getattr(module, "main", None))
