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

logger = logging.getLogger(__name__)

# Try to import cryptography for encryption support
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.info("Cryptography not available - API keys will be stored in plain text")


class ConfigManager:
    """
    Singleton class for managing application configuration.

    Handles persistent storage of:
    - API keys (with optional encryption)
    - Application settings
    - Model cache

    Attributes:
        _instance: Singleton instance
        _initialized: Whether initialization has completed
    """

    _instance: Optional['ConfigManager'] = None

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
                # Set restrictive permissions on Unix-like systems
                if os.name != 'nt':
                    KEY_FILE.chmod(0o600)
                logger.info("Generated new encryption key")

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
        except OSError as e:
            logger.error("Failed to save config file: %s", e)

    def get_api_key(self) -> str:
        """
        Retrieve the stored API key.

        Returns:
            Decrypted API key, or empty string if not set.
        """
        encrypted_key = self._config.get('api_key', '')
        if not encrypted_key:
            return ''

        if self._cipher and CRYPTO_AVAILABLE:
            try:
                return self._cipher.decrypt(encrypted_key.encode()).decode()
            except Exception as e:
                logger.warning("Failed to decrypt API key: %s", e)
                # Fall back to treating as plain text
                return encrypted_key

        return encrypted_key

    def set_api_key(self, api_key: str) -> None:
        """
        Store an API key.

        Args:
            api_key: The API key to store.
        """
        if self._cipher and CRYPTO_AVAILABLE:
            try:
                encrypted = self._cipher.encrypt(api_key.encode()).decode()
                self._config['api_key'] = encrypted
                logger.debug("Stored encrypted API key")
            except Exception as e:
                logger.warning("Failed to encrypt API key: %s", e)
                self._config['api_key'] = api_key
        else:
            self._config['api_key'] = api_key
            logger.debug("Stored plain text API key")

        self._save_config()

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
        except OSError as e:
            logger.warning("Failed to cache models: %s", e)

    def get_last_project_path(self) -> str:
        """
        Get the last opened project path.

        Returns:
            Path string or empty string if not set.
        """
        return self._config.get('last_project_path', '')

    def set_last_project_path(self, path: str) -> None:
        """
        Store the last opened project path.

        Args:
            path: Project path to store.
        """
        self._config['last_project_path'] = path
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
