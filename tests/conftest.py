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

PAID_API_BLOCKED = "paid API blocked in tests"


def _raise_paid_api_blocked(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError(PAID_API_BLOCKED)


@pytest.fixture(autouse=True)
def _block_paid_gemini_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent accidental live Gemini/Google billable API calls during tests.

    Patches ``google.genai.Client.__init__`` so a real client cannot be
    constructed. Existing tests that assign a MagicMock/SimpleNamespace to
    ``GeminiAPIClient._client`` are unaffected because they never instantiate
    ``Client``. ``Models.generate_content`` / ``Models.list`` are also wrapped
    as a second layer if a real client object somehow already exists.
    """
    try:
        from google.genai.client import Client
        from google.genai.models import Models
    except ImportError:
        return

    monkeypatch.setattr(Client, "__init__", _raise_paid_api_blocked)
    monkeypatch.setattr(Models, "generate_content", _raise_paid_api_blocked)
    monkeypatch.setattr(Models, "list", _raise_paid_api_blocked)

    try:
        from ai_context_studio import api_client as api_client_mod
    except ImportError:
        return

    if api_client_mod.genai is not None:
        monkeypatch.setattr(api_client_mod.genai.Client, "__init__", _raise_paid_api_blocked)


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

    from ai_context_studio import config as config_mod
    from ai_context_studio import constants
    from ai_context_studio import custom_prompts as custom_prompts_mod
    from ai_context_studio.config import ConfigManager
    from ai_context_studio.custom_prompts import reset_custom_prompts_manager
    from ai_context_studio.token_estimator import CostHistoryManager

    config_file = config_dir / "config.json"
    key_file = config_dir / ".keyfile"
    models_cache = config_dir / "models_cache.json"
    prompts_file = config_dir / "custom_prompts.json"
    history_file = config_dir / "cost_history.json"

    monkeypatch.setattr(constants, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(constants, "CONFIG_FILE", config_file)
    monkeypatch.setattr(constants, "KEY_FILE", key_file)
    monkeypatch.setattr(constants, "MODELS_CACHE_FILE", models_cache)

    monkeypatch.setattr(config_mod, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)
    monkeypatch.setattr(config_mod, "KEY_FILE", key_file)
    monkeypatch.setattr(config_mod, "MODELS_CACHE_FILE", models_cache)

    monkeypatch.setattr(custom_prompts_mod, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(custom_prompts_mod, "CUSTOM_PROMPTS_FILE", prompts_file)
    monkeypatch.setattr(CostHistoryManager, "HISTORY_FILE", history_file)

    ConfigManager.reset_instance()
    reset_custom_prompts_manager()

    yield config_dir

    ConfigManager.reset_instance()
    reset_custom_prompts_manager()
