# -*- coding: utf-8 -*-
"""
Pytest configuration and fixtures for AI Context Studio tests.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Add src to path for imports - ensure our src package takes precedence
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for tests.

    Yields:
        Path to temporary directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_project(temp_dir: Path) -> Path:
    """
    Create a sample project structure for testing.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to the project root.
    """
    # Create directory structure
    (temp_dir / "src").mkdir()
    (temp_dir / "tests").mkdir()
    (temp_dir / "docs").mkdir()

    # Create sample Python files
    (temp_dir / "src" / "main.py").write_text(
        '#!/usr/bin/env python3\n"""Main module."""\n\ndef main():\n    print("Hello")\n',
        encoding='utf-8'
    )
    (temp_dir / "src" / "utils.py").write_text(
        '"""Utility functions."""\n\ndef helper():\n    return 42\n',
        encoding='utf-8'
    )

    # Create test file
    (temp_dir / "tests" / "test_main.py").write_text(
        '"""Test main module."""\n\ndef test_main():\n    assert True\n',
        encoding='utf-8'
    )

    # Create config files
    (temp_dir / "README.md").write_text(
        '# Sample Project\n\nThis is a test project.\n',
        encoding='utf-8'
    )
    (temp_dir / "requirements.txt").write_text(
        'pytest>=7.0\nblack>=22.0\n',
        encoding='utf-8'
    )

    # Create ignored directories
    (temp_dir / "__pycache__").mkdir()
    (temp_dir / "__pycache__" / "main.cpython-310.pyc").write_bytes(b'\x00')
    (temp_dir / ".git").mkdir()
    (temp_dir / ".git" / "config").write_text('[core]\n', encoding='utf-8')

    return temp_dir


@pytest.fixture
def sample_code_content() -> str:
    """
    Return sample code content for testing.

    Returns:
        Sample Python code as string.
    """
    return '''
#!/usr/bin/env python3
"""Sample module for testing."""

from typing import Optional

class SampleClass:
    """A sample class."""

    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        """Return a greeting."""
        return f"Hello, {self.name}!"

def sample_function(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y
'''


@pytest.fixture
def mock_config_dir(temp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Create a mock configuration directory.

    Args:
        temp_dir: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        Path to mock config directory.
    """
    config_dir = temp_dir / ".ai_context_studio"
    config_dir.mkdir()

    # Monkeypatch the config paths
    from ai_context_studio import constants
    monkeypatch.setattr(constants, 'CONFIG_DIR', config_dir)
    monkeypatch.setattr(constants, 'CONFIG_FILE', config_dir / "config.json")
    monkeypatch.setattr(constants, 'KEY_FILE', config_dir / ".keyfile")
    monkeypatch.setattr(constants, 'MODELS_CACHE_FILE', config_dir / "models_cache.json")

    return config_dir
