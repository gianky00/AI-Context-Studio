# -*- coding: utf-8 -*-
"""Tests for ConfigManager."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from ai_context_studio import config as config_mod
from ai_context_studio.config import (
    CRYPTO_AVAILABLE,
    ConfigManager,
    normalize_appearance_mode,
    restrict_file_permissions,
)


class _MemoryKeyring:
    """In-memory stand-in so tests never touch the OS credential vault."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}
        self.set_error: Optional[Exception] = None
        self.get_error: Optional[Exception] = None

    def get_password(self, service: str, username: str) -> Optional[str]:
        if self.get_error is not None:
            raise self.get_error
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        if self.set_error is not None:
            raise self.set_error
        self._store[(service, username)] = password


@pytest.fixture(autouse=True)
def _never_call_real_icacls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub subprocess.run so tests never invoke real icacls on the profile."""

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = list(args[0]) if args else []  # type: ignore[arg-type]
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(config_mod.subprocess, "run", fake_run)


@pytest.fixture(autouse=True)
def memory_keyring(monkeypatch: pytest.MonkeyPatch) -> _MemoryKeyring:
    vault = _MemoryKeyring()
    monkeypatch.setattr(config_mod, "KEYRING_AVAILABLE", True)
    monkeypatch.setattr(config_mod, "keyring", vault)
    return vault


class TestConfigManager:
    """Tests for configuration persistence and API key handling."""

    def test_singleton(self, mock_config_dir: Path) -> None:
        first = ConfigManager()
        second = ConfigManager()
        assert first is second

    def test_reset_instance_creates_new(self, mock_config_dir: Path) -> None:
        first = ConfigManager()
        ConfigManager.reset_instance()
        second = ConfigManager()
        assert first is not second

    def test_set_and_get_value(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        config.set("theme", "dark")
        assert config.get("theme") == "dark"
        assert (mock_config_dir / "config.json").exists()

    def test_get_missing_returns_default(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        assert config.get("missing", "fallback") == "fallback"

    def test_api_key_roundtrip_via_keyring(
        self, mock_config_dir: Path, memory_keyring: _MemoryKeyring
    ) -> None:
        config = ConfigManager()
        config.set("api_key", "legacy-copy")
        config.set_api_key("test-secret-key")

        assert config.get_api_key() == "test-secret-key"
        assert (
            memory_keyring.get_password("ai-context-studio", "gemini-api-key")
            == "test-secret-key"
        )
        assert config.get("api_key") is None

    def test_api_key_fallback_when_keyring_raises(
        self, mock_config_dir: Path, memory_keyring: _MemoryKeyring
    ) -> None:
        memory_keyring.set_error = RuntimeError("keyring backend failed")
        memory_keyring.get_error = RuntimeError("keyring backend failed")

        config = ConfigManager()
        config.set_api_key("fallback-secret")
        assert config.get_api_key() == "fallback-secret"

        if CRYPTO_AVAILABLE:
            stored = config.get("api_key")
            assert stored != "fallback-secret"
            assert (mock_config_dir / ".keyfile").exists()

    def test_decrypt_failure_returns_empty(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        config.set("api_key", "not-valid-fernet-ciphertext")
        if CRYPTO_AVAILABLE and config._cipher:
            assert config.get_api_key() == ""
        else:
            assert config.get_api_key() == "not-valid-fernet-ciphertext"

    def test_empty_api_key(
        self, mock_config_dir: Path, memory_keyring: _MemoryKeyring
    ) -> None:
        config = ConfigManager()
        assert config.get_api_key() == ""

    def test_set_api_key_empty_string(
        self, mock_config_dir: Path, memory_keyring: _MemoryKeyring
    ) -> None:
        config = ConfigManager()
        config.set_api_key("temporary-key")
        assert config.get_api_key() == "temporary-key"
        config.set_api_key("")
        assert config.get_api_key() == ""

    def test_set_api_key_whitespace_only_clears(
        self, mock_config_dir: Path, memory_keyring: _MemoryKeyring
    ) -> None:
        config = ConfigManager()
        config.set_api_key("test-secret-key")
        assert config.get_api_key() == "test-secret-key"
        config.set_api_key("   ")
        assert config.get_api_key() == ""
        stored = memory_keyring.get_password("ai-context-studio", "gemini-api-key")
        assert stored in (None, "")

    @pytest.mark.parametrize("unsafe", ["k\x00", "k\n", "k\t"])
    def test_set_api_key_c0_controls_clear(
        self,
        mock_config_dir: Path,
        memory_keyring: _MemoryKeyring,
        unsafe: str,
    ) -> None:
        config = ConfigManager()
        config.set_api_key("test-secret-key")
        assert config.get_api_key() == "test-secret-key"
        config.set_api_key(unsafe)
        assert config.get_api_key() == ""
        stored = memory_keyring.get_password("ai-context-studio", "gemini-api-key")
        assert stored in (None, "")
        if stored:
            assert "\x00" not in stored
            assert "\n" not in stored
            assert "\t" not in stored

    @pytest.mark.parametrize("bad", [None, 123])
    def test_set_api_key_non_str_leaves_previous(
        self,
        mock_config_dir: Path,
        memory_keyring: _MemoryKeyring,
        bad: object,
    ) -> None:
        config = ConfigManager()
        config.set_api_key("test-secret-key")
        config.set_api_key(bad)  # type: ignore[arg-type]
        assert config.get_api_key() == "test-secret-key"

    def test_get_api_key_rejects_stored_c0(
        self, mock_config_dir: Path, memory_keyring: _MemoryKeyring
    ) -> None:
        memory_keyring.set_password(
            "ai-context-studio", "gemini-api-key", "k\x00"
        )
        config = ConfigManager()
        assert config.get_api_key() == ""

    def test_get_api_key_rejects_stored_del(
        self, mock_config_dir: Path, memory_keyring: _MemoryKeyring
    ) -> None:
        memory_keyring.set_password(
            "ai-context-studio", "gemini-api-key", "k\x7f"
        )
        config = ConfigManager()
        assert config.get_api_key() == ""

    def test_last_project_path(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        config.set_last_project_path("C:\\Projects\\Demo")
        assert config.get_last_project_path() == "C:\\Projects\\Demo"

    def test_last_project_path_normal_roundtrip(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        path = "C:\\Users\\gianc\\proj"
        config.set_last_project_path(path)
        assert config.get_last_project_path() == path
        stored = json.loads((mock_config_dir / "config.json").read_text(encoding="utf-8"))
        assert stored["last_project_path"] == path

    @pytest.mark.parametrize(
        "unsafe",
        [
            "C:\\proj\\foo\nbar",
            "C:\\proj\\foo\x00bar",
            "C:\\proj\\foo\x1bbar",
            "C:\\proj\\foo\rbar",
            "C:\\proj\\foo\tbar",
            "C:\\proj\\foo\x7fbar",
        ],
    )
    def test_set_last_project_path_rejects_c0_controls(
        self, mock_config_dir: Path, unsafe: str
    ) -> None:
        config = ConfigManager()
        config.set_last_project_path(unsafe)
        assert config.get_last_project_path() == ""
        stored = json.loads((mock_config_dir / "config.json").read_text(encoding="utf-8"))
        assert stored["last_project_path"] == ""
        assert "\n" not in stored["last_project_path"]
        assert "\x00" not in stored["last_project_path"]
        assert "\x1b" not in stored["last_project_path"]

    def test_get_last_project_path_rejects_hand_edited_c0(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "config.json").write_text(
            json.dumps({"last_project_path": "C:\\proj\\foo\nbar"}),
            encoding="utf-8",
        )
        ConfigManager.reset_instance()
        config = ConfigManager()
        assert config.get_last_project_path() == ""

    def test_get_last_project_path_rejects_hand_edited_nul(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "config.json").write_text(
            json.dumps({"last_project_path": "C:\\proj\\foo\x00bar"}),
            encoding="utf-8",
        )
        ConfigManager.reset_instance()
        config = ConfigManager()
        assert config.get_last_project_path() == ""

    def test_get_last_project_path_rejects_hand_edited_del(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "config.json").write_text(
            json.dumps({"last_project_path": "C:\\proj\\foo\x7fbar"}),
            encoding="utf-8",
        )
        ConfigManager.reset_instance()
        config = ConfigManager()
        assert config.get_last_project_path() == ""

    def test_onboarding_flag(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        assert config.is_first_run() is True
        config.set_onboarding_completed()
        assert config.is_first_run() is False

    def test_model_cache_roundtrip(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        assert config.get_cached_models() is None
        config.set_cached_models(["gemini-2.0-flash", "gemini-1.5-pro"])
        cached = config.get_cached_models()
        assert cached == ["gemini-2.0-flash", "gemini-1.5-pro"]

    def test_expired_model_cache_returns_none(self, mock_config_dir: Path) -> None:
        stale = (datetime.now() - timedelta(hours=48)).isoformat()
        (mock_config_dir / "models_cache.json").write_text(
            json.dumps({"timestamp": stale, "models": ["stale-model"]}),
            encoding="utf-8",
        )
        config = ConfigManager()
        assert config.get_cached_models() is None

    @pytest.mark.parametrize(
        "models",
        [
            "gemini-2.5-flash",
            {"name": "x"},
            123,
        ],
    )
    def test_get_cached_models_non_list_is_cache_miss(
        self, mock_config_dir: Path, models: object
    ) -> None:
        (mock_config_dir / "models_cache.json").write_text(
            json.dumps(
                {"timestamp": datetime.now().isoformat(), "models": models}
            ),
            encoding="utf-8",
        )
        config = ConfigManager()
        assert config.get_cached_models() is None

    def test_get_cached_models_fresh_list_returns_list(
        self, mock_config_dir: Path
    ) -> None:
        (mock_config_dir / "models_cache.json").write_text(
            json.dumps(
                {
                    "timestamp": datetime.now().isoformat(),
                    "models": ["gemini-2.0-flash"],
                }
            ),
            encoding="utf-8",
        )
        config = ConfigManager()
        assert config.get_cached_models() == ["gemini-2.0-flash"]

    def test_set_cached_models_restricts_cache_file(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = ConfigManager()
        recorded = self._record_restrict(monkeypatch)

        config.set_cached_models(["gemini-2.0-flash"])

        expected = mock_config_dir / "models_cache.json"
        assert any(Path(p).resolve() == expected.resolve() for p in recorded)

    def test_set_cached_models_oserror_does_not_restrict(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = ConfigManager()
        recorded = self._record_restrict(monkeypatch)

        original_write = Path.write_text

        def fail_write(self: Path, *args: object, **kwargs: object) -> int:
            if self == config_mod.MODELS_CACHE_FILE:
                raise OSError("disk full")
            return original_write(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_write)

        config.set_cached_models(["gemini-2.0-flash"])

        assert recorded == []

    def test_invalid_json_config_resets(self, mock_config_dir: Path) -> None:
        (mock_config_dir / "config.json").write_text("{not-json", encoding="utf-8")
        ConfigManager.reset_instance()
        config = ConfigManager()
        assert config.get("anything") is None

    def test_keyring_error_does_not_log_api_key(
        self,
        mock_config_dir: Path,
        memory_keyring: _MemoryKeyring,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        secret = "AIzaSyDummyTestKeyNotReal000"
        memory_keyring.set_error = RuntimeError(f"cannot store {secret}")

        config = ConfigManager()
        with caplog.at_level(logging.DEBUG):
            config.set_api_key(secret)

        assert secret not in caplog.text
        assert "[REDACTED]" in caplog.text

    def _force_file_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config_mod, "KEYRING_AVAILABLE", False)
        monkeypatch.setattr(config_mod, "keyring", None)

    def _record_restrict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[Path]:
        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(Path(path))

        monkeypatch.setattr(config_mod, "restrict_file_permissions", record_restrict)
        return recorded

    def test_plaintext_fallback_restricts_config_file(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._force_file_fallback(monkeypatch)
        config = ConfigManager()
        config._cipher = None
        recorded = self._record_restrict(monkeypatch)

        config.set_api_key("plain-fallback-secret")

        expected = mock_config_dir / "config.json"
        assert any(Path(p).resolve() == expected.resolve() for p in recorded)
        assert config.get("api_key") == "plain-fallback-secret"

    def test_encrypted_file_fallback_restricts_config_file(
        self, mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._force_file_fallback(monkeypatch)
        config = ConfigManager()
        if not (CRYPTO_AVAILABLE and config._cipher):
            pytest.skip("cryptography not available")
        recorded = self._record_restrict(monkeypatch)

        config.set_api_key("encrypted-fallback-secret")

        expected = mock_config_dir / "config.json"
        assert any(Path(p).resolve() == expected.resolve() for p in recorded)
        assert config.get("api_key") != "encrypted-fallback-secret"

    def test_keyring_success_does_not_restrict_config_file(
        self,
        mock_config_dir: Path,
        memory_keyring: _MemoryKeyring,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        recorded: list[Path] = []

        def record_restrict(path: Path) -> None:
            recorded.append(path)

        monkeypatch.setattr(config_mod, "restrict_file_permissions", record_restrict)

        config = ConfigManager()
        config.set("api_key", "legacy-copy")
        recorded.clear()
        config.set_api_key("test-secret-key")

        assert config_mod.CONFIG_FILE not in recorded
        assert config.get("api_key") is None

    def test_appearance_mode_defaults_to_light(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        assert config.get_appearance_mode() == "light"
        assert config.get("appearance_mode") is None

    def test_appearance_mode_roundtrip(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        config.set_appearance_mode("dark")
        assert config.get_appearance_mode() == "dark"
        assert config.get("appearance_mode") == "dark"

        ConfigManager.reset_instance()
        reloaded = ConfigManager()
        assert reloaded.get_appearance_mode() == "dark"

    def test_appearance_mode_normalizes_case(self, mock_config_dir: Path) -> None:
        config = ConfigManager()
        config.set_appearance_mode("SYSTEM")
        assert config.get_appearance_mode() == "system"
        assert config.get("appearance_mode") == "system"

    def test_appearance_mode_invalid_falls_back_to_light(
        self, mock_config_dir: Path
    ) -> None:
        config = ConfigManager()
        config.set_appearance_mode("neon")
        assert config.get_appearance_mode() == "light"
        assert config.get("appearance_mode") == "light"

        config.set("appearance_mode", "not-a-theme")
        assert config.get_appearance_mode() == "light"


class TestNormalizeAppearanceMode:
    """Pure helper: no ConfigManager or Tk required."""

    def test_valid_values(self) -> None:
        assert normalize_appearance_mode("light") == "light"
        assert normalize_appearance_mode("dark") == "dark"
        assert normalize_appearance_mode("system") == "system"

    def test_case_insensitive(self) -> None:
        assert normalize_appearance_mode("Light") == "light"
        assert normalize_appearance_mode("DARK") == "dark"
        assert normalize_appearance_mode("SyStEm") == "system"

    def test_strips_whitespace(self) -> None:
        assert normalize_appearance_mode("  dark  ") == "dark"

    def test_invalid_and_non_string_fallback(self) -> None:
        assert normalize_appearance_mode("") == "light"
        assert normalize_appearance_mode("neon") == "light"
        assert normalize_appearance_mode(None) == "light"
        assert normalize_appearance_mode(123) == "light"


class TestRestrictFilePermissions:
    """restrict_file_permissions must not call real icacls in tests."""

    def test_non_nt_chmod_600(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config_mod.os, "name", "posix")
        fake_run = MagicMock(side_effect=AssertionError("icacls must not run on posix"))
        monkeypatch.setattr(config_mod.subprocess, "run", fake_run)

        fake_path = MagicMock()
        restrict_file_permissions(fake_path)

        fake_path.chmod.assert_called_once_with(0o600)
        fake_run.assert_not_called()

    def test_nt_builds_icacls_args_with_username(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        recorded: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            recorded["args"] = list(args[0])  # type: ignore[arg-type]
            recorded["kwargs"] = kwargs
            argv = list(args[0])  # type: ignore[arg-type]
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(config_mod.os, "name", "nt")
        monkeypatch.setenv("USERNAME", "Alice")
        monkeypatch.setattr(config_mod.subprocess, "run", fake_run)

        target = tmp_path / "keyfile"
        target.write_text("x", encoding="utf-8")
        restrict_file_permissions(target)

        argv = recorded["args"]
        assert isinstance(argv, list)
        assert argv[0] == "icacls"
        assert str(target) in argv
        assert "/inheritance:r" in argv
        assert "/grant:r" in argv
        assert "Alice:(R,W)" in argv
        kwargs = recorded["kwargs"]
        assert isinstance(kwargs, dict)
        assert kwargs.get("capture_output") is True
        assert kwargs.get("check") is False

    def test_oserror_is_logged_not_raised(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(config_mod.os, "name", "posix")
        fake_path = MagicMock()
        fake_path.chmod.side_effect = OSError("permission denied")

        with caplog.at_level(logging.WARNING):
            restrict_file_permissions(fake_path)

        assert "Failed to restrict permissions" in caplog.text
        assert "permission denied" in caplog.text
