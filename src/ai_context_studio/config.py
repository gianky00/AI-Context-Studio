# -*- coding: utf-8 -*-
"""
Configuration management for AI Context Studio.

This module provides a singleton ConfigManager class that handles:
- API key storage with optional encryption
- Application settings persistence
- Model cache management
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .constants import (
    CONFIG_DIR,
    CONFIG_FILE,
    KEY_FILE,
    MODELS_CACHE_FILE,
    MODELS_CACHE_HOURS,
)
from .secret_redaction import redact_secrets

logger = logging.getLogger(__name__)

# Try to import cryptography for encryption support
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.info("Cryptography not available - API keys will be stored in plain text")

try:
    import keyring
except ImportError:
    keyring = None

KEYRING_AVAILABLE = keyring is not None

KEYRING_SERVICE = "ai-context-studio"
KEYRING_USERNAME = "gemini-api-key"

VALID_APPEARANCE_MODES: frozenset[str] = frozenset({"light", "dark", "system"})
DEFAULT_APPEARANCE_MODE: str = "light"


def _sanitize_last_project_path(path: object) -> str:
    """Return *path* only if it is a string with no C0 controls or DEL.

    Newlines, CR, tab, NUL, ESC, other C0 bytes (ord < 32), and DEL (ord 127)
    are rejected wholesale (stored/returned as ``""``). Stripping them would
    concatenate ``C:\\proj\\foo\\nbar`` into a different, surprising path.
    ``str.strip()`` does not remove DEL.
    """
    if not isinstance(path, str):
        return ""
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
        return ""
    return path


def _reject_c0_secret(value: str) -> str:
    """Return ``""`` if *value* contains C0 controls or DEL; otherwise *value*."""
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return ""
    return value


def normalize_appearance_mode(value: object) -> str:
    """Return a valid CustomTkinter appearance mode.

    Accepts case-insensitive ``light``, ``dark``, or ``system``.
    Invalid or non-string values fall back to ``light``.
    """
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in VALID_APPEARANCE_MODES:
            return normalized
    return DEFAULT_APPEARANCE_MODE


def restrict_file_permissions(path: Path) -> None:
    """Restrict a file to the current user (Unix chmod or Windows icacls)."""
    try:
        if os.name != "nt":
            path.chmod(0o600)
            return

        username = os.environ.get("USERNAME") or os.getlogin()
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{username}:(R,W)",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as e:
        logger.warning("Failed to restrict permissions on %s: %s", path, e)


class ConfigManager:
    """
    Singleton class for managing application configuration.

    Handles persistent storage of:
    - API keys (OS keyring when available, Fernet-encrypted file fallback)
    - Application settings
    - Model cache

    Attributes:
        _instance: Singleton instance
        _initialized: Whether initialization has completed
    """

    _instance: Optional['ConfigManager'] = None
    _initialized: bool = False

    def __new__(cls) -> 'ConfigManager':
        """
        Create or return the singleton instance.

        Returns:
            The singleton ConfigManager instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the singleton so tests can construct a fresh manager."""
        cls._instance = None

    def __init__(self) -> None:
        """Initialize the ConfigManager if not already initialized."""
        if self._initialized:
            return

        self._initialized = True
        self._config: dict[str, Any] = {}
        self._cipher: Optional[Any] = None  # Fernet instance

        self._ensure_config_dir()
        self._init_encryption()
        self._load_config()

    def _ensure_config_dir(self) -> None:
        """Create configuration directory if it doesn't exist."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            logger.debug("Config directory ensured: %s", CONFIG_DIR)
        except OSError as e:
            logger.error("Failed to create config directory: %s", e)

    def _init_encryption(self) -> None:
        """Initialize encryption for API key storage."""
        if not CRYPTO_AVAILABLE:
            logger.debug("Encryption not available")
            return

        try:
            if KEY_FILE.exists():
                key = KEY_FILE.read_bytes()
                logger.debug("Loaded existing encryption key")
            else:
                key = Fernet.generate_key()
                KEY_FILE.write_bytes(key)
                logger.info("Generated new encryption key")

            restrict_file_permissions(KEY_FILE)
            self._cipher = Fernet(key)
        except Exception as e:
            logger.warning("Failed to initialize encryption: %s", e)
            self._cipher = None

    def _load_config(self) -> None:
        """Load configuration from disk."""
        if not CONFIG_FILE.exists():
            logger.debug("No existing config file found")
            return

        try:
            content = CONFIG_FILE.read_text(encoding='utf-8')
            self._config = json.loads(content)
            logger.debug("Loaded configuration with %d keys", len(self._config))
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in config file: %s", e)
            self._config = {}
        except OSError as e:
            logger.error("Failed to read config file: %s", e)
            self._config = {}

    def _save_config(self) -> None:
        """Save configuration to disk."""
        try:
            content = json.dumps(self._config, indent=2, ensure_ascii=False)
            CONFIG_FILE.write_text(content, encoding='utf-8')
            logger.debug("Saved configuration")
            if 'api_key' in self._config:
                restrict_file_permissions(CONFIG_FILE)
        except OSError as e:
            logger.error("Failed to save config file: %s", e)

    def get_api_key(self) -> str:
        """
        Retrieve the stored API key.

        Prefers the OS keyring; falls back to Fernet-encrypted config.json.

        Returns:
            Decrypted API key, or empty string if not set.
        """
        if KEYRING_AVAILABLE and keyring is not None:
            try:
                stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
                if stored:
                    return _reject_c0_secret(stored)
            except Exception as e:
                logger.warning(
                    "Failed to read API key from keyring: %s",
                    redact_secrets(str(e)),
                )

        encrypted_key = self._config.get('api_key', '')
        if not encrypted_key:
            return ''

        if self._cipher and CRYPTO_AVAILABLE:
            try:
                decrypted = self._cipher.decrypt(encrypted_key.encode()).decode()
                return _reject_c0_secret(decrypted)
            except Exception as e:
                logger.warning(
                    "Failed to decrypt API key: %s",
                    redact_secrets(str(e)),
                )
                return ""

        return _reject_c0_secret(encrypted_key)

    def set_api_key(self, api_key: object) -> None:
        """
        Store an API key.

        Prefers the OS keyring. On success, removes any leftover api_key from
        config.json. Falls back to Fernet (or plaintext) file storage if the
        keyring is unavailable or fails.

        Whitespace-only values clear the stored key (same as ``""``). Values
        containing C0 controls or DEL are rejected as empty. Non-strings are
        ignored so a bad caller cannot wipe a stored key.

        Args:
            api_key: The API key to store.
        """
        if not isinstance(api_key, str):
            return
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in api_key):
            api_key = ""
        stripped = api_key.strip()

        if KEYRING_AVAILABLE and keyring is not None:
            try:
                keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, stripped)
                if 'api_key' in self._config:
                    del self._config['api_key']
                    self._save_config()
                logger.debug("Stored API key in OS keyring")
                return
            except Exception as e:
                logger.warning(
                    "Failed to store API key in keyring: %s",
                    redact_secrets(str(e)),
                )

        if self._cipher and CRYPTO_AVAILABLE:
            try:
                encrypted = self._cipher.encrypt(stripped.encode()).decode()
                self._config['api_key'] = encrypted
                logger.debug("Stored encrypted API key")
            except Exception as e:
                logger.warning(
                    "Failed to encrypt API key: %s",
                    redact_secrets(str(e)),
                )
                self._config['api_key'] = stripped
        else:
            self._config['api_key'] = stripped
            logger.debug("Stored plain text API key")

        self._save_config()
        restrict_file_permissions(CONFIG_FILE)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key to retrieve.
            default: Default value if key not found.

        Returns:
            The configuration value or default.
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key to set.
            value: Value to store.
        """
        self._config[key] = value
        self._save_config()

    def get_cached_models(self) -> Optional[list[str]]:
        """
        Get cached model list if still valid.

        Returns:
            List of model names if cache is valid, None otherwise.
        """
        if not MODELS_CACHE_FILE.exists():
            return None

        try:
            content = MODELS_CACHE_FILE.read_text(encoding='utf-8')
            cache = json.loads(content)
            cached_time = datetime.fromisoformat(
                cache.get('timestamp', '2000-01-01')
            )

            if datetime.now() - cached_time < timedelta(hours=MODELS_CACHE_HOURS):
                models = cache.get('models', [])
                if not isinstance(models, list):
                    return None
                logger.debug("Returning %d cached models", len(models))
                return models

            logger.debug("Model cache expired")
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning("Failed to read model cache: %s", e)

        return None

    def set_cached_models(self, models: list[str]) -> None:
        """
        Cache the model list.

        Args:
            models: List of model names to cache.
        """
        try:
            cache = {
                'timestamp': datetime.now().isoformat(),
                'models': models
            }
            content = json.dumps(cache, indent=2)
            MODELS_CACHE_FILE.write_text(content, encoding='utf-8')
            logger.debug("Cached %d models", len(models))
            restrict_file_permissions(MODELS_CACHE_FILE)
        except OSError as e:
            logger.warning("Failed to cache models: %s", e)

    def get_last_project_path(self) -> str:
        """
        Get the last opened project path.

        Returns:
            Path string or empty string if not set or if the stored value
            contains C0 controls or DEL (defense against a hand-edited
            config.json).
        """
        return _sanitize_last_project_path(
            self._config.get('last_project_path', '')
        )

    def set_last_project_path(self, path: str) -> None:
        """
        Store the last opened project path.

        Paths containing C0 controls (newline, CR, tab, NUL, ESC, ...) or
        DEL are rejected and stored as an empty string.

        Args:
            path: Project path to store.
        """
        self._config['last_project_path'] = _sanitize_last_project_path(path)
        self._save_config()

    def get_appearance_mode(self) -> str:
        """Return persisted appearance mode, defaulting to light."""
        return normalize_appearance_mode(
            self._config.get("appearance_mode", DEFAULT_APPEARANCE_MODE)
        )

    def set_appearance_mode(self, mode: str) -> None:
        """Persist appearance mode after normalizing to light/dark/system."""
        self._config["appearance_mode"] = normalize_appearance_mode(mode)
        self._save_config()

    def is_first_run(self) -> bool:
        """
        Check if this is the first application run.

        Returns:
            True if onboarding hasn't been completed.
        """
        return not self._config.get('onboarding_completed', False)

    def set_onboarding_completed(self) -> None:
        """Mark onboarding as completed."""
        self._config['onboarding_completed'] = True
        self._save_config()
