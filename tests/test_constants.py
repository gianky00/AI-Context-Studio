# -*- coding: utf-8 -*-
"""
Tests for constants module.
"""

from __future__ import annotations

import pytest

from ai_context_studio.constants import (
    APP_AUTHOR,
    APP_NAME,
    APP_VERSION,
    COLORS,
    CONFIG_DIR,
    DEFAULT_IGNORED_DIRS,
    FILE_ICONS,
    MAX_FILE_SIZE,
    MAX_SCAN_DEPTH,
    SUPPORTED_EXTENSIONS,
    TOKEN_FACTOR,
)


class TestAppConstants:
    """Tests for application metadata constants."""

    def test_app_name_is_string(self) -> None:
        """App name should be a non-empty string."""
        assert isinstance(APP_NAME, str)
        assert len(APP_NAME) > 0

    def test_app_version_format(self) -> None:
        """App version should follow semantic versioning."""
        assert isinstance(APP_VERSION, str)
        parts = APP_VERSION.split(".")
        assert len(parts) >= 2
        for part in parts:
            assert part.isdigit()

    def test_app_author_is_string(self) -> None:
        """App author should be a non-empty string."""
        assert isinstance(APP_AUTHOR, str)
        assert len(APP_AUTHOR) > 0


class TestFileConstants:
    """Tests for file-related constants."""

    def test_supported_extensions_not_empty(self) -> None:
        """Supported extensions should not be empty."""
        assert len(SUPPORTED_EXTENSIONS) > 0

    def test_supported_extensions_are_lowercase(self) -> None:
        """All extensions should be lowercase with dot prefix."""
        for ext in SUPPORTED_EXTENSIONS:
            assert ext.startswith(".")
            assert ext == ext.lower()

    def test_common_extensions_included(self) -> None:
        """Common programming file extensions should be included."""
        common = {'.py', '.js', '.ts', '.html', '.css', '.json'}
        for ext in common:
            assert ext in SUPPORTED_EXTENSIONS

    def test_ignored_dirs_not_empty(self) -> None:
        """Ignored directories should not be empty."""
        assert len(DEFAULT_IGNORED_DIRS) > 0

    def test_common_ignored_dirs_included(self) -> None:
        """Common ignored directories should be included."""
        common = {'node_modules', '__pycache__', '.git', 'venv'}
        for dirname in common:
            assert dirname in DEFAULT_IGNORED_DIRS


class TestConfigConstants:
    """Tests for configuration constants."""

    def test_config_dir_is_path(self) -> None:
        """Config directory should be a Path object."""
        from pathlib import Path
        assert isinstance(CONFIG_DIR, Path)

    def test_token_factor_is_positive(self) -> None:
        """Token factor should be a positive integer."""
        assert isinstance(TOKEN_FACTOR, int)
        assert TOKEN_FACTOR > 0

    def test_max_file_size_is_reasonable(self) -> None:
        """Max file size should be between 100KB and 10MB."""
        assert MAX_FILE_SIZE >= 100_000
        assert MAX_FILE_SIZE <= 10_000_000

    def test_max_scan_depth_is_reasonable(self) -> None:
        """Max scan depth should be between 5 and 100."""
        assert MAX_SCAN_DEPTH >= 5
        assert MAX_SCAN_DEPTH <= 100


class TestColorConstants:
    """Tests for color scheme constants."""

    def test_colors_is_dict(self) -> None:
        """Colors should be a dictionary."""
        assert isinstance(COLORS, dict)

    def test_colors_not_empty(self) -> None:
        """Colors dict should not be empty."""
        assert len(COLORS) > 0

    def test_color_values_are_hex(self) -> None:
        """All color values should be valid hex codes."""
        for name, color in COLORS.items():
            assert isinstance(color, str), f"{name} is not a string"
            assert color.startswith("#"), f"{name} doesn't start with #"
            assert len(color) == 7, f"{name} is not 7 characters"

    def test_essential_colors_present(self) -> None:
        """Essential color keys should be present."""
        essential = {'primary', 'success', 'warning', 'danger'}
        for color_name in essential:
            assert color_name in COLORS


class TestFileIcons:
    """Tests for file icon mappings."""

    def test_file_icons_is_dict(self) -> None:
        """File icons should be a dictionary."""
        assert isinstance(FILE_ICONS, dict)

    def test_python_icon_present(self) -> None:
        """Python file icon should be present."""
        assert '.py' in FILE_ICONS

    def test_icon_values_are_strings(self) -> None:
        """All icon values should be non-empty strings."""
        for ext, icon in FILE_ICONS.items():
            assert isinstance(icon, str)
            assert len(icon) > 0
