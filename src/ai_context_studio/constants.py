# -*- coding: utf-8 -*-
"""
Constants and configuration values for AI Context Studio.

This module contains all application-wide constants including:
- Application metadata
- Supported file extensions
- Ignored directories
- Configuration paths
- Color schemes
"""

from __future__ import annotations

from pathlib import Path


# Application metadata
APP_NAME: str = "AI Context Studio"
APP_VERSION: str = "2.1.0"
APP_AUTHOR: str = "Giancarlo Allegretti"

# File extensions supported for code analysis
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    '.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.scss', '.sass',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
    '.java', '.kt', '.scala', '.cpp', '.c', '.h', '.hpp',
    '.go', '.rs', '.rb', '.php', '.swift', '.m',
    '.md', '.rst', '.txt', '.sql', '.graphql', '.proto',
    '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd',
    '.xml', '.xsl', '.xslt', '.vue', '.svelte'
})

# Directories to ignore during scanning
DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset({
    '.git', '.svn', '.hg', 'node_modules', 'bower_components',
    '__pycache__', '.pytest_cache', '.mypy_cache',
    'venv', '.venv', 'env', '.env', '.idea', '.vscode', '.vs',
    'dist', 'build', 'out', 'target', '.tox', '.nox',
    'htmlcov', '.coverage', 'eggs', '.eggs',
    '.terraform', '.serverless', 'vendor', 'packages',
})

# Configuration paths
CONFIG_DIR: Path = Path.home() / ".ai_context_studio"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
KEY_FILE: Path = CONFIG_DIR / ".keyfile"
MODELS_CACHE_FILE: Path = CONFIG_DIR / "models_cache.json"

# Token estimation settings
TOKEN_FACTOR: int = 4  # Characters per token (approximate)
MODELS_CACHE_HOURS: int = 24

# Maximum file size to process (1MB)
MAX_FILE_SIZE: int = 1_000_000

# Maximum directory depth for scanning
MAX_SCAN_DEPTH: int = 20

# UI Color scheme
COLORS: dict[str, str] = {
    'primary': '#2563eb',
    'primary_hover': '#1d4ed8',
    'success': '#16a34a',
    'success_hover': '#15803d',
    'warning': '#d97706',
    'danger': '#dc2626',
    'danger_hover': '#b91c1c',
    'purple': '#7c3aed',
    'purple_hover': '#6d28d9',
    'teal': '#0d9488',
    'teal_hover': '#0f766e',
    'pink': '#db2777',
    'orange': '#ea580c',
    'slate': '#475569',
    'bg_dark': '#0f172a',
    'bg_card': '#ffffff',
    'text_muted': '#64748b',
    'bg_light': '#f8fafc',
}

# File type icons for display
FILE_ICONS: dict[str, str] = {
    '.py': '\U0001F40D',   # Python snake
    '.js': '\U0001F4DC',   # Scroll
    '.ts': '\U0001F4D8',   # Blue book
    '.jsx': '\u269B\uFE0F',  # Atom
    '.tsx': '\u269B\uFE0F',  # Atom
    '.html': '\U0001F310',  # Globe
    '.css': '\U0001F3A8',   # Palette
    '.json': '\U0001F4CB',  # Clipboard
    '.md': '\U0001F4DD',    # Memo
    '.sql': '\U0001F5C4\uFE0F',  # File cabinet
    '.java': '\u2615',      # Coffee
    '.go': '\U0001F439',    # Hamster
    '.rs': '\U0001F980',    # Crab
}
